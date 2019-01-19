import random
import logging
import sc2
import sys
import time
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls
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


class MyBot(sc2.BotAI):
    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position
        return self.enemy_start_locations[0]

    def set_hq_army_rally_point(self):
        # Bot has main_base_ramp but it sometimes points to the back door ramp if base has multiple ramps
        self.ramps_distance_sorted = sorted(self._game_info.map_ramps, key=lambda ramp: ramp.top_center.distance_to(self.start_location))
        doors = []
        for ramp in self.ramps_distance_sorted:
            if ramp.top_center.distance_to(self.start_location) <= MAX_BASE_DOOR_RANGE:
                doors.append(ramp)
        if len(doors) == 1:
            self.hq_army_rally_point = doors[0].top_center
            self.log("This base seems to have only one ramp")
        elif len(doors) == 2:
            self.log("This base seems to have two ramps, let's make a guess and rally at the smaller one", logging.WARNING)
            if doors[0].size < doors[1].size:
                self.hq_army_rally_point = doors[0].top_center
            else:
                self.hq_army_rally_point = doors[1].top_center
        else:
            self.log("This base seems to have many ramps, hard to tell where to rally", logging.ERROR)
            self.hq_army_rally_point = self.start_location.towards(self.game_info.map_center, 10)

    def on_start(self):
        self.expansions_sorted = []
        self.ramps_distance_sorted = None
        self.init_calculation_done = False
        self.first_enemy_base_scouting_done = False
        self.last_cap_covered = 0
        self.hq_army_rally_point = None
        self.hq_loss_handled = False
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
                cap_safety_buffer = 1 * len(self.townhalls)
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
        # Computationally heavy calculations that may cause step timeout unless handled separately
        if not self.init_calculation_done:
            if iteration == 0:
                self.expansions_sorted = economy.get_expansion_order(self.expansion_locations, self.start_location, self.enemy_start_locations, logger)
            else:
                self.set_hq_army_rally_point()
                await self.do(self.townhalls.first(RALLY_HATCHERY_UNITS, self.hq_army_rally_point))
                self.init_calculation_done = True
            return

        larvae = self.units(LARVA)
        overlords = self.units(OVERLORD)
        forces = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        actions = []

        # Kamikaze if all bases lost
        if not self.townhalls.exists:
            if not self.hq_loss_handled:
                self.hq_loss_handled = True
                self.log("All townhalls lost, loss is probably imminent!", logging.WARNING)
                for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                    actions.append(unit.attack(self.enemy_start_locations[0]))
                await self.do_actions(actions)
            return
        else:
            random_townhall = self.townhalls.first

        # Attack to enemy base
        # TODO rally first near enemy base/expansion, and then attack with a larger force
        if len(forces.idle) > 50 and iteration % 50 == 0:
            self.log("Ordering {} forces to attack".format(len(forces.idle)), logging.DEBUG)
            for unit in forces.idle:
                actions.append(unit.attack(self.select_target()))

        # Scout home base with overlords
        for idle_overlord in overlords.idle:
            if len(overlords) < 4:
                patrol = self.hq_army_rally_point.random_on_distance(random.randrange(1, 5))
            else:
                patrol = self.start_location.random_on_distance(random.randrange(20, 30))
            actions.append(idle_overlord.move(patrol))

        # Set rally points for new hatcheries
        if iteration % 100 == 0:
            for hatch in self.units(HATCHERY).not_ready:
                self.log("Setting rally points for new hatchery", logging.DEBUG)
                actions.append(hatch(RALLY_HATCHERY_UNITS, self.hq_army_rally_point))
                actions.append(hatch(RALLY_HATCHERY_WORKERS, economy.get_closest_mineral_for_hatchery(self.state.mineral_field(), hatch)))
            await self.do_actions(actions)
            return

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
                elif self.units(ROACHWARREN).ready.exists and self.can_afford(ROACH):
                    actions.append(larva.train(ROACH))
                    self.log("Training roach", logging.DEBUG)
                elif self.can_afford(ZERGLING):
                    self.log("Training ling", logging.DEBUG)
                    actions.append(larva.train(ZERGLING))
            if self.units(SPAWNINGPOOL).ready.exists and townhall.is_ready and townhall.noqueue:
                if self.can_afford(QUEEN):
                    if not self.units(QUEEN).closer_than(10, townhall):
                        self.log("Training queen", logging.INFO)
                        actions.append(townhall.train(QUEEN))

        # Build tree
        if economy.should_build_hatchery(self.townhalls, self.minerals, self.expansions_sorted):
            self.log("Building hatchery")
            # TODO Should not be so naive that sites are available and building will succeed and remain intact
            await self.build(HATCHERY, self.expansions_sorted.pop(0))
        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                self.log("Building spawning pool")
                await self.build(SPAWNINGPOOL, near=random_townhall)

        if self.units(SPAWNINGPOOL).ready.exists:
            if self.units(EXTRACTOR).amount < 1 and not self.already_pending(EXTRACTOR) and self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor #1")
                actions.append(drone.build(EXTRACTOR, target))
            if not (self.units(SPINECRAWLER).exists or self.already_pending(SPINECRAWLER)) and self.can_afford(SPINECRAWLER):
                self.log("Building spine crawler")
                await self.build(SPINECRAWLER, near=random_townhall)
            if not (self.units(LAIR).exists or self.already_pending(LAIR)) and random_townhall.noqueue:
                if self.can_afford(LAIR):
                    self.log("Building lair")
                    actions.append(self.townhalls.ready.first.build(LAIR))
            if not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)) and self.can_afford(ROACHWARREN):
                self.log("Building roach warren")
                await self.build(ROACHWARREN, near=random_townhall)

        if self.units(ROACHWARREN).ready.exists:
            if self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR) and self.can_afford(EXTRACTOR):
                drone = self.workers.random  # FIXME should be drone near hq, this sometimes picks the drone building expansion
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor #2")
                actions.append(drone.build(EXTRACTOR, target))
            if not (self.units(EVOLUTIONCHAMBER).exists or self.already_pending(EVOLUTIONCHAMBER)) and self.can_afford(EVOLUTIONCHAMBER):
                self.log("Building evolution chamber")
                await self.build(EVOLUTIONCHAMBER, near=random_townhall)

        actions += tech.upgrade_tech(self)
        actions += await economy.produce_larvae(self)
        actions += economy.assign_drones_to_extractors(self)

        if not self.first_enemy_base_scouting_done and self.units(ZERGLING).ready.exists:
            volunteer = self.units(ZERGLING).ready.first
            actions.append(volunteer.move(self.enemy_start_locations[0]))
            self.first_enemy_base_scouting_done = True
            self.log("Scouting enemy base with first ling")

        # Reacting to enemy movement
        if self.known_enemy_units and iteration % 10 == 0:
            # Intelligence
            if self.known_enemy_race is None:
                self.known_enemy_race = self.known_enemy_units[0].race
                self.log("Enemy is now known to be " + str(self.known_enemy_race))

            # Base defend
            for town in self.townhalls:
                enemies_approaching = self.known_enemy_units.closer_than(30, town)
                if enemies_approaching:
                    if len(enemies_approaching) == 1:
                        self.log("Enemy is probably scouting our base", logging.DEBUG)
                    if enemies_approaching(DRONE) | enemies_approaching(PROBE) | enemies_approaching(SCV):
                        self.log("Enemy harvester in our base!", logging.DEBUG)
                    else:
                        self.log("Enemy in our base!", logging.DEBUG)
                enemies_dangerously_near = self.known_enemy_units.closer_than(15, town)
                if enemies_dangerously_near:
                    aggressor = enemies_dangerously_near.first
                    defenders = forces.idle.closer_than(30, aggressor)
                    if defenders:
                        for unit in defenders:
                            actions.append(unit.attack(aggressor.position))  # Attack the position, not the unit to avoid being drawn too far
                    else:
                        if self.time < 180:
                            for drone in self.units(DRONE):
                                actions.append(drone.attack(aggressor.position))

        # Warnings
        if self.vespene > 1000 and iteration % 40 == 0:
            self.log("Too much gas", logging.WARNING)
        if self.supply_left == 0 and iteration % 40 == 0:
            self.log("Not enough overlords!", logging.WARNING)

        await self.do_actions(actions)
