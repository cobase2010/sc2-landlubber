from sc2.constants import *
import bot.economy as economy


async def build(bot, it):
    if not (bot.units(it).exists or bot.already_pending(it)) and bot.can_afford(it):
        bot.log(f"Building {it}")
        await bot.build(it, near=bot.townhalls.first)


# Build tree
async def begin_projects(bot):
    random_townhall = bot.townhalls.first

    if economy.should_build_hatchery(bot):
        bot.log("Building hatchery")
        drone = bot.workers.random
        bot.active_expansion_builder = drone.tag
        await bot.do_actions([drone.build(HATCHERY, bot.expansions_sorted.pop(0))]) # TODO Should not be so naive that sites are available and building will succeed and remain intact

    await build(bot, SPAWNINGPOOL)

    if bot.units(SPAWNINGPOOL).exists:
        if bot.units(EXTRACTOR).amount < 1 and not bot.already_pending(EXTRACTOR) and bot.can_afford(EXTRACTOR):
            bot.log("Building extractor #1")
            drone = bot.workers.random
            target = bot.state.vespene_geyser.closest_to(drone.position)
            await bot.do_actions([drone.build(EXTRACTOR, target)])
    if bot.units(SPAWNINGPOOL).ready.exists:
        if not (bot.units(LAIR).exists or bot.already_pending(LAIR)) and random_townhall.noqueue:
            if bot.can_afford(LAIR):
                bot.log("Building lair")
                await bot.do_actions([bot.townhalls.ready.first.build(LAIR)])

        await build(bot, ROACHWARREN)

    if bot.units(ROACHWARREN).ready.exists:
        if bot.units(EXTRACTOR).amount < 2 and not bot.already_pending(EXTRACTOR) and bot.can_afford(EXTRACTOR):
            bot.log("Building extractor #2")
            drone = bot.workers.random  # FIXME should be drone near hq, this sometimes picks the drone building expansion
            target = bot.state.vespene_geyser.closest_to(drone.position)
            await bot.do_actions([drone.build(EXTRACTOR, target)])

        if len(bot.townhalls) > 1:
            await build(bot, EVOLUTIONCHAMBER)
