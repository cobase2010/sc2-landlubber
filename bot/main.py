import random
import logging
import sc2
import sys
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
log_format = logging.Formatter('%(levelname)-8s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(log_format)
logger.addHandler(handler)

LOOPS_PER_MIN = 22.4 * 60
HATCHERY_COST_BUFFER_INCREMENT = 100
HATCHERY_COST = 300
EXPANSION_DRONE_THRESHOLD = 0.90
DRONE_TRAINING_PROBABILITY_AT_EXPANSIONS = 70


class MyBot(sc2.BotAI):
    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position
        return self.enemy_start_locations[0]

    def set_expansion_order(self):
        exps = self.expansion_locations
        del exps[self.start_location]
        for enemy in self.enemy_start_locations:
            del exps[enemy]
        sorted = self.start_location.sort_by_distance(exps)

        assert self.start_location not in sorted, "Starting location unexpectedly still in expansion locations"
        for enemy in self.enemy_start_locations:
            assert enemy not in sorted, "Enemy location unexpectedly still in expansion locations"
        self.expansions_sorted = sorted

    def probability(self, percent=50):
        return random.randrange(100) < percent

    def set_hq_army_rally_point(self):
        self.hq_army_rally_point = self.start_location.towards(self.game_info.map_center, 10)

    def get_closest_mineral_for_hatchery(self, hatch):
        mineral = self.state.mineral_field().closest_to(hatch.position)
        return mineral

    def on_start(self):
        self.last_cap_covered = 0
        self.hq_loss_handled = False
        logger.info("Game started, gl hf!")

    def on_end(self, result):
        self.log("Game ended in " + str(result))

    def log(self, msg, level=logging.INFO):
        time_in_minutes = self.state.game_loop / LOOPS_PER_MIN
        cap_usage = "{}/{}".format(self.supply_used, self.supply_cap)
        logger.log(level, "{:4.1f} {:7} {}".format(time_in_minutes, cap_usage, msg))

    def should_train_overlord(self):
        if self.can_afford(OVERLORD):
            if self.units(OVERLORD).amount == 1:
                cap_safety_buffer = 0
            else:
                cap_safety_buffer = 2 * len(self.townhalls)
            should = self.supply_left <= cap_safety_buffer and self.supply_cap != self.last_cap_covered and self.supply_cap < 200
            return should

    def should_train_drone(self, townhall):
        if townhall.assigned_harvesters < townhall.ideal_harvesters and self.can_afford(DRONE):
            if len(self.townhalls) == 1:
                probability = 100
            else:
                probability = DRONE_TRAINING_PROBABILITY_AT_EXPANSIONS
            return self.probability(probability)

    def global_drone_rate(self):
        assigned_drones = 0
        ideal_drone_count = 0
        for town in self.townhalls:
            ideal_drone_count += town.ideal_harvesters
            assigned_drones += town.assigned_harvesters
        return assigned_drones / ideal_drone_count

    # FIXME this seems bugged. Bot starts multiple expansions at the same time
    def should_build_hatchery(self):
        if self.global_drone_rate() >= EXPANSION_DRONE_THRESHOLD and len(self.expansions_sorted) > 0:
            if self.minerals >= HATCHERY_COST + (HATCHERY_COST_BUFFER_INCREMENT * len(self.townhalls)):
                return True
        return False

    def get_town_with_free_jobs(self, excluded=None):
        for town in self.townhalls:
            if town.assigned_harvesters < town.ideal_harvesters:
                if excluded is not None:
                    if town != excluded:
                        return town
                else:
                    return town
        return None

    def get_reassignable_drone(self, town):
        workers = self.workers.closer_than(10, town)
        for worker in workers:
            if len(worker.orders) == 1 and worker.orders[0].ability.id in {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN}:
                return worker
        return workers.random

    async def reassign_overideal_drones(self, old_town):
        if old_town.assigned_harvesters > old_town.ideal_harvesters:
            drone = self.get_reassignable_drone(old_town)
            new_town = self.get_town_with_free_jobs(old_town)
            if new_town and drone:
                self.log("Reassigning drone from overcrowded town", logging.DEBUG)
                mineral = self.get_closest_mineral_for_hatchery(new_town)
                await self.do_actions([drone.gather(mineral)])

    async def on_step(self, iteration):
        larvae = self.units(LARVA)
        overlords = self.units(OVERLORD)
        forces = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        actions = []
        if iteration == 0:
            self.set_expansion_order()
            self.set_hq_army_rally_point()
            actions.append(self.townhalls.first(RALLY_HATCHERY_UNITS, self.hq_army_rally_point))

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
        if self.units(ROACH).amount > 10 and iteration % 50 == 0:
            if len(forces.idle) > 0:
                self.log("Ordering {} forces to attack".format(len(forces.idle)), logging.DEBUG)
                for unit in forces.idle:
                    actions.append(unit.attack(self.select_target()))

        # Scout home base with overlords
        for idle_overlord in overlords.idle:
            patrol = self.start_location.random_on_distance(random.randrange(20, 30))
            actions.append(idle_overlord.move(patrol))

        # Set rally points for new hatcheries
        if iteration % 100 == 0:
            for hatch in self.units(HATCHERY).not_ready:
                self.log("Setting rally points for new hatchery", logging.DEBUG)
                actions.append(hatch(RALLY_HATCHERY_UNITS, self.hq_army_rally_point))
                actions.append(hatch(RALLY_HATCHERY_WORKERS, self.get_closest_mineral_for_hatchery(hatch)))
            await self.do_actions(actions)
            return

        # Training units
        for townhall in self.townhalls:
            await self.reassign_overideal_drones(townhall)
            town_larvae = larvae.closer_than(5, townhall)
            if town_larvae.exists:
                larva = town_larvae.random
                if self.should_train_overlord():
                    self.log("Training overlord", logging.DEBUG)
                    actions.append(larva.train(OVERLORD))
                    self.last_cap_covered = self.supply_cap
                elif self.should_train_drone(townhall):
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
        if self.should_build_hatchery():
            self.log("Building hatchery")
            # TODO Should not be so naive that sites are available and building will succeed and remain intact
            await self.build(HATCHERY, self.expansions_sorted.pop(0))
        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                self.log("Building spawning pool")
                await self.build(SPAWNINGPOOL, near=random_townhall)
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount < 1 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor #1")
                actions.append(drone.build(EXTRACTOR, target))
        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(LAIR).exists and random_townhall.noqueue:
                if self.can_afford(LAIR):
                    self.log("Building lair")
                    actions.append(random_townhall.build(LAIR))
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount > 0:
            if not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)):
                if self.can_afford(ROACHWARREN):
                    self.log("Building roach warren")
                    await self.build(ROACHWARREN, near=random_townhall)
        if self.units(ROACHWARREN).ready.exists and self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor #2")
                actions.append(drone.build(EXTRACTOR, target))

        if GLIALRECONSTITUTION not in self.state.upgrades and self.can_afford(GLIALRECONSTITUTION):
            if self.units(ROACHWARREN).ready.exists and self.units(LAIR).exists and self.units(ROACHWARREN).ready.noqueue:
                self.log("Upgrading roaches with Glial Reconstitution", logging.INFO)
                actions.append(self.units(ROACHWARREN).ready.first.research(GLIALRECONSTITUTION))

        # Rare, low-priority actions
        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                self.log("Queen creating larvae", logging.DEBUG)
                actions.append(queen(EFFECT_INJECTLARVA, self.townhalls.closest_to(queen.position)))

        for extractor in self.units(EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                worker = self.workers.closer_than(20, extractor)
                if worker.exists:
                    self.log("Assigning drone to extractor", logging.DEBUG)
                    actions.append(worker.random.gather(extractor))

        # Warnings
        if self.vespene > 1000 and iteration % 40 == 0:
            self.log("Too much gas", logging.WARNING)
        if self.supply_left == 0 and iteration % 40 == 0:
            self.log("Not enough overlords!", logging.WARNING)

        await self.do_actions(actions)

"""

# From point towards map center
near=cc.position.towards(self.game_info.map_center, 5)

# Distance between points
unit.position.to2.distance_to(depo.position.to2)

"""
