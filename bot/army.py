import random
import logging
from sc2.constants import *

ARMY_SIZE_BASE_LEVEL = 5
ARMY_SIZE_TIME_MULTIPLIER = 3
ARMY_SIZE_MAX = 180

ARMY_MOVEMENT_NEXT_MARCH_DISTANCE = 5
ARMY_MOVEMENT_REGROUP_RANGE = 15

def get_simple_army_strength(units):
    half_food = units(ZERGLING).ready.amount
    double_food = units(ROACH).ready.amount + units(MUTALISK).ready.amount
    return (0.5 * half_food) + (2 * double_food)


def nearest_enemy_building(rally, enemy_structures, enemy_start_locations):
    if enemy_structures.exists:
        return enemy_structures.closest_to(rally).position
    return rally.closest(enemy_start_locations)


def debug_army(bot, forces_idle):
    if forces_idle:
        army_distance = bot.hq_front_door.distance_to(forces_idle.center)
        marching_left = forces_idle.center.distance_to(bot.army_attack_point)
    else:
        army_distance = -100.0
        marching_left = -100.0
    print("{:4.1f} {:4.1f} {:4.1f} {:4.1f}".format(
        bot.hq_front_door.distance_to(bot.army_attack_point),
        bot.hq_front_door.distance_to(bot.army_spawn_rally_point),
        army_distance,
        marching_left
    ))


# Attack to enemy base
def get_army_actions(bot, iteration, forces_idle, enemy_structures, enemy_start_locations, units, time, supply_used):
    actions = []
    if iteration % 10 == 0:
        strength = get_simple_army_strength(units)
        enough = (ARMY_SIZE_BASE_LEVEL + ((time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
        towards = None
        if (strength >= enough or supply_used > ARMY_SIZE_MAX):
            if forces_idle and forces_idle.center.distance_to(bot.army_attack_point) < ARMY_MOVEMENT_REGROUP_RANGE:
                towards = nearest_enemy_building(
                    bot.army_attack_point,
                    enemy_structures,
                    enemy_start_locations)
        else:
            towards = bot.hq_front_door
        if towards:
            bot.army_attack_point = bot.army_attack_point.towards(towards, ARMY_MOVEMENT_NEXT_MARCH_DISTANCE)
            bot.army_spawn_rally_point = bot.army_attack_point.towards(bot.townhalls.first, 20)

    for unit in forces_idle:
        actions.append(unit.attack(bot.army_attack_point))

    debug_army(bot, forces_idle)

    return actions


# Scout home base with overlords
def patrol_with_overlords(overlords, front_door, start_location):
    actions = []
    for overlord in overlords.idle:
        if len(overlords) < 4:
            patrol = front_door.random_on_distance(random.randrange(1, 5))
        else:
            patrol = start_location.random_on_distance(random.randrange(20, 30))
        actions.append(overlord.move(patrol))
    return actions


def is_worker_rush(bot, town, enemies_approaching):
    enemies = enemies_approaching.closer_than(6, town)
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
