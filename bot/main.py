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


class MyBot(sc2.BotAI):
    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position
        return self.enemy_start_locations[0]

    def on_start(self):
        self.last_cap_covered = 0
        logger.info("Game started, gl hf!")

    def on_end(self, result):
        self.log("Game ended in " + str(result))

    def log(self, msg, level=logging.INFO):
        time_in_minutes = self.state.game_loop / LOOPS_PER_MIN
        cap_usage = "{}/{}".format(self.supply_used, self.supply_cap)
        logger.log(level, "{:4.1f} {:7} {}".format(time_in_minutes, cap_usage, msg))

    async def on_step(self, iteration):
        larvae = self.units(LARVA)
        forces = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        actions = []

        # Kamikaze if HQ lost
        if not self.townhalls.exists:
            self.log("HQ lost, kamikazeing!", logging.WARNING)
            for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                actions.append(unit.attack(self.enemy_start_locations[0]))
            await self.do_actions(actions)
            return
        else:
            hq = self.townhalls.first

        if self.minerals > 400:
            self.log("Too many minerals, building another hatchery")
            await self.build(HATCHERY, near=hq)
        if self.vespene > 1000 and iteration % 10 == 0:
            self.log("Too much gas", logging.WARNING)
        if self.supply_left == 0 and iteration % 50 == 0:
            self.log("Not enough overlords!", logging.WARNING)

        # Basic needs
        cap_buffer = 2 * len(self.townhalls)
        if self.supply_left < cap_buffer and self.supply_cap != self.last_cap_covered:
            if self.can_afford(OVERLORD) and larvae.exists:
                self.log("Training overlord, cap buffer required " + str(cap_buffer), logging.DEBUG)
                actions.append(larvae.random.train(OVERLORD))
                self.last_cap_covered = self.supply_cap
                await self.do_actions(actions)
                return
        else:
            if hq.assigned_harvesters < hq.ideal_harvesters:
                if self.can_afford(DRONE) and larvae.exists:
                    larva = larvae.random
                    self.log("Training drone, currently assigned {}/{}".format(hq.assigned_harvesters, hq.ideal_harvesters), logging.DEBUG)
                    actions.append(larva.train(DRONE))
                    await self.do_actions(actions)
                    return


        # Train roach
        if self.units(ROACHWARREN).ready.exists:
            if self.can_afford(ROACH) and larvae.exists:
                self.log("Training roach", logging.DEBUG)
                # log.info(self.state.game_loop)
                actions.append(larvae.random.train(ROACH))
                await self.do_actions(actions)
                return

        # AGGRO
        if self.units(ROACH).amount > 10 and iteration % 50 == 0:
            self.log("Ordering forces to attack", logging.DEBUG)
            for unit in forces.idle:
                actions.append(unit.attack(self.select_target()))

        # More larvas
        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                self.log("Queen creating larvae", logging.DEBUG)
                actions.append(queen(EFFECT_INJECTLARVA, hq))

        # Build tree
        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                self.log("Building spawning pool")
                await self.build(SPAWNINGPOOL, near=hq)
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                self.log("Building extractor")
                err = actions.append(drone.build(EXTRACTOR, target))
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount > 0:
            if not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)):
                if self.can_afford(ROACHWARREN):
                    self.log("Building roach warren")
                    await self.build(ROACHWARREN, near=hq)


        for extractor in self.units(EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                worker = self.workers.closer_than(20, extractor)
                if worker.exists:
                    self.log("Assigning drone to extractor", logging.DEBUG)
                    actions.append(worker.random.gather(extractor))

        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(QUEEN).exists and hq.is_ready and hq.noqueue:
                if self.can_afford(QUEEN):
                    self.log("Training queen", logging.DEBUG)
                    actions.append(hq.train(QUEEN))

        if self.units(ZERGLING).amount < 20 and self.minerals > 1000:
            if larvae.exists and self.can_afford(ZERGLING):
                self.log("Training ling")
                actions.append(larvae.random.train(ZERGLING))

        await self.do_actions(actions)
