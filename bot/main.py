import random
import logging
import sc2
import sys
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
log_format = logging.Formatter('%(levelname)-8s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(log_format)
logger.addHandler(handler)

LOOPS_PER_MIN = 22.4 * 60


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

    def set_hq_army_rally_point(self):
        # TODO set to ramp
        self.hq_army_rally_point = self.start_location.towards(self.game_info.map_center, 10)

    def get_closest_mineral_for_hatchery(self, hatch):
        print("Hatch position", hatch.position)
        res = self.state.mineral_field().closest_to(hatch.position)
        print(res)
        return res

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
        if self.units(OVERLORD).amount == 1:
            cap_safety_buffer = 0
        else:
            cap_safety_buffer = 2 * len(self.townhalls)
        should = self.supply_left <= cap_safety_buffer and self.supply_cap != self.last_cap_covered
        return should

    async def on_step(self, iteration):
        larvae = self.units(LARVA)
        overlords = self.units(OVERLORD)
        forces = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        actions = []
        if iteration == 0:
            self.set_expansion_order()
            self.set_hq_army_rally_point()
            actions.append(self.townhalls.first(RALLY_HATCHERY_UNITS, self.hq_army_rally_point))

        # Kamikaze if HQ lost
        if not self.townhalls.exists:
            if not self.hq_loss_handled:
                self.hq_loss_handled = True
                self.log("HQ lost, loss is probably imminent!", logging.WARNING)
                for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                    actions.append(unit.attack(self.enemy_start_locations[0]))
                await self.do_actions(actions)
            return
        else:
            hq = self.townhalls.first

        # if len(forces.idle) > 0:
        #     self.log("Move to ramp", logging.DEBUG)
        #     ramp = self.main_base_ramp.points
        #     print(len(ramp))
        #     for unit in forces.idle:
        #         actions.append(unit.move(ramp[0]))

        # Attack to enemy base
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
            town_larvae = larvae.closer_than(5, townhall)
            actions.append(townhall.move(self.enemy_start_locations[0])) # FIXME did not set waypoint
            if town_larvae.exists:
                larva = town_larvae.random
                if self.should_train_overlord():
                    if self.can_afford(OVERLORD):
                        self.log("Training overlord", logging.DEBUG)
                        actions.append(larva.train(OVERLORD))
                        self.last_cap_covered = self.supply_cap
                        await self.do_actions(actions)
                        return
                if townhall.assigned_harvesters < townhall.ideal_harvesters:
                    if self.can_afford(DRONE):
                        self.log("Training drone, current situation at this expansion {}/{}".format(townhall.assigned_harvesters, townhall.ideal_harvesters), logging.DEBUG)
                        actions.append(larva.train(DRONE))
                        await self.do_actions(actions)
                        return
                if self.units(ROACHWARREN).ready.exists:
                    if self.can_afford(ROACH) and larvae.exists:
                        actions.append(larva.train(ROACH))
                        self.log("Training roach", logging.DEBUG)
                        await self.do_actions(actions)
                        return
                if self.units(ZERGLING).amount < 20 and self.minerals > 1000:
                    if larvae.exists and self.can_afford(ZERGLING):
                        self.log("Training ling")
                        actions.append(larva.train(ZERGLING))

            # TODO make as many queens as there are townhalls
            if self.units(SPAWNINGPOOL).ready.exists:
                if not self.units(QUEEN).exists and hq.is_ready and hq.noqueue:
                    if self.can_afford(QUEEN):
                        self.log("Training queen", logging.DEBUG)
                        actions.append(hq.train(QUEEN))

        # Build tree
        if self.can_afford(HATCHERY):
            self.log("Building hatchery")
            # TODO Should not be so naive that sites are available and building will succeed and remain intact
            # FIXME error on pop on empty list
            await self.build(HATCHERY, self.expansions_sorted.pop(0))
        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                self.log("Building spawning pool")
                await self.build(SPAWNINGPOOL, near=hq)
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount < 1 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor #1")
                err = actions.append(drone.build(EXTRACTOR, target))
        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(LAIR).exists and hq.noqueue:
                if self.can_afford(LAIR):
                    self.log("Building lair")
                    actions.append(hq.build(LAIR))
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount > 0:
            if not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)):
                if self.can_afford(ROACHWARREN):
                    self.log("Building roach warren")
                    await self.build(ROACHWARREN, near=hq)
        if self.units(ROACHWARREN).ready.exists and self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor #2")
                err = actions.append(drone.build(EXTRACTOR, target))

        # Rare, low-priority actions
        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                self.log("Queen creating larvae", logging.DEBUG)
                actions.append(queen(EFFECT_INJECTLARVA, hq))
        for extractor in self.units(EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                worker = self.workers.closer_than(20, extractor)
                if worker.exists:
                    self.log("Assigning drone to extractor", logging.DEBUG)
                    actions.append(worker.random.gather(extractor))

        # Warnings
        if self.vespene > 600 and iteration % 20 == 0:
            self.log("Too much gas", logging.WARNING)
        if self.supply_left == 0 and iteration % 30 == 0:
            self.log("Not enough overlords!", logging.WARNING)
        if hq.assigned_harvesters > hq.ideal_harvesters and iteration % 20 == 0:
            self.log("Overassigned drones, should expand!", logging.WARNING)


        await self.do_actions(actions)

"""

# From point towards map center
near=cc.position.towards(self.game_info.map_center, 5)

# Distance between points
unit.position.to2.distance_to(depo.position.to2)

"""
