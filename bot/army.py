import random
import logging
from sc2.constants import *
# import bot.headless_render as headless

MAX_BASE_DOOR_RANGE = 30
ARMY_SIZE_BASE_LEVEL = 5
ARMY_SIZE_TIME_MULTIPLIER = 3
ARMY_SIZE_MAX = 180
ARMY_MOVEMENT_NEXT_MARCH_DISTANCE = 5
ARMY_MOVEMENT_REGROUP_RANGE = 15


async def kamikaze(bot, forces):
    if not bot.hq_loss_handled:
        try:
            actions = []
            bot.hq_loss_handled = True
            bot.log("All townhalls lost, loss is probably imminent!", logging.WARNING)
            if bot.enemy_start_locations:
                for unit in bot.units(DRONE) | bot.units(QUEEN) | forces:
                    actions.append(unit.attack(bot.enemy_start_locations[0]))
                await bot.do_actions(actions)
        except Exception as e:
            print(e)


def get_simple_army_strength(units):
    half_food = units(ZERGLING).ready.amount
    double_food = units(ROACH).ready.amount + units(MUTALISK).ready.amount
    return (0.5 * half_food) + (2 * double_food)


def nearest_enemy_building(rally, enemy_structures, enemy_start_locations):
    if enemy_structures.exists:
        return enemy_structures.closest_to(rally).position
    return rally.closest(enemy_start_locations)


def guess_front_door(bot):
    # Bot has main_base_ramp but it sometimes points to the back door ramp if base has multiple ramps
    bot.ramps_distance_sorted = sorted(bot._game_info.map_ramps, key=lambda ramp: ramp.top_center.distance_to(bot.start_location))
    doors = []
    for ramp in bot.ramps_distance_sorted:
        if ramp.top_center.distance_to(bot.start_location) <= MAX_BASE_DOOR_RANGE:
            doors.append(ramp)
    if len(doors) == 1:
        bot.log("This base seems to have only one ramp")
        return doors[0].top_center
    elif len(doors) == 2:
        bot.log("This base seems to have two ramps, let's make a guess and rally at the smaller one", logging.WARNING)
        if doors[0].size < doors[1].size:
            return doors[0].top_center
        else:
            return doors[1].top_center
    else:
        bot.log("This base seems to have many ramps, hard to tell where to rally", logging.ERROR)
        return bot.start_location.towards(bot.game_info.map_center, 10)

def enemy_is_building_on_our_side_of_the_map(bot):
    if bot.known_enemy_structures:
        range = bot.start_location.distance_to(bot._game_info.map_center)
        if bot.start_location.distance_to_closest(bot.known_enemy_structures) < range:
            return True
    return False

# Attack to enemy base
def get_army_actions(bot, iteration, forces_idle, enemy_structures, enemy_start_locations, units, time, supply_used):
    actions = []
    if iteration % 10 == 0:
        strength = get_simple_army_strength(units)
        enough = (ARMY_SIZE_BASE_LEVEL + ((time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
        if enemy_is_building_on_our_side_of_the_map(bot):
            bot.log("Enemy is building on our side of the map!", logging.WARNING)
            enough = ARMY_SIZE_BASE_LEVEL
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
        # headless.render_army(bot, forces_idle)

    for unit in forces_idle:
        actions.append(unit.attack(bot.army_attack_point))

    return actions


# Scout home base with overlords
def patrol_with_overlords(overlords, front_door, start_location, enemy_start_locations):
    actions = []
    for overlord in overlords.idle:
        if len(overlords) == 1:
            for enemy_loc in enemy_start_locations:
                actions.append(overlord.move(enemy_loc, queue=True))
            actions.append(overlord.move(start_location, queue=True))
            return actions
        elif len(overlords) < 4:
            patrol = front_door.random_on_distance(random.randrange(3, 6))
        else:
            patrol = start_location.random_on_distance(30)
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
