import random
import logging
import sc2
import sys
import time
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.data import race_townhalls
from sc2.player import Bot, Computer
from sc2.position import Point3
import bot.army as army
import bot.build as build
import bot.economy as economy
import bot.tech as tech
import bot.debug as debug

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
log_format = logging.Formatter('%(levelname)-8s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(log_format)
logger.addHandler(handler)


class MyBot(sc2.BotAI):
    def on_start(self):
        self.tick_millis = 0
        self.tick_millis_since_last_base_management = 0
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
        self.hq_scout_found_front_door = False
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

    def world_text(self, text, pos):
        if pos:
            self._client.debug_text_world(text, Point3((pos.position.x, pos.position.y, 10)), None, 14)
        else:
            self.log("Received None position to draw text", logging.ERROR)

    def log(self, msg, level=logging.INFO):
        logger.log(level, "{:4.1f} {:3}/{:3} {}".format(self.time / 60, self.supply_used, self.supply_cap, msg))

    async def on_step(self, iteration):
        step_start = time.time()
        await self.main_loop(iteration)
        debug.warn_for_step_duration(self, step_start)
        # try:
        # except Exception as e:
        #     print("ONLY SUCKERS CRASH!", e)


    # MAIN LOOP =========================================================================
    async def main_loop(self, iteration):
        self.tick_millis = int(self.time * 1000)
        if self.state.action_errors:
            self.log(self.state.action_errors, logging.ERROR)

        if not self.init_calculation_done:
            start = time.time()
            self.expansions_sorted = economy.get_expansion_order(self.expansion_locations, self.start_location, self.enemy_start_locations, logger)
            self.enemy_start_locations_not_yet_scouted = self.enemy_start_locations
            if len(self.enemy_start_locations) == 1:
                self.enemy_known_base_locations.append(self.enemy_start_locations[0])
            self.hq_front_door = army.guess_front_door(self)
            self.army_attack_point = self.hq_front_door
            self.army_spawn_rally_point = self.hq_front_door
            self.init_calculation_done = True
            self.log("Init calculations took {:.2f}s".format(time.time() - start))
            return

        larvae = self.units(LARVA)
        overlords = self.units(OVERLORD)
        forces = self.units(ZERGLING).ready | self.units(ROACH).ready | self.units(HYDRALISK).ready | self.units(MUTALISK).ready
        # forces_ground = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        # forces_air = self.units(MUTALISK)
        actions = []

        if not self.townhalls.exists:
            await army.kamikaze(self, forces)
            return

        actions += army.get_army_actions(
            self,
            iteration,
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
                actions.append(hatch(RALLY_HATCHERY_UNITS, self.army_spawn_rally_point))
                if not hatch.is_ready:
                    actions.append(hatch(RALLY_HATCHERY_WORKERS, economy.get_closest_mineral_for_hatchery(self.state.mineral_field(), hatch)))

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
                if self.units(ZERGLING).ready.exists:
                    scout = self.units(ZERGLING).ready.first
                    self.active_scout_tag = scout.tag
                    self.log("Assigned a new zergling scout " + str(scout.tag), logging.INFO)
                elif self.units(ROACHWARREN).exists and self.units(DRONE).ready.exists:
                    scout = self.units(DRONE).ready.random
                    self.active_scout_tag = scout.tag
                    self.log("Assigned a new drone scout " + str(scout.tag), logging.INFO)
            if scout:
                if scout.is_idle:
                    if self.enemy_start_locations_not_yet_scouted:
                        targets = self.enemy_start_locations_not_yet_scouted
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
                                self.log("Scout verified front door")

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

        await self.do_actions(actions)

        debug.warn_unoptimal_play(self, iteration)
        debug.print_score(self, iteration)
        debug.print_running_speed(self, iteration)
        self.world_text("door", self.hq_front_door)
        await self._client.send_debug()
