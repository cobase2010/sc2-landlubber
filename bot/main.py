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
log_format = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(log_format)
log.addHandler(handler)


class MyBot(sc2.BotAI):
    def select_target(self):
        if self.known_enemy_structures.exists:
            return random.choice(self.known_enemy_structures).position
        return self.enemy_start_locations[0]

    def on_start(self):
        log.info("Game started, gl hf!")

    def on_end(self, result):
        log.info("Game ended in " + str(result))

    async def on_step(self, iteration):
        larvae = self.units(LARVA)
        forces = self.units(ZERGLING) | self.units(HYDRALISK)
        actions = []

        if self.units(HYDRALISK).amount > 10 and iteration % 50 == 0:
            for unit in forces.idle:
                actions.append(unit.attack(self.select_target()))

        if self.supply_left < 2:
            if self.can_afford(OVERLORD) and larvae.exists:
                log.info("Training overlord")
                actions.append(larvae.random.train(OVERLORD))
                await self.do_actions(actions)
                return

        if self.units(HYDRALISKDEN).ready.exists:
            if self.can_afford(HYDRALISK) and larvae.exists:
                log.debug("Training hydra")
                actions.append(larvae.random.train(HYDRALISK))
                await self.do_actions(actions)
                return

        if not self.townhalls.exists:
            for unit in self.units(DRONE) | self.units(QUEEN) | forces:
                actions.append(unit.attack(self.enemy_start_locations[0]))
            await self.do_actions(actions)
            return
        else:
            hq = self.townhalls.first

        for queen in self.units(QUEEN).idle:
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                log.info("Queen creating larvae")
                actions.append(queen(EFFECT_INJECTLARVA, hq))

        if not (self.units(SPAWNINGPOOL).exists or self.already_pending(SPAWNINGPOOL)):
            if self.can_afford(SPAWNINGPOOL):
                log.info("Building spawning pool")
                await self.build(SPAWNINGPOOL, near=hq)

        if self.units(SPAWNINGPOOL).ready.exists:
            if not self.units(LAIR).exists and hq.noqueue:
                if self.can_afford(LAIR):
                    log.info("Building lair")
                    actions.append(hq.build(LAIR))

        if self.units(LAIR).ready.exists:
            if not (self.units(HYDRALISKDEN).exists or self.already_pending(HYDRALISKDEN)):
                if self.can_afford(HYDRALISKDEN):
                    log.info("Building hydra den")
                    await self.build(HYDRALISKDEN, near=hq)

        if self.units(EXTRACTOR).amount < 2 and not self.already_pending(EXTRACTOR):
            if self.can_afford(EXTRACTOR):
                drone = self.workers.random
                target = self.state.vespene_geyser.closest_to(drone.position)
                log.info("Building extractor")
                err = actions.append(drone.build(EXTRACTOR, target))

        if hq.assigned_harvesters < hq.ideal_harvesters:
            if self.can_afford(DRONE) and larvae.exists:
                larva = larvae.random
                actions.append(larva.train(DRONE))
                await self.do_actions(actions)
                return

        for a in self.units(EXTRACTOR):
            if a.assigned_harvesters < a.ideal_harvesters:
                w = self.workers.closer_than(20, a)
                if w.exists:
                    actions.append(w.random.gather(a))

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
