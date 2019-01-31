import logging
from sc2.constants import *


def can_research(bot, tech):
    if tech not in bot.state.upgrades and bot.can_afford(tech):
        if tech in [ZERGGROUNDARMORSLEVEL2, ZERGMISSILEWEAPONSLEVEL2, ZERGFLYERWEAPONSLEVEL2, ZERGFLYERARMORSLEVEL2]:
            if bot.units(LAIR).exists:
                return True
        elif tech in [ZERGGROUNDARMORSLEVEL3, ZERGMISSILEWEAPONSLEVEL3, ZERGFLYERWEAPONSLEVEL3, ZERGFLYERARMORSLEVEL3]:
            if bot.units(HIVE).exists:
                return True
        else:
            return True
    return False


def get_tech_to_research(bot, techs):
    for tech in techs:
        if can_research(bot, tech):
            return tech
    return None


def upgrade_tech(bot):
    if GLIALRECONSTITUTION not in bot.state.upgrades and bot.can_afford(GLIALRECONSTITUTION):
        if bot.units(ROACHWARREN).ready.exists and bot.units(LAIR).exists and bot.units(ROACHWARREN).ready.noqueue:
            bot.log("Researching Glial Reconstitution for roaches", logging.INFO)
            return [bot.units(ROACHWARREN).ready.first.research(GLIALRECONSTITUTION)]

    idle_chambers = bot.units(EVOLUTIONCHAMBER).ready.noqueue
    if idle_chambers:
        research_order = [
            ZERGGROUNDARMORSLEVEL1,
            ZERGGROUNDARMORSLEVEL2,
            ZERGMISSILEWEAPONSLEVEL1,
            ZERGMISSILEWEAPONSLEVEL2,
            ZERGGROUNDARMORSLEVEL3,
            ZERGMISSILEWEAPONSLEVEL3
        ]
        tech = get_tech_to_research(bot, research_order)
        if tech:
            bot.log(f"Researching {tech}", logging.INFO)
            return [idle_chambers.first.research(tech)]

    idle_spire = bot.units(SPIRE).ready.noqueue
    if idle_spire:
        research_order = [
            ZERGFLYERWEAPONSLEVEL1,
            ZERGFLYERWEAPONSLEVEL2,
            ZERGFLYERARMORSLEVEL1,
            ZERGFLYERARMORSLEVEL2,
            ZERGFLYERWEAPONSLEVEL3,
            ZERGFLYERARMORSLEVEL3
        ]
        tech = get_tech_to_research(bot, research_order)
        if tech:
            bot.log(f"Researching {tech}", logging.INFO)
            return [idle_spire.first.research(tech)]

    return []
