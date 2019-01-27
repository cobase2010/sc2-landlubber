import random
import logging
import sc2
import sys
import time
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls
import bot.army as army
import bot.build as build
import bot.economy as economy
import bot.tech as tech

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
log_format = logging.Formatter('%(levelname)-8s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(log_format)
logger.addHandler(handler)

MAX_BASE_DOOR_RANGE = 30

def print_running_speed(bot):
    elapsed_realtime = time.time() - bot.match_start_time
    bot.log("real={:.0f}s game={:.0f}s iter={} speed={:.0f}x it/rt={:.0f} it/gt={:.1f}".format(
        elapsed_realtime,
        bot.time,
        iteration,
        bot.time / elapsed_realtime,
        iteration / elapsed_realtime,
        iteration / bot.time
    ), logging.INFO)


def print_score(bot):
    s = bot.state.score
    bot.log("score  unit stru   minerals    gas      rate     idle")
    bot.log("{:5} {:5.0f} {:4.0f} {:5.0f}/{:5.0f} {:3.0f}/{:3.0f} {:4.0f}/{:3.0f} {:.0f}/{:.0f}".format(
        s.score,
        s.total_value_units,
        s.total_value_structures,
        s.spent_minerals,
        s.collected_minerals,
        s.spent_vespene,
        s.collected_vespene,
        s.collection_rate_minerals,
        s.collection_rate_vespene,
        s.idle_worker_time,
        s.idle_production_time
    ))


class MyBot(sc2.BotAI):
    def guess_front_door(self):
        # Bot has main_base_ramp but it sometimes points to the back door ramp if base has multiple ramps
        self.ramps_distance_sorted = sorted(self._game_info.map_ramps, key=lambda ramp: ramp.top_center.distance_to(self.start_location))
        doors = []
        for ramp in self.ramps_distance_sorted:
            if ramp.top_center.distance_to(self.start_location) <= MAX_BASE_DOOR_RANGE:
                doors.append(ramp)
        if len(doors) == 1:
            self.log("This base seems to have only one ramp")
            return doors[0].top_center
        elif len(doors) == 2:
            self.log("This base seems to have two ramps, let's make a guess and rally at the smaller one", logging.WARNING)
            if doors[0].size < doors[1].size:
                return doors[0].top_center
            else:
                return doors[1].top_center
        else:
            self.log("This base seems to have many ramps, hard to tell where to rally", logging.ERROR)
            return self.start_location.towards(self.game_info.map_center, 10)

    def on_start(self):
        self.match_start_time = time.time()
        self.score_logged = False
        self.active_expansion_builder = None
        self.active_scout_tag = None
        self.enemy_start_locations_not_yet_scouted = []
        self.enemy_known_base_locations = []
        self.expansions_sorted = []
        self.ramps_distance_sorted = None
        self.init_calculation_done = False
        self.last_cap_covered = 0
        self.hq_loss_handled = False
        self.hq_front_door = None
        self.army_attack_point = None
        self.army_spawn_rally_point = None
        if self.enemy_race != Race.Random:
            self.known_enemy_race = self.enemy_race
        else:
            self.known_enemy_race = None
        logger.info("Game started, gl hf!")

    def on_end(self, result):
        self.log("Game ended in " + str(result))
        self.log("Score: " + str(self.state.score.score))
        # from pprint import pprint
        # pprint(vars(self.state.score))

    def log(self, msg, level=logging.INFO):
        time_in_minutes = self.time / 60
        cap_usage = "{}/{}".format(self.supply_used, self.supply_cap)
        logger.log(level, "{:4.1f} {:7} {}".format(time_in_minutes, cap_usage, msg))

    def should_train_overlord(self):
        if self.can_afford(OVERLORD):
            if self.units(OVERLORD).amount == 1:
                cap_safety_buffer = 0
            else:
                cap_safety_buffer = 2 * len(self.townhalls.ready)
            should = self.supply_left <= cap_safety_buffer and self.supply_cap != self.last_cap_covered and self.supply_cap < 200
            return should

    async def reassign_overideal_drones(self, old_town):
        if old_town.assigned_harvesters > old_town.ideal_harvesters:
            drone = economy.get_reassignable_drone(old_town, self.workers)
            new_town = economy.get_town_with_free_jobs(self.townhalls, old_town)
            if new_town and drone:
                self.log("Reassigning drone from overcrowded town", logging.DEBUG)
                mineral = economy.get_closest_mineral_for_hatchery(self.state.mineral_field(), new_town)
                await self.do_actions([drone.gather(mineral)])


    async def on_step(self, iteration):
        await self.main_loop(iteration)
        # try:
        # except Exception as e:
        #     print("ONLY SUCKERS CRASH!", e)


    # MAIN LOOP =========================================================================
    async def main_loop(self, iteration):
        if self.state.action_errors:
            self.log(self.state.action_errors, logging.ERROR)

        if self.time in [300, 600, 900, 1145]:
            print_score(self)

        if iteration % 100 == 0 and self.time > 0:
            print_running_speed(self)

        # Computationally heavy calculations that may cause step timeout unless handled separately
        if not self.init_calculation_done:
            if iteration == 0:
                self.expansions_sorted = economy.get_expansion_order(self.expansion_locations, self.start_location, self.enemy_start_locations, logger)
            else:
                self.enemy_start_locations_not_yet_scouted = self.enemy_start_locations
                if len(self.enemy_start_locations) == 1:
                    self.enemy_known_base_locations.append(self.enemy_start_locations[0])
                self.hq_front_door = self.guess_front_door()
                self.army_attack_point = self.hq_front_door
                self.army_spawn_rally_point = self.hq_front_door
                self.init_calculation_done = True
            return

        larvae = self.units(LARVA)
        overlords = self.units(OVERLORD)
        forces = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK) | self.units(MUTALISK)
        forces_ground = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        forces_air = self.units(MUTALISK)
        actions = []

        # Kamikaze if all bases lost
        if not self.townhalls.exists:
            if not self.hq_loss_handled:
                self.hq_loss_handled = True
                self.log("All townhalls lost, loss is probably imminent!", logging.WARNING)
                if self.enemy_start_locations:
                    for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                        actions.append(unit.attack(self.enemy_start_locations[0]))
                    await self.do_actions(actions)
            return

        actions += army.get_army_actions(
            self,
            iteration,
            forces.idle,
            self.known_enemy_structures,
            self.enemy_start_locations,
            self.units,
            self.time,
            self.supply_used)
        actions += army.patrol_with_overlords(overlords, self.hq_front_door, self.start_location)

        # Hatchery rally points
        if iteration % 10 == 0:
            for hatch in self.townhalls:
                actions.append(hatch(RALLY_HATCHERY_UNITS, self.army_spawn_rally_point))
                if not hatch.is_ready:
                    actions.append(hatch(RALLY_HATCHERY_WORKERS, economy.get_closest_mineral_for_hatchery(self.state.mineral_field(), hatch)))

        # Training units
        for townhall in self.townhalls:
            await self.reassign_overideal_drones(townhall)
            town_larvae = larvae.closer_than(5, townhall)
            # TODO This currently trains one unit and one or more buildings per cycle.
            # Should we while loop larvae? Or should we only build max one building per cycle?
            if town_larvae.exists:
                larva = town_larvae.random
                if self.should_train_overlord():
                    self.log("Training overlord", logging.DEBUG)
                    actions.append(larva.train(OVERLORD))
                    self.last_cap_covered = self.supply_cap
                elif economy.should_train_drone(self, townhall):
                    self.log("Training drone, current situation at this expansion {}/{}".format(townhall.assigned_harvesters, townhall.ideal_harvesters), logging.DEBUG)
                    actions.append(larva.train(DRONE))
                else:
                    if self.can_afford(MUTALISK) and self.units(SPIRE).ready.exists:
                        actions.append(larva.train(MUTALISK))
                        self.log("Training mutalisk", logging.DEBUG)
                    elif self.can_afford(ROACH) and self.units(ROACHWARREN).ready.exists:
                        actions.append(larva.train(ROACH))
                        self.log("Training roach", logging.DEBUG)
                    elif self.can_afford(ZERGLING) and self.units(SPAWNINGPOOL).ready.exists:
                        self.log("Training ling", logging.DEBUG)
                        actions.append(larva.train(ZERGLING))
            if self.units(SPAWNINGPOOL).ready.exists and townhall.is_ready and townhall.noqueue:
                if self.can_afford(QUEEN):
                    if not self.units(QUEEN).closer_than(10, townhall):
                        self.log("Training queen", logging.INFO)
                        actions.append(townhall.train(QUEEN))

        await build.begin_projects(self)
        actions += tech.upgrade_tech(self)
        actions += await economy.produce_larvae(self)
        actions += economy.assign_idle_drones_to_minerals(self)
        actions += economy.assign_drones_to_extractors(self)

        # Scouting
        scout = self.units.find_by_tag(self.active_scout_tag)
        if not scout:
            if self.units(ZERGLING).ready.exists:
                scout = self.units(ZERGLING).ready.first
                self.active_scout_tag = scout.tag
                self.log("Assigned a new scout " + str(scout.tag), logging.DEBUG)
        if scout:
            if scout.is_idle:
                if self.enemy_start_locations_not_yet_scouted:
                    targets = self.enemy_start_locations_not_yet_scouted
                else:
                    targets = self.expansions_sorted
                for location in targets:
                    actions.append(scout.move(location, queue=True))

        if self.enemy_start_locations_not_yet_scouted and iteration % 10 == 0:
            for i, base in enumerate(self.enemy_start_locations_not_yet_scouted):
                if self.units.closest_distance_to(base) < 10:
                    self.enemy_start_locations_not_yet_scouted.pop(i)
                    if self.known_enemy_structures and self.known_enemy_structures.closest_distance_to(base) < 20:
                        self.enemy_known_base_locations.append(base)

        # Reacting to enemy movement
        if self.known_enemy_units and iteration % 10 == 0:
            # Intelligence
            if self.known_enemy_race is None:
                self.known_enemy_race = self.known_enemy_units[0].race
                self.log("Enemy is now known to be " + str(self.known_enemy_race))

            actions += army.base_defend(self, forces)

        # Warnings
        if self.vespene > 600 and iteration % 30 == 0:
            self.log("Too much gas", logging.WARNING)
        if self.supply_left == 0 and iteration % 30 == 0:
            self.log("Not enough overlords!", logging.WARNING)

        await self.do_actions(actions)
