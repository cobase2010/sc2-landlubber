import random
from sc2.ids.unit_typeid import UnitTypeId


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
    print(strength)
    return strength
