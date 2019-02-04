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
        if not (bot.units(it).exists or bot.already_pending(it)) and bot.can_afford(it):
            self.logger.log(f"Building {it}")
            await bot.build(it, near=bot.townhalls.first.position.towards(bot._game_info.map_center, 5))

    async def _ensure_extractors(self):
        bot = self.bot
        if bot.units(UnitTypeId.EXTRACTOR).ready.amount > 0 and not bot.units(UnitTypeId.LAIR).ready.exists:
            return
        elif not bot.already_pending(UnitTypeId.EXTRACTOR):
                for town in bot.townhalls:
                    if town.is_ready and economy.drone_rate_for_towns([town]) >= 0.90:
                        for geyser in bot.state.vespene_geyser.closer_than(10, town):
                            if await bot.can_place(UnitTypeId.EXTRACTOR, geyser.position) and bot.can_afford(UnitTypeId.EXTRACTOR):
                                workers = bot.workers.gathering
                                if workers.exists:
                                    worker = workers.closest_to(geyser)
                                    self.logger.log("Building extractor")
                                    await bot.do_actions([worker.build(UnitTypeId.EXTRACTOR, geyser)])
                                    return

    def _should_train_overlord(self):
        bot = self.bot
        if bot.can_afford(UnitTypeId.OVERLORD):
            if bot.units(UnitTypeId.OVERLORD).amount == 1:
                required_buffer = 0
            else:
                required_buffer = int((bot.townhalls.ready.amount + bot.units(UnitTypeId.QUEEN).ready.amount) * 0.45 + 2)
            buffer = bot.supply_left + (bot.already_pending(UnitTypeId.OVERLORD) * 8)
            should = buffer <= required_buffer and bot.supply_cap < 200
            return should

    # Build tree
    async def begin_projects(self):
        bot = self.bot
        random_townhall = bot.townhalls.first
        strategy_penalty_multiplier = 1
        if self.opponent.strategy in [Strategy.PROXY]:
            strategy_penalty_multiplier = 1.8

        if economy.should_build_hatchery(bot):
            self.logger.log("Building hatchery")
            drone = bot.workers.random
            bot.active_expansion_builder = drone.tag
            await bot.do_actions([drone.build(UnitTypeId.HATCHERY, bot.expansions_sorted.pop(0))]) # TODO Should not be so naive that sites are available and building will succeed and remain intact

        await self._build_one(UnitTypeId.SPAWNINGPOOL)

        if bot.units(UnitTypeId.SPAWNINGPOOL).exists:
            await self._ensure_extractors()
        if bot.units(UnitTypeId.SPAWNINGPOOL).ready.exists:
            await self._build_one(UnitTypeId.ROACHWARREN)

        print(self.army.strength)

        if bot.units(UnitTypeId.ROACHWARREN).ready.exists and self.army.strength >= 600 * strategy_penalty_multiplier:
            if (not bot.units(UnitTypeId.LAIR).exists or bot.already_pending(UnitTypeId.LAIR)) and random_townhall.noqueue:
                if bot.can_afford(UnitTypeId.LAIR):
                    self.logger.log("Building lair")
                    await bot.do_actions([random_townhall.build(UnitTypeId.LAIR)])

            if bot.units(UnitTypeId.LAIR).ready.exists and len(bot.townhalls.ready) > 1 and self.army.strength >= 600 * strategy_penalty_multiplier:
                await self._build_one(UnitTypeId.EVOLUTIONCHAMBER)
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
                    self.logger.log("<-- Training overlord")
                    actions.append(larva.train(UnitTypeId.OVERLORD))
                elif economy.should_train_drone(bot, townhall):
                    self.logger.debug("Training drone, current situation at this expansion {}/{}".format(townhall.assigned_harvesters, townhall.ideal_harvesters))
                    actions.append(larva.train(UnitTypeId.DRONE))
                else:
                    if bot.can_afford(UnitTypeId.MUTALISK) and bot.units(UnitTypeId.SPIRE).ready.exists:
                        actions.append(larva.train(UnitTypeId.MUTALISK))
                        self.logger.debug("Training mutalisk")
                    elif bot.units(UnitTypeId.ROACHWARREN).ready.exists and bot.can_afford(UnitTypeId.ROACH):
                        actions.append(larva.train(UnitTypeId.ROACH))
                        self.logger.debug("Training roach")
                    elif bot.can_afford(UnitTypeId.ZERGLING) and bot.units(UnitTypeId.SPAWNINGPOOL).ready.exists:
                        self.logger.debug("Training ling")
                        actions.append(larva.train(UnitTypeId.ZERGLING))
            if bot.units(UnitTypeId.SPAWNINGPOOL).ready.exists and townhall.is_ready and townhall.noqueue:
                if bot.can_afford(UnitTypeId.QUEEN):
                    if not bot.units(UnitTypeId.QUEEN).closer_than(15, townhall):
                        self.logger.log("Training queen")
                        actions.append(townhall.train(UnitTypeId.QUEEN))
        return actions
