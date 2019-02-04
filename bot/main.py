import random
import sys
import time
import sc2
from sc2 import Difficulty, Race
from sc2.data import race_townhalls
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.player import Bot, Computer
from bot.army.army import ArmyManager
from bot.opponent.opponent import Opponent
from bot.economy import economy, tech
from bot.economy.build import Builder
from bot.util.debug import DebugPrinter
from bot.util.log import TerminalLogger
from bot.util.map import Map
from bot.util.timer import Timer


class MyBot(sc2.BotAI):
    def on_start(self):
        self.logger = TerminalLogger(self)
        self.debugger = DebugPrinter(self)
        self.opponent = Opponent(self)
        self.army = ArmyManager(self)
        self.builder = Builder(self)
        self.map = Map(self)
        
        self.drone_eco_optimization_timer = Timer(self, 0.2)
        self.army_timer = Timer(self, 0.05)
        self.build_timer = Timer(self, 0.5)
        self.match_status_timer = Timer(self, 60)
        self.warn_timer = Timer(self, 3)

        self.score_logged = False
        self.active_expansion_builder = None
        self.expansions_sorted = []
        self.ramps_distance_sorted = None
        self.first_step = True
        self.hq_loss_handled = False
        self.hq_front_door = None
        self.army_attack_point = None

    # Deferred actions after game state is available
    def on_first_step(self):
        self.first_step = False
        start = time.time()
        self.expansions_sorted = economy.get_expansion_order(self.logger, self.expansion_locations, self.start_location)
        self.hq_front_door = self.army.guess_front_door()
        self.army_attack_point = self.hq_front_door
        self.opponent.deferred_init()
        self.army.deferred_init()
        self.map.deferred_init()
        self.logger.log("First step took {:.2f}s".format(time.time() - start))

    def on_end(self, result):
        self.logger.log(f"Game ended in {result} with score {self.state.score.score}")

    async def on_step(self, iteration):
        # TODO FIXME Before the deadline, switch raise to return and wrap in try-except
        step_start = time.time()
        budget = self.time_budget_available  # pylint: disable=no-member
        if budget and budget < 0.3:
            self.logger.error(f"Skipping step to avoid post-cooldown vegetable bug, budget {budget:.3f}")
            self.debugger.step_durations.append(time.time() - step_start)
            # return
            raise Exception
        else:
            await self.main_loop()
            self.debugger.warn_for_step_duration(step_start)
            self.debugger.step_durations.append(time.time() - step_start)
            # try:
            # except Exception as e:
            #     print("ONLY SUCKERS CRASH!", e)

    async def main_loop(self):
        if self.state.action_errors:
            self.logger.error(self.state.action_errors)
        if self.first_step:
            self.on_first_step()
            return
        else:
            self.opponent.refresh()
            self.army.refresh()
        if not self.townhalls.exists:
            await self.army.kamikaze()
            return

        actions = []

        if self.drone_eco_optimization_timer.rings:
            await economy.reassign_overideal_drones(self)  # TODO combine to drone actions below
            actions += economy.get_drone_actions(self)

        if self.army_timer.rings:
            actions += self.army.get_army_actions()
            actions += self.army.patrol_with_overlords()
            actions += self.army.scout_and_harass()
            actions += self.army.scout_no_mans_expansions()
            actions += self.army.flank()
            actions += self.army.base_defend()

        if self.build_timer.rings:
            actions += economy.set_hatchery_rally_points(self)
            actions += self.builder.train_units()
            await self.builder.begin_projects()
            actions += tech.upgrade_tech(self)
            actions += await economy.produce_larvae(self)

        await self.do_actions(actions)

        if self.match_status_timer.rings:
            self.debugger.print_score()
            self.debugger.print_step_stats()
        if self.warn_timer.rings:
            self.debugger.warn_unoptimal_play()
        self.debugger.world_text("door", self.hq_front_door)
        scouts = self.army.no_mans_expansions_scouts.select_units(self.units)
        if scouts:
            for scout in scouts:
                self.debugger.world_text("scout", scout.position)
        await self._client.send_debug()
