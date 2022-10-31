from sc2.ids.unit_typeid import UnitTypeId
from bot.economy import economy
from bot.opponent.strategy import Strategy
from bot.util import util


class Builder:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.opponent = bot.opponent
        self.army = bot.army

    async def _build_one(self, it):
        bot = self.bot
        if not (bot.structures(it).exists or bot.already_pending(it)) and bot.can_afford(it):
            self.logger.log(f"{bot.supply_used}: Building {it}")
            await bot.build(it, near=bot.townhalls.first.position.towards(bot._game_info.map_center, 5))

    async def _ensure_extractors(self):
        bot = self.bot
        if bot.structures(UnitTypeId.EXTRACTOR).ready.amount > 0 and not bot.structures(UnitTypeId.LAIR).ready.exists:
            return
        elif not bot.already_pending(UnitTypeId.EXTRACTOR):
                for town in bot.townhalls:
                    if town.is_ready and economy.drone_rate_for_towns([town]) >= 0.90:
                        for geyser in bot.vespene_geyser.closer_than(10, town):
                            can_we_place = await bot.can_place(UnitTypeId.EXTRACTOR, geyser.position)
                            if  can_we_place and bot.can_afford(UnitTypeId.EXTRACTOR):
                                workers = bot.workers.gathering
                                if workers.exists:
                                    worker = workers.closest_to(geyser)
                                    self.logger.log(f"{bot.supply_used}: Building extractor")
                                    worker.build(UnitTypeId.EXTRACTOR, geyser)
                                    # worker.build_gas(geyser)
                                    # await bot.do_actions([worker.build(UnitTypeId.EXTRACTOR, geyser)])
                                    return

    def _should_train_overlord(self):
        bot = self.bot
        if bot.can_afford(UnitTypeId.OVERLORD):
            if bot.units(UnitTypeId.OVERLORD).amount == 1:
                required_buffer = 0
            else:
                required_buffer = int((bot.townhalls.ready.amount + bot.units(UnitTypeId.QUEEN).ready.amount) * 0.7 + 2.5)
            buffer = bot.supply_left + (bot.already_pending(UnitTypeId.OVERLORD) * 8)
            should = buffer <= required_buffer and bot.supply_cap < 200
            return should

    # Build tree
    async def begin_projects(self):
        bot = self.bot
        random_townhall = bot.townhalls.first
        tech_penalty_multiplier = 1
        if {Strategy.PROXY} & self.opponent.strategies:
            tech_penalty_multiplier = 2

        if economy.should_build_hatchery(bot):
            self.logger.log(f"{bot.supply_used}: Building hatchery")
            drone = bot.workers.random
            bot.active_expansion_builder = drone.tag
            drone.build(UnitTypeId.HATCHERY, bot.expansions_sorted.pop(0))
            # await bot.do_actions([drone.build(UnitTypeId.HATCHERY, bot.expansions_sorted.pop(0))]) # TODO Should not be so naive that sites are available and building will succeed and remain intact

        if not economy.should_save_for_expansion(bot):
            await self._build_one(UnitTypeId.SPAWNINGPOOL)

            if bot.structures(UnitTypeId.SPAWNINGPOOL).exists:
                await self._ensure_extractors()
            if bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists:
                await self._build_one(UnitTypeId.ROACHWARREN)

            if bot.structures(UnitTypeId.ROACHWARREN).ready.exists and self.army.strength >= 500 * tech_penalty_multiplier:
                if (not bot.structures(UnitTypeId.LAIR).exists or bot.already_pending(UnitTypeId.LAIR)) and random_townhall.is_idle:
                    if bot.can_afford(UnitTypeId.LAIR):
                        self.logger.log(f"{bot.supply_used}: Building lair")
                        random_townhall.build(UnitTypeId.LAIR)
                        # await bot.do_actions([random_townhall.build(UnitTypeId.LAIR)])

                if bot.structures(UnitTypeId.LAIR).ready.exists and len(bot.townhalls.ready) > 1 and self.army.strength >= 500 * tech_penalty_multiplier:
                    await self._build_one(UnitTypeId.EVOLUTIONCHAMBER)
                    # await self._build_one(UnitTypeId.HYDRALISKDEN)
                    await self._build_one(UnitTypeId.SPIRE)

    # Training units
    def train_units(self):
        bot = self.bot
        actions = []
        for townhall in bot.townhalls:
            town_larvae = bot.units(UnitTypeId.LARVA).closer_than(5, townhall)
            if town_larvae.exists:
                larva = town_larvae.random
                if self._should_train_overlord():
                    self.logger.log(f"{bot.supply_used}:  overlord")
                    # actions.append(larva.train(UnitTypeId.OVERLORD))
                    larva.train(UnitTypeId.OVERLORD)
                elif economy.should_train_drone(bot, townhall):
                    self.logger.debug(f"{bot.supply_used}: Training drone, current situation at this expansion {townhall.assigned_harvesters}/{townhall.ideal_harvesters}")
                    # actions.append(larva.train(UnitTypeId.DRONE))
                    if bot.can_afford(UnitTypeId.DRONE):
                        larva.train(UnitTypeId.DRONE)
                    
                elif not economy.should_save_for_expansion(bot):
                    if bot.can_afford(UnitTypeId.MUTALISK) and bot.structures(UnitTypeId.SPIRE).ready:
                        self.logger.debug(f"{bot.supply_used}: Training mutalisk")
                        if bot.can_afford(UnitTypeId.MUTALISK):
                            _amount_trained: int = bot.train(UnitTypeId.MUTALISK, 1)
                        # actions.append(larva.train(UnitTypeId.MUTALISK))
                    # if bot.can_afford(UnitTypeId.HYDRALISK) and bot.units(UnitTypeId.HYDRALISKDEN).ready.exists:
                    #     self.logger.debug("Training hydralisk")
                    #     actions.append(larva.train(UnitTypeId.HYDRALISK))
                    elif bot.structures(UnitTypeId.ROACHWARREN).ready:
                #         print("can afford roach", bot.can_afford(UnitTypeId.ROACH))
                #         print(f"n_workers: {bot.workers.amount}, n_idle_workers: {bot.workers.idle.amount},", \
                # f"minerals: {bot.minerals}, gas: {bot.vespene}, supply: {bot.supply_used}/{bot.supply_cap},", \
                # f"extractors: {bot.structures(UnitTypeId.EXTRACTOR).amount},", \
                # f"roachwarren: {bot.structures(UnitTypeId.ROACHWARREN).amount}, spires: {bot.structures(UnitTypeId.SPIRE).amount}", \
                # f"zerg: {bot.units(UnitTypeId.ZERGLING).amount}, roach: {bot.units(UnitTypeId.ROACH).amount}", )
            

                        if bot.can_afford(UnitTypeId.ROACH):
                            self.logger.info(f"{bot.supply_used}: Training roach")
                            # actions.append(larva.train(UnitTypeId.ROACH))
                            _amount_trained: int = bot.train(UnitTypeId.ROACH, 1)
                        elif bot.minerals > 400 and bot.units(UnitTypeId.LARVA).amount > 5:
                            self.logger.info(f"{bot.supply_used}: Training late ling because excessive minerals")
                            # actions.append(larva.train(UnitTypeId.ZERGLING))
                            if bot.can_afford(UnitTypeId.ZERGLING):
                                _amount_trained: int = bot.train(UnitTypeId.ZERGLING, 1)
                    elif bot.can_afford(UnitTypeId.ZERGLING) and bot.structures(UnitTypeId.SPAWNINGPOOL).ready:
                        self.logger.info(f"{bot.supply_used}: Training ling")
                        # actions.append(larva.train(UnitTypeId.ZERGLING))
                        amount_trained: int = bot.train(UnitTypeId.ZERGLING, 1)
            if bot.structures(UnitTypeId.SPAWNINGPOOL).ready.exists and townhall.is_ready and townhall.is_idle:
                if bot.can_afford(UnitTypeId.QUEEN):
                    if not bot.units(UnitTypeId.QUEEN).closer_than(15, townhall):
                        self.logger.info(f"{bot.supply_used}: Training queen")
                        # actions.append(townhall.train(UnitTypeId.QUEEN))
                        amount_trained: int = townhall.train(UnitTypeId.QUEEN)
        return actions
