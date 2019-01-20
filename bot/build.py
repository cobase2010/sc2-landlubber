from sc2.constants import *
import bot.economy as economy

# Build tree
async def build(bot):
    random_townhall = bot.townhalls.first

    if economy.should_build_hatchery(bot.townhalls, bot.minerals, bot.expansions_sorted):
        bot.log("Building hatchery")
        # TODO Should not be so naive that sites are available and building will succeed and remain intact
        await bot.build(HATCHERY, bot.expansions_sorted.pop(0))

    if not (bot.units(SPAWNINGPOOL).exists or bot.already_pending(SPAWNINGPOOL)):
        if bot.can_afford(SPAWNINGPOOL):
            bot.log("Building spawning pool")
            await bot.build(SPAWNINGPOOL, near=random_townhall)

    if bot.units(SPAWNINGPOOL).ready.exists:
        if bot.units(EXTRACTOR).amount < 1 and not bot.already_pending(EXTRACTOR) and bot.can_afford(EXTRACTOR):
            bot.log("Building extractor #1")
            drone = bot.workers.random
            target = bot.state.vespene_geyser.closest_to(drone.position)
            await bot.do_actions([drone.build(EXTRACTOR, target)])

        if not (bot.units(SPINECRAWLER).exists or bot.already_pending(SPINECRAWLER)) and bot.can_afford(SPINECRAWLER):
            bot.log("Building spine crawler")
            await bot.build(SPINECRAWLER, near=random_townhall)

        if not (bot.units(LAIR).exists or bot.already_pending(LAIR)) and random_townhall.noqueue:
            if bot.can_afford(LAIR):
                bot.log("Building lair")
                await bot.do_actions([bot.townhalls.ready.first.build(LAIR)])

        if not (bot.units(ROACHWARREN).exists or bot.already_pending(ROACHWARREN)) and bot.can_afford(ROACHWARREN):
            bot.log("Building roach warren")
            await bot.build(ROACHWARREN, near=random_townhall)

    if bot.units(ROACHWARREN).ready.exists:
        if bot.units(EXTRACTOR).amount < 2 and not bot.already_pending(EXTRACTOR) and bot.can_afford(EXTRACTOR):
            bot.log("Building extractor #2")
            drone = bot.workers.random  # FIXME should be drone near hq, this sometimes picks the drone building expansion
            target = bot.state.vespene_geyser.closest_to(drone.position)
            await bot.do_actions([drone.build(EXTRACTOR, target)])

        if not (bot.units(EVOLUTIONCHAMBER).exists or bot.already_pending(EVOLUTIONCHAMBER)) and bot.can_afford(EVOLUTIONCHAMBER):
            bot.log("Building evolution chamber")
            await bot.build(EVOLUTIONCHAMBER, near=random_townhall)
