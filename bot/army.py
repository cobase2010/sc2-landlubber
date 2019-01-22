import random
from sc2.constants import *

ARMY_SIZE_BASE_LEVEL = 5
ARMY_SIZE_TIME_MULTIPLIER = 3
ARMY_SIZE_MAX = 180

def get_army_strength(units):
    single_food = units(ZERGLING).ready.amount
    double_food = units(ROACH).ready.amount
    return single_food + (2 * double_food)


def nearest_enemy_building(rally, enemy_structures, enemy_start_locations):
    if enemy_structures.exists:
        return enemy_structures.closest_to(rally).position
    return rally.closest(enemy_start_locations)


# Attack to enemy base
# TODO rally first near enemy base/expansion, and then attack with a larger force
def get_army_actions(iteration, forces, rally, enemy_structures, enemy_start_locations, units, time, supply_used):
    actions = []
    if iteration % 30 == 0:
        strength = get_army_strength(units)
        enough = (ARMY_SIZE_BASE_LEVEL + ((time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
        if strength >= enough or supply_used > ARMY_SIZE_MAX:
            for unit in forces:
                actions.append(unit.attack(nearest_enemy_building(rally, enemy_structures, enemy_start_locations)))
    return actions


# Scout home base with overlords
def patrol_with_overlords(overlords, rally, start_location):
    actions = []
    for overlord in overlords.idle:
        if len(overlords) < 4:
            patrol = rally.random_on_distance(random.randrange(1, 5))
        else:
            patrol = start_location.random_on_distance(random.randrange(20, 30))
        actions.append(overlord.move(patrol))
    return actions
