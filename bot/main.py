import random
import logging
import sc2
import sys
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.player import Bot, Computer
from sc2.data import race_townhalls

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.propagate = False
log_format = logging.Formatter('%(levelname)-8s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(log_format)
log.addHandler(handler)

LOOPS_PER_MIN = 22.4 * 60

class MyBot(sc2.BotAI):
    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position
        return self.enemy_start_locations[0]

    def on_start(self):
        self.last_cap_covered = 0
        log.info("Game started, gl hf!")

    def on_end(self, result):
        log.info("Game ended in " + str(result))

    def logg(self, msg):
        log.info("{:5.2f} {}".format(self.state.game_loop / LOOPS_PER_MIN, msg))

    async def on_step(self, iteration):
        larvae = self.units(LARVA)
        forces = self.units(ZERGLING) | self.units(ROACH) | self.units(HYDRALISK)
        actions = []

        # Kamikaze if HQ lost
        if not self.townhalls.exists:
            log.warning("HQ lost, kamikazeing!")
            for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                actions.append(unit.attack(self.enemy_start_locations[0]))
            await self.do_actions(actions)
            return
        else:
            hq = self.townhalls.first

        if self.minerals > 400:
            log.info("Too many minerals, building another hatchery")
            await self.build(HATCHERY, near=hq)
        if self.vespene > 1000 and iteration % 10 == 0:
            log.debug("Too much gas")
        if self.supply_left == 0 and iteration % 50 == 0:
            log.warn("Not enough overlords!")

        # Supply
        if self.supply_left < 3 and self.supply_cap != self.last_cap_covered:
            if self.can_afford(OVERLORD) and larvae.exists:
                self.logg("Training overlord")
                actions.append(larvae.random.train(OVERLORD))
                self.last_cap_covered = self.supply_cap
                await self.do_actions(actions)
                return

        # Train roach
        if self.units(ROACHWARREN).ready.exists:
            if self.can_afford(ROACH) and larvae.exists:
                log.debug("Training roach")
                # log.info(self.state.game_loop)
                actions.append(larvae.random.train(ROACH))
                await self.do_actions(actions)
                return

        # AGGRO
        if self.units(ROACH).amount > 15 and iteration % 50 == 0:
            log.debug("Ordering forces to attack")
            for unit in forces.idle:
                actions.append(unit.attack(self.select_target()))

        # More larvas
        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                log.debug("Queen creating larvae")
                actions.append(queen(EFFECT_INJECTLARVA, hq))

        # Build tree
        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                log.info("Building spawning pool")
                await self.build(SPAWNINGPOOL, near=hq)
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                log.info("Building extractor")
                err = actions.append(drone.build(EXTRACTOR, target))
        if self.units(SPAWNINGPOOL).ready.exists and self.units(EXTRACTOR).amount > 0:
            if not (self.units(ROACHWARREN).exists or self.already_pending(ROACHWARREN)):
                if self.can_afford(ROACHWARREN):
                    log.info("Building roach warren")
                    await self.build(ROACHWARREN, near=hq)

        # Collect resources
        if hq.assigned_harvesters < hq.ideal_harvesters:
            if self.can_afford(DRONE) and larvae.exists:
                larva = larvae.random
                log.debug("Training drone, currently assigned {}/{}".format(hq.assigned_harvesters, hq.ideal_harvesters))
                actions.append(larva.train(DRONE))
                await self.do_actions(actions)
                return
        for extractor in self.units(EXTRACTOR):
            if extractor.assigned_harvesters < extractor.ideal_harvesters:
                worker = self.workers.closer_than(20, extractor)
                if worker.exists:
                    log.debug("Assigning drone to extractor")
                    actions.append(worker.random.gather(extractor))

        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(QUEEN).exists and hq.is_ready and hq.noqueue:
                if self.can_afford(QUEEN):
                    log.info("Training queen")
                    actions.append(hq.train(QUEEN))

        if self.units(ZERGLING).amount < 20 and self.minerals > 1000:
            if larvae.exists and self.can_afford(ZERGLING):
                log.debug("Training ling")
                actions.append(larvae.random.train(ZERGLING))

        await self.do_actions(actions)
