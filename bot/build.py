from sc2.constants import *
import bot.economy as economy


async def build_one(bot, it):
    if not (bot.units(it).exists or bot.already_pending(it)) and bot.can_afford(it):
        bot.log(f"Building {it}")
        await bot.build(it, near=bot.townhalls.first)


async def ensure_extractors(bot):
    if not bot.already_pending(EXTRACTOR):
        for town in bot.townhalls:
            if town.is_ready and economy.drone_rate_for_towns([town]) >= 0.90:
                for geyser in bot.state.vespene_geyser.closer_than(10, town):
                    if await bot.can_place(EXTRACTOR, geyser.position) and bot.can_afford(EXTRACTOR):
                        workers = bot.workers.gathering
                        if workers.exists:
                            worker = workers.closest_to(geyser)
                            bot.log("Building extractor")
                            await bot.do_actions([worker.build(EXTRACTOR, geyser)])
                            return


# Build tree
async def begin_projects(bot):
    random_townhall = bot.townhalls.first

    if economy.should_build_hatchery(bot):
        bot.log("Building hatchery")
        drone = bot.workers.random
        bot.active_expansion_builder = drone.tag
        await bot.do_actions([drone.build(HATCHERY, bot.expansions_sorted.pop(0))]) # TODO Should not be so naive that sites are available and building will succeed and remain intact

    await build_one(bot, SPAWNINGPOOL)

    if bot.units(SPAWNINGPOOL).exists:
        await ensure_extractors(bot)
    if bot.units(SPAWNINGPOOL).ready.exists:
        if not (bot.units(LAIR).exists or bot.already_pending(LAIR)) and random_townhall.noqueue:
            if bot.can_afford(LAIR):
                bot.log("Building lair")
                await bot.do_actions([bot.townhalls.ready.first.build(LAIR)])

        await build_one(bot, ROACHWARREN)

    if bot.units(ROACHWARREN).ready.exists:
        if len(bot.townhalls) > 1:
            await build_one(bot, EVOLUTIONCHAMBER)
