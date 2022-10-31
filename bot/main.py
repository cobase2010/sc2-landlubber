import random
import sys
import time
import sc2
from sc2.data import Difficulty, Race
from sc2.data import race_townhalls
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.player import Bot, Computer
from sc2.bot_ai import BotAI
from bot.army.army import ArmyManager
from bot.opponent.opponent import Opponent
from bot.economy import economy, tech
from bot.economy.build import Builder
from bot.util.debug import DebugPrinter
from bot.util.log import TerminalLogger
from bot.util.map import Map
from bot.util.timer import Timer


class MyBot(BotAI):
    def __init__(self):
        # BotAI.__init__(self)
        self.proxy_built = False
        # self.unit_command_uses_self_do = True
        self.raw_affects_selection = True
        self.distance_calculation_method: int = 2
    
    async def on_before_start(self):
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
    async def on_start(self):
        self.first_step = False
        start = time.time()
        self.expansions_sorted = economy.get_expansion_order(self.logger, self.expansion_locations, self.start_location)
        self.hq_front_door = self.army.guess_front_door()
        self.army_attack_point = self.hq_front_door
        self.opponent.deferred_init()
        self.army.deferred_init()
        self.map.deferred_init()
        self.logger.log("First step took {:.2f}s".format(time.time() - start))

    async def on_end(self, result):
        self.logger.log(f"Game ended in {result} with score {self.state.score.score}")

    async def on_step(self, iteration):
        try:
            step_start = time.time()
            # budget = self.time_budget_available  # pylint: disable=no-member
            # if budget and budget < 0.3:
            #     self.logger.error(f"Skipping step to avoid post-cooldown vegetable bug, budget {budget:.3f}")
            # else:
            await self.main_loop(iteration)
            self.debugger.warn_for_step_duration(step_start)
            self.debugger.step_durations.append(time.time() - step_start)
        except Exception as crash:
            # print("ONLY SUCKERS CRASH!", crash)
            raise crash

    async def main_loop(self, iteration):
        if self.state.action_errors:
            self.logger.error(self.state.action_errors)
        if self.first_step:
            await self.on_start()
            return
        else:
            self.opponent.refresh()
            self.army.refresh()
        if not self.townhalls.exists:
            self.army.kamikaze()
            return

        actions = []
        if iteration % 100 == 0:
            print(f"{iteration}, n_workers: {self.workers.amount}, n_idle_workers: {self.workers.idle.amount},", \
                    f"minerals: {self.minerals}, gas: {self.vespene}, supply: {self.supply_used}/{self.supply_cap},", \
                    f"extractors: {self.structures(UnitTypeId.EXTRACTOR).amount},", \
                    f"roachwarren: {self.structures(UnitTypeId.ROACHWARREN).amount}, spires: {self.structures(UnitTypeId.SPIRE).amount}", \
                    f"lair: {self.structures(UnitTypeId.LAIR).amount}, hachery: {self.structures(UnitTypeId.HATCHERY).amount}", \
                    f"zerg: {self.units(UnitTypeId.ZERGLING).amount}, roach: {self.units(UnitTypeId.ROACH).amount}", \
                    f"mutalisk: {self.units(UnitTypeId.MUTALISK).amount}, queen: {self.units(UnitTypeId.QUEEN).amount}", \
                )
            

        if self.drone_eco_optimization_timer.rings:
            economy.reassign_overideal_drones(self)
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
            actions += economy.produce_larvae(self)
        # print(actions)
        # await self.do(actions)
        # await self._do_actions(actions)
        # result = await self.client.actions(actions)
        # return result

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
        await self._client._send_debug()
