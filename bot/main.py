import random
import sc2
import sys
import time
from sc2 import Race, Difficulty
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.data import race_townhalls
from sc2.player import Bot, Computer
from sc2.position import Point3
from bot.army import army
from bot.army.opponent import Opponent
from bot.economy import build
from bot.economy import economy
from bot.economy import tech
from bot.debug import debug
from bot.debug.debug import DebugPrinter
from bot.util.log import TerminalLogger


class MyBot(sc2.BotAI):
    def on_start(self):
        self.logger = TerminalLogger(self)
        self.debugger = DebugPrinter(self)
        self.opponent = Opponent(self)
        
        self.iteration = 0  # FIXME We should probably not time things based on steps, but time
        self.previous_step_duration_millis = 0.0
        self.tick_millis = 0
        self.tick_millis_since_last_base_management = 0
        self.match_start_time = time.time()
        self.score_logged = False
        self.active_expansion_builder = None
        self.active_scout_tag = None
        self.expansions_sorted = []
        self.ramps_distance_sorted = None
        self.first_step = True
        self.last_cap_covered = 0
        self.hq_loss_handled = False
        self.hq_front_door = None
        self.hq_scout_found_front_door = False
        self.army_attack_point = None
        self.army_spawn_rally_point = None
        self.logger.log("Game started, gl hf!")

    def on_end(self, result):
        self.logger.log("Game ended in " + str(result))
        self.logger.log("Score: " + str(self.state.score.score))

    def world_text(self, text, pos):
        if pos:
            self._client.debug_text_world(text, Point3((pos.position.x, pos.position.y, 10)), None, 14)
        else:
            self.logger.error("Received None position to draw text")

    async def on_step(self, iteration):
        # TODO FIXME Before the deadline, switch raise to return and wrap in try-except
        self.iteration = iteration
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
        self.previous_step_duration_millis = (time.time() - step_start) * 1000


    # MAIN LOOP =========================================================================
    async def main_loop(self):
        self.tick_millis = int(self.time * 1000)
        if self.state.action_errors:
            self.logger.error(self.state.action_errors)

        if self.first_step:
            self.first_step = False
            start = time.time()
            self.expansions_sorted = economy.get_expansion_order(self.logger, self.expansion_locations, self.start_location)
            self.hq_front_door = army.guess_front_door(self)
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
            await army.kamikaze(self, forces)
            return

        actions += army.get_army_actions(
            self,
            self.iteration, # <- TODO remove iteration
            # TODO we should filter out non-fighting
            forces, #forces.idle,  # TODO all_units or just idle?
            self.known_enemy_structures,
            self.enemy_start_locations,
            self.units,  # TODO all_units or just idle?
            self.time,
            self.supply_used)
        actions += army.patrol_with_overlords(
            overlords,
            self.hq_front_door,
            self.start_location,
            self.enemy_start_locations)

        # Non-time-critical
        if (self.tick_millis - self.tick_millis_since_last_base_management) >= 500:
            self.tick_millis_since_last_base_management = self.tick_millis

            # Hatchery rally points
            for hatch in self.townhalls:
                actions.append(hatch(AbilityId.RALLY_HATCHERY_UNITS, self.army_spawn_rally_point))
                if not hatch.is_ready:
                    actions.append(hatch(AbilityId.RALLY_HATCHERY_WORKERS, economy.get_closest_mineral_for_hatchery(self.state.mineral_field(), hatch)))

            actions += build.train_units(self, larvae)
            await build.begin_projects(self)
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

            actions += army.base_defend(self, forces)

        await self.do_actions(actions)

        self.debugger.warn_unoptimal_play()
        self.debugger.print_score()
        self.debugger.print_running_speed()
        self.world_text("door", self.hq_front_door)
        await self._client.send_debug()
