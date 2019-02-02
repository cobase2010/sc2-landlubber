from bot.economy import economy
from sc2.ids.unit_typeid import UnitTypeId


async def build_one(bot, it):
    if not (bot.units(it).exists or bot.already_pending(it)) and bot.can_afford(it):
        bot.logger.log(f"Building {it}")
        await bot.build(it, near=bot.townhalls.first.position.towards(bot._game_info.map_center, 5))


async def ensure_extractors(bot):
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
                                bot.logger.log("Building extractor")
                                await bot.do_actions([worker.build(UnitTypeId.EXTRACTOR, geyser)])
                                return

def should_train_overlord(bot):
    if bot.can_afford(UnitTypeId.OVERLORD):
        if bot.units(UnitTypeId.OVERLORD).amount == 1:
            required_buffer = 0
        else:
            required_buffer = int((bot.townhalls.ready.amount + bot.units(UnitTypeId.QUEEN).ready.amount) * 0.45 + 2)
        buffer = bot.supply_left + (bot.already_pending(UnitTypeId.OVERLORD) * 8)
        should = buffer <= required_buffer and bot.supply_cap < 200
        return should


# Build tree
async def begin_projects(bot):
    random_townhall = bot.townhalls.first

    if economy.should_build_hatchery(bot):
        bot.logger.log("Building hatchery")
        drone = bot.workers.random
        bot.active_expansion_builder = drone.tag
        await bot.do_actions([drone.build(UnitTypeId.HATCHERY, bot.expansions_sorted.pop(0))]) # TODO Should not be so naive that sites are available and building will succeed and remain intact

    await build_one(bot, UnitTypeId.SPAWNINGPOOL)

    if bot.units(UnitTypeId.SPAWNINGPOOL).exists:
        await ensure_extractors(bot)
    if bot.units(UnitTypeId.SPAWNINGPOOL).ready.exists:
        await build_one(bot, UnitTypeId.ROACHWARREN)

    if bot.units(UnitTypeId.ROACHWARREN).ready.exists:
        if (not bot.units(UnitTypeId.LAIR).exists or bot.already_pending(UnitTypeId.LAIR)) and random_townhall.noqueue:
            if bot.can_afford(UnitTypeId.LAIR):
                bot.logger.log("Building lair")
                await bot.do_actions([random_townhall.build(UnitTypeId.LAIR)])

    if bot.units(UnitTypeId.LAIR).ready.exists and len(bot.townhalls.ready) > 1:
        await build_one(bot, UnitTypeId.EVOLUTIONCHAMBER)
        await build_one(bot, UnitTypeId.SPIRE)


# Training units
def train_units(bot, larvae):
    actions = []
    for townhall in bot.townhalls:
        town_larvae = larvae.closer_than(5, townhall)
        if town_larvae.exists:
            larva = town_larvae.random
            if should_train_overlord(bot):
                bot.logger.log("<-- Training overlord")
                actions.append(larva.train(UnitTypeId.OVERLORD))
            elif economy.should_train_drone(bot, townhall):
                bot.logger.debug("Training drone, current situation at this expansion {}/{}".format(townhall.assigned_harvesters, townhall.ideal_harvesters))
                actions.append(larva.train(UnitTypeId.DRONE))
            else:
                if bot.can_afford(UnitTypeId.MUTALISK) and bot.units(UnitTypeId.SPIRE).ready.exists:
                    actions.append(larva.train(UnitTypeId.MUTALISK))
                    bot.logger.debug("Training mutalisk")
                elif bot.units(UnitTypeId.ROACHWARREN).ready.exists:
                    if bot.can_afford(UnitTypeId.ROACH):
                        actions.append(larva.train(UnitTypeId.ROACH))
                        bot.logger.debug("Training roach")
                elif bot.can_afford(UnitTypeId.ZERGLING) and bot.units(UnitTypeId.SPAWNINGPOOL).ready.exists:
                    bot.logger.debug("Training ling")
                    actions.append(larva.train(UnitTypeId.ZERGLING))
        if bot.units(UnitTypeId.SPAWNINGPOOL).ready.exists and townhall.is_ready and townhall.noqueue:
            if bot.can_afford(UnitTypeId.QUEEN):
                if not bot.units(UnitTypeId.QUEEN).closer_than(15, townhall):
                    bot.logger.log("Training queen")
                    actions.append(townhall.train(UnitTypeId.QUEEN))
    return actions
