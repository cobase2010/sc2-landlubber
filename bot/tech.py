import logging
from sc2.constants import *

def get_upgrade_actions(bot):
    idle_chambers = bot.units(EVOLUTIONCHAMBER).ready.noqueue
    research_actions = []
    if idle_chambers:
        if ZERGGROUNDARMORSLEVEL1 not in bot.state.upgrades:
            if bot.can_afford(ZERGGROUNDARMORSLEVEL1):
                bot.log("Researching ground armor 1", logging.INFO)
                research_actions.append(idle_chambers.first.research(ZERGGROUNDARMORSLEVEL1))
        elif ZERGGROUNDARMORSLEVEL2 not in bot.state.upgrades:
            if bot.can_afford(ZERGGROUNDARMORSLEVEL2) and bot.units(LAIR).exists:
                bot.log("Researching ground armor 2", logging.INFO)
                research_actions.append(idle_chambers.first.research(ZERGGROUNDARMORSLEVEL2))
        elif ZERGMISSILEWEAPONSLEVEL1 not in bot.state.upgrades:
            if bot.can_afford(ZERGMISSILEWEAPONSLEVEL1):
                bot.log("Researching ground missile weapons 1", logging.INFO)
                research_actions.append(idle_chambers.first.research(ZERGMISSILEWEAPONSLEVEL1))
        elif ZERGMISSILEWEAPONSLEVEL2 not in bot.state.upgrades:
            if bot.can_afford(ZERGMISSILEWEAPONSLEVEL2) and bot.units(LAIR).exists:
                bot.log("Researching ground missile weapons 2", logging.INFO)
                research_actions.append(idle_chambers.first.research(ZERGMISSILEWEAPONSLEVEL2))
    return research_actions
