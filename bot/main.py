import random
import sc2
import sys
import time
from sc2 import Race, Difficulty
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.data import race_townhalls
from sc2.player import Bot, Computer
from bot.army.army import ArmyManager
from bot.army.opponent import Opponent
from bot.economy.build import Builder
from bot.economy import economy
from bot.economy import tech
from bot.debug import debug
from bot.debug.debug import DebugPrinter
from bot.util.log import TerminalLogger
from bot.util.timer import Timer


class MyBot(sc2.BotAI):
    def on_start(self):
        self.logger = TerminalLogger(self)
        self.debugger = DebugPrinter(self)
        self.opponent = Opponent(self)
        self.builder = Builder(self)
        self.army = ArmyManager(self)
        
        self.army_actions_timer = Timer(self, 0.1)
        self.build_timer = Timer(self, 0.5)
        self.match_status_timer = Timer(self, 60)
        self.warn_timer = Timer(self, 3)

        self.score_logged = False
        self.active_expansion_builder = None
        self.active_scout_tag = None
        self.expansions_sorted = []
        self.ramps_distance_sorted = None
        self.first_step = True
        self.hq_loss_handled = False
        self.hq_front_door = None
        self.hq_scout_found_front_door = False
        self.army_attack_point = None
        self.army_spawn_rally_point = None
        self.logger.log("Game started, gl hf!")

    def on_end(self, result):
        self.logger.log("Game ended in " + str(result))
        self.logger.log("Score: " + str(self.state.score.score))

    async def on_step(self, iteration):
        # TODO FIXME Before the deadline, switch raise to return and wrap in try-except
        step_start = time.time()
        budget = self.time_budget_available  # pylint: disable=no-member
        if budget and budget < 0.3:
            self.logger.error(f"Skipping step to avoid post-cooldown vegetable bug, budget {budget:.3f}")
            # return
            raise Exception
        else:
            await self.main_loop()
            self.debugger.warn_for_step_duration(step_start)
            # try:
            # except Exception as e:
            #     print("ONLY SUCKERS CRASH!", e)


    # MAIN LOOP =========================================================================
    async def main_loop(self):
        if self.state.action_errors:
            self.logger.error(self.state.action_errors)

        if self.first_step:
            self.first_step = False
            start = time.time()
            self.expansions_sorted = economy.get_expansion_order(self.logger, self.expansion_locations, self.start_location)
            self.hq_front_door = self.army.guess_front_door()
            self.army_attack_point = self.hq_front_door
            self.army_spawn_rally_point = self.hq_front_door
            self.logger.log("Init calculations took {:.2f}s".format(time.time() - start))
            return
        else:
            self.opponent.refresh()

        larvae = self.units(UnitTypeId.LARVA)
        overlords = self.units(UnitTypeId.OVERLORD)
        forces = self.units(UnitTypeId.ZERGLING).ready | self.units(UnitTypeId.ROACH).ready | self.units(UnitTypeId.HYDRALISK).ready | self.units(UnitTypeId.MUTALISK).ready
        # forces_ground = self.units(UnitTypeId.ZERGLING) | self.units(UnitTypeId.ROACH) | self.units(UnitTypeId.HYDRALISK)
        # forces_air = self.units(UnitTypeId.MUTALISK)
        actions = []

        if not self.townhalls.exists:
            await self.army.kamikaze(forces)
            return

        actions += self.army.get_army_actions(
            self.army_actions_timer,
            # TODO we should filter out non-fighting
            forces, #forces.idle,  # TODO all_units or just idle?
            self.known_enemy_structures,
            self.enemy_start_locations,
            self.units,  # TODO all_units or just idle?
            self.time,
            self.supply_used)
        actions += self.army.patrol_with_overlords(
            overlords,
            self.hq_front_door,
            self.start_location,
            self.enemy_start_locations)

        if self.build_timer.rings:
            # Hatchery rally points
            for hatch in self.townhalls:
                actions.append(hatch(AbilityId.RALLY_HATCHERY_UNITS, self.army_spawn_rally_point))
                if not hatch.is_ready:
                    actions.append(hatch(AbilityId.RALLY_HATCHERY_WORKERS, economy.get_closest_mineral_for_hatchery(self.state.mineral_field(), hatch)))

            actions += self.builder.train_units(larvae)
            await self.builder.begin_projects()
            await economy.reassign_overideal_drones(self)
            actions += tech.upgrade_tech(self)
            actions += await economy.produce_larvae(self)
            actions += economy.assign_idle_drones_to_minerals(self)
            actions += economy.assign_drones_to_extractors(self)

            # Scouting
            scout = self.units.find_by_tag(self.active_scout_tag)
            if not scout:
                if self.units(UnitTypeId.ZERGLING).ready.exists:
                    scout = self.units(UnitTypeId.ZERGLING).ready.first
                    self.active_scout_tag = scout.tag
                    self.logger.log("Assigned a new zergling scout " + str(scout.tag))
                elif self.units(UnitTypeId.ROACHWARREN).exists and self.units(UnitTypeId.DRONE).ready.exists:
                    scout = self.units(UnitTypeId.DRONE).ready.random
                    self.active_scout_tag = scout.tag
                    self.logger.log("Assigned a new drone scout " + str(scout.tag))
            if scout:
                if scout.is_idle:
                    if self.opponent.unverified_hq_locations:
                        targets = self.opponent.unverified_hq_locations
                    else:
                        targets = self.expansions_sorted
                    for location in targets:
                        actions.append(scout.move(location, queue=True))
                else:
                    if not self.hq_scout_found_front_door:
                        for ramp in self._game_info.map_ramps:
                            if scout.distance_to(ramp.top_center) < 5:
                                self.hq_scout_found_front_door = True
                                self.hq_front_door = ramp.top_center
                                self.logger.log("Scout verified front door")

            actions += self.army.base_defend(forces)

        await self.do_actions(actions)

        if self.match_status_timer.rings:
            self.debugger.print_score()
        if self.warn_timer.rings:
            self.debugger.warn_unoptimal_play()
        self.debugger.world_text("door", self.hq_front_door)
        await self._client.send_debug()
