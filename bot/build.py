import logging
from sc2.constants import *
import bot.economy as economy


async def build_one(bot, it):
    if not (bot.units(it).exists or bot.already_pending(it)) and bot.can_afford(it):
        bot.log(f"Building {it}")
        await bot.build(it, near=bot.townhalls.first.position.towards(bot._game_info.map_center, 5))


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

def should_train_overlord(bot):
    if bot.can_afford(OVERLORD):
        if bot.units(OVERLORD).amount == 1:
            cap_safety_buffer = 0
        else:
            cap_safety_buffer = int((bot.townhalls.ready.amount + bot.units(QUEEN).ready.amount) * 0.45 + 2)
        should = bot.supply_left <= cap_safety_buffer and bot.supply_cap != bot.last_cap_covered and bot.supply_cap < 200
        return should

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
        await build_one(bot, ROACHWARREN)

    if bot.units(ROACHWARREN).ready.exists:
        if not (bot.units(LAIR).exists or bot.already_pending(LAIR)) and random_townhall.noqueue:
            if bot.can_afford(LAIR):
                bot.log("Building lair")
                await bot.do_actions([random_townhall.build(LAIR)])

        if len(bot.townhalls) > 1:
            await build_one(bot, EVOLUTIONCHAMBER)

    if bot.units(LAIR).ready.exists and len(bot.townhalls.ready) > 1:
        await build_one(bot, SPIRE)


# Training units
def train_units(bot, larvae):
    actions = []
    for townhall in bot.townhalls:
        town_larvae = larvae.closer_than(5, townhall)
        if town_larvae.exists:
            larva = town_larvae.random
            if should_train_overlord(bot):
                bot.log("Training overlord", logging.DEBUG)
                actions.append(larva.train(OVERLORD))
                bot.last_cap_covered = bot.supply_cap
            elif economy.should_train_drone(bot, townhall):
                bot.log("Training drone, current situation at this expansion {}/{}".format(townhall.assigned_harvesters, townhall.ideal_harvesters), logging.DEBUG)
                actions.append(larva.train(DRONE))
            else:
                if bot.can_afford(MUTALISK) and bot.units(SPIRE).ready.exists:
                    actions.append(larva.train(MUTALISK))
                    bot.log("Training mutalisk", logging.DEBUG)
                elif bot.units(ROACHWARREN).ready.exists:
                    if bot.can_afford(ROACH):
                        actions.append(larva.train(ROACH))
                        bot.log("Training roach", logging.DEBUG)
                elif bot.can_afford(ZERGLING) and bot.units(SPAWNINGPOOL).ready.exists:
                    bot.log("Training ling", logging.DEBUG)
                    actions.append(larva.train(ZERGLING))
        if bot.units(SPAWNINGPOOL).ready.exists and townhall.is_ready and townhall.noqueue:
            if bot.can_afford(QUEEN):
                if not bot.units(QUEEN).closer_than(15, townhall):
                    bot.log("Training queen", logging.INFO)
                    actions.append(townhall.train(QUEEN))
    return actions
