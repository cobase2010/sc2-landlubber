from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from bot.util import util

HATCHERY_COST = 300
HATCHERY_COST_BUFFER_INCREMENT = 25
EXPANSION_DRONE_THRESHOLD = 0.80
MAX_NUMBER_OF_DRONES = 70
DRONE_TRAINING_PROBABILITY_AT_EXPANSIONS = 90


def drone_rate_for_towns(townhalls):
    assigned_drones = 0
    ideal_drone_count = 0
    for town in townhalls:
        ideal_drone_count += town.ideal_harvesters
        assigned_drones += town.assigned_harvesters
    if ideal_drone_count == 0:  # If no jobs available, we should definitely expand
        return 1.0
    return assigned_drones / ideal_drone_count


def should_build_hatchery(bot):
    if not bot.townhalls.not_ready and not bot.units.find_by_tag(bot.active_expansion_builder):
        if len(bot.units(UnitTypeId.QUEEN)) >= len(bot.townhalls):
            if drone_rate_for_towns(bot.townhalls) >= EXPANSION_DRONE_THRESHOLD and len(bot.expansions_sorted) > 0:
                if bot.minerals >= HATCHERY_COST + (HATCHERY_COST_BUFFER_INCREMENT * (len(bot.townhalls) - 1)):
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


def get_expansion_order(logger, expansion_locations, start_location):
    exps = expansion_locations  # Fetching this property takes 1.6 seconds after which it is cached forever
    exps.pop(start_location)
    sorted = start_location.sort_by_distance(exps)
    if start_location in sorted:
        logger.error("Starting location unexpectedly still in expansion locations")
    return sorted


async def reassign_overideal_drones(bot):
    for old_town in bot.townhalls:
        if old_town.assigned_harvesters > old_town.ideal_harvesters:
            drone = get_reassignable_drone(old_town, bot.workers)
            new_town = get_town_with_free_jobs(bot.townhalls, old_town)
            if new_town and drone:
                bot.logger.debug("Reassigning drone from overcrowded town")
                mineral = get_closest_mineral_for_hatchery(bot.state.mineral_field(), new_town)
                await bot.do_actions([drone.gather(mineral)])


def get_reassignable_drone(town, workers):
    workers = workers.closer_than(10, town)
    for worker in workers:
        if len(worker.orders) == 1 and worker.orders[0].ability.id in {AbilityId.HARVEST_GATHER, AbilityId.HARVEST_RETURN}:
            return worker
    if workers:
        return workers.random
    else:
        return None


def should_train_drone(bot, townhall):
    if len(bot.units(UnitTypeId.DRONE)) < MAX_NUMBER_OF_DRONES:
        if townhall.assigned_harvesters < townhall.ideal_harvesters and bot.can_afford(UnitTypeId.DRONE):
            if len(bot.townhalls) == 1:
                probability = 100
            else:
                probability = DRONE_TRAINING_PROBABILITY_AT_EXPANSIONS
            return util.probability(probability)
    else:
        bot.logger.debug("Reached max number of drones")
        return False


def get_closest_mineral_for_hatchery(minerals, hatch):
    return minerals.closest_to(hatch.position)


def get_drone_actions(self):
    return assign_idle_drones_to_minerals(self) + assign_drones_to_extractors(self)


def assign_drones_to_extractors(bot):
    actions = []
    for extractor in bot.units(UnitTypeId.EXTRACTOR):
        if extractor.assigned_harvesters < extractor.ideal_harvesters:
            worker = bot.workers.closer_than(20, extractor)
            if worker.exists:
                bot.logger.debug("Assigning drone to extractor")
                actions.append(worker.random.gather(extractor))
    return actions


async def produce_larvae(bot):
    actions = []
    for queen in bot.units(UnitTypeId.QUEEN).idle:
        abilities = await bot.get_available_abilities(queen)
        if AbilityId.EFFECT_INJECTLARVA in abilities:
            bot.logger.debug("Queen creating larvae")
            actions.append(queen(AbilityId.EFFECT_INJECTLARVA, bot.townhalls.closest_to(queen.position)))
    return actions


def assign_idle_drones_to_minerals(bot):
    actions = []
    for drone in bot.units(UnitTypeId.DRONE).idle:
        new_town = get_town_with_free_jobs(bot.townhalls)
        if new_town:
            bot.logger.debug("Reassigning idle drone")
            mineral = get_closest_mineral_for_hatchery(bot.state.mineral_field(), new_town)
            actions.append(drone.gather(mineral))
    return actions


def set_hatchery_rally_points(bot):
    actions = []
    for hatch in bot.townhalls:
        actions.append(hatch(AbilityId.RALLY_HATCHERY_UNITS, bot.hq_front_door))
        if not hatch.is_ready:
            actions.append(hatch(AbilityId.RALLY_HATCHERY_WORKERS, get_closest_mineral_for_hatchery(bot.state.mineral_field(), hatch)))
    return actions
