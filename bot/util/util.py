import random
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Pointlike


def probability(percent):
    return random.randrange(100) < percent


def get_units_strength(bot, units):
    strength = 0
    for unit in units.filter(lambda u: u.can_attack_ground):
        if unit.type_id in [UnitTypeId.DRONE, UnitTypeId.SCV, UnitTypeId.PROBE]:
            strength += 10
        else:
            cost = bot._game_data.units[unit.type_id.value].cost
            strength += cost.minerals + cost.vespene
    return strength


def away_more(this: Pointlike, from_this: Pointlike, this_much_more: float):
    distance_total = from_this.distance_to(this) + this_much_more
    return from_this.towards(this, distance_total)
