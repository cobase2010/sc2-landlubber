import logging
from sc2.constants import *

def upgrade_tech(bot):
    actions = []

    if GLIALRECONSTITUTION not in bot.state.upgrades and bot.can_afford(GLIALRECONSTITUTION):
        if bot.units(ROACHWARREN).ready.exists and bot.units(LAIR).exists and bot.units(ROACHWARREN).ready.noqueue:
            bot.log("Researching Glial Reconstitution for roaches", logging.INFO)
            actions.append(bot.units(ROACHWARREN).ready.first.research(GLIALRECONSTITUTION))

    idle_chambers = bot.units(EVOLUTIONCHAMBER).ready.noqueue
    if idle_chambers:
        if ZERGGROUNDARMORSLEVEL1 not in bot.state.upgrades:
            if bot.can_afford(ZERGGROUNDARMORSLEVEL1):
                bot.log("Researching ground armor 1", logging.INFO)
                actions.append(idle_chambers.first.research(ZERGGROUNDARMORSLEVEL1))
        elif ZERGGROUNDARMORSLEVEL2 not in bot.state.upgrades:
            if bot.can_afford(ZERGGROUNDARMORSLEVEL2) and bot.units(LAIR).exists:
                bot.log("Researching ground armor 2", logging.INFO)
                actions.append(idle_chambers.first.research(ZERGGROUNDARMORSLEVEL2))
        elif ZERGMISSILEWEAPONSLEVEL1 not in bot.state.upgrades:
            if bot.can_afford(ZERGMISSILEWEAPONSLEVEL1):
                bot.log("Researching ground missile weapons 1", logging.INFO)
                actions.append(idle_chambers.first.research(ZERGMISSILEWEAPONSLEVEL1))
        elif ZERGMISSILEWEAPONSLEVEL2 not in bot.state.upgrades:
            if bot.can_afford(ZERGMISSILEWEAPONSLEVEL2) and bot.units(LAIR).exists:
                bot.log("Researching ground missile weapons 2", logging.INFO)
                actions.append(idle_chambers.first.research(ZERGMISSILEWEAPONSLEVEL2))
    return actions
