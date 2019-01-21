import logging
from sc2.constants import *
import bot.util as util

HATCHERY_COST = 300
HATCHERY_COST_BUFFER_INCREMENT = 90
EXPANSION_DRONE_THRESHOLD = 0.90
MAX_NUMBER_OF_DRONES = 48
DRONE_TRAINING_PROBABILITY_AT_EXPANSIONS = 70


def global_drone_rate(townhalls):
    assigned_drones = 0
    ideal_drone_count = 0
    for town in townhalls:
        ideal_drone_count += town.ideal_harvesters
        assigned_drones += town.assigned_harvesters
    if ideal_drone_count == 0:  # If no jobs available, we should definitely expand
        return 1.0
    return assigned_drones / ideal_drone_count


def should_build_hatchery(townhalls, minerals, expansions_sorted):
    if not townhalls.not_ready:
        if global_drone_rate(townhalls) >= EXPANSION_DRONE_THRESHOLD and len(expansions_sorted) > 0:
            if minerals >= HATCHERY_COST + (HATCHERY_COST_BUFFER_INCREMENT * len(townhalls)):
                return True
    return False


def get_town_with_free_jobs(townhalls, excluded=None):
    for town in townhalls:
        if town.assigned_harvesters < town.ideal_harvesters:
            if excluded is not None:
                if town != excluded:
                    return town
            else:
                return town
    return None


def get_expansion_order(expansion_locations, start_location, enemy_start_locations, logger):
    exps = expansion_locations  # Fetching this property takes 1.6 seconds after which it is cached forever
    del exps[start_location]
    for enemy in enemy_start_locations:
        del exps[enemy]
    sorted = start_location.sort_by_distance(exps)
    if len(enemy_start_locations) != 1:
        logger.error("There are more than one enemy start location in this map! Assumptions might fail" + str(len(enemy_start_locations)))
    if start_location in sorted:
        logger.error("Starting location unexpectedly still in expansion locations")
    for enemy in enemy_start_locations:
        if enemy in sorted:
            logger.error("Enemy location unexpectedly still in expansion locations")
    return sorted


def get_reassignable_drone(town, workers):
    workers = workers.closer_than(10, town)
    for worker in workers:
        if len(worker.orders) == 1 and worker.orders[0].ability.id in {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN}:
            return worker
    return workers.random


def should_train_drone(bot, townhall):
    if len(bot.units(DRONE)) < MAX_NUMBER_OF_DRONES:
        if townhall.assigned_harvesters < townhall.ideal_harvesters and bot.can_afford(DRONE):
            if len(bot.townhalls) == 1:
                probability = 100
            else:
                probability = DRONE_TRAINING_PROBABILITY_AT_EXPANSIONS
            return util.probability(probability)
    else:
        bot.log("Reached max number of drones", logging.DEBUG)
        return False


def get_closest_mineral_for_hatchery(minerals, hatch):
    return minerals.closest_to(hatch.position)


def assign_drones_to_extractors(bot):
    actions = []
    for extractor in bot.units(EXTRACTOR):
        if extractor.assigned_harvesters < extractor.ideal_harvesters:
            worker = bot.workers.closer_than(20, extractor)
            if worker.exists:
                bot.log("Assigning drone to extractor", logging.DEBUG)
                actions.append(worker.random.gather(extractor))
    return actions


async def produce_larvae(bot):
    actions = []
    for queen in bot.units(QUEEN).idle:
        abilities = await bot.get_available_abilities(queen)
        if AbilityId.EFFECT_INJECTLARVA in abilities:
            bot.log("Queen creating larvae", logging.DEBUG)
            actions.append(queen(EFFECT_INJECTLARVA, bot.townhalls.closest_to(queen.position)))
    return actions


def assign_idle_drones_to_minerals(bot):
    actions = []
    for drone in bot.units(DRONE).idle:
        new_town = get_town_with_free_jobs(bot.townhalls)
        if new_town:
            bot.log("Reassigning idle drone", logging.DEBUG)
            mineral = get_closest_mineral_for_hatchery(bot.state.mineral_field(), new_town)
            actions.append(drone.gather(mineral))
    return actions
