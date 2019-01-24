import random
import logging
from sc2.constants import *

ARMY_SIZE_BASE_LEVEL = 5
ARMY_SIZE_TIME_MULTIPLIER = 3
ARMY_SIZE_MAX = 180

def get_army_strength(units):
    half_food = units(ZERGLING).ready.amount
    double_food = units(ROACH).ready.amount
    return (0.5 * half_food) + (2 * double_food)


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


def is_worker_rush(bot, town, enemies_approaching):
    enemies = enemies_approaching.closer_than(10, town)
    worker_enemies = enemies(DRONE) | enemies(PROBE) | enemies(SCV)
    if worker_enemies.amount > 1 and (worker_enemies.amount / enemies.amount) >= 0.8:
        return True
    return False


# Base defend
def base_defend(bot, forces):
    actions = []
    for town in bot.townhalls:
        enemies = bot.known_enemy_units.closer_than(20, town)
        if enemies:
            enemy = enemies.closest_to(town)
            defenders = forces.idle.closer_than(40, town)
            if defenders:
                bot.log(f"Defending our base with {defenders.amount} units against {enemies.amount} enemies", logging.INFO)
                for unit in defenders:
                    actions.append(unit.attack(enemy.position))  # Attack the position, not the unit, to avoid being lured
            else:
                bot.log(f"Enemy attacking our base with {enemies.amount} units but no defenders left!", logging.WARNING)

            if is_worker_rush(bot, town, enemies):
                bot.log("We are being worker rushed!", logging.WARNING)
                for drone in bot.units(DRONE).closer_than(60, town):
                    actions.append(drone.attack(enemy.position))

            if len(enemies) == 1:
                bot.log("Enemy is probably scouting our base", logging.DEBUG)

    return actions
