import time
import random
import statistics
from sc2.ids.unit_typeid import UnitTypeId
# from bot.debug import headless_render

MAX_BASE_DOOR_RANGE = 30
ARMY_SIZE_BASE_LEVEL = 4
ARMY_SIZE_TIME_MULTIPLIER = 2.8
ARMY_SIZE_MAX = 180
ARMY_DISPERSION_MAX = 15
ARMY_MAIN_FORCE_RADIUS = 25 # 15 yo-yos too much back and forth, 30 is almost slightly too string-like march.


class ArmyManager:
    def __init__(self, bot):
        self.bot = bot

    async def kamikaze(self, forces):
        bot = self.bot
        if not bot.hq_loss_handled:
            try:
                actions = []
                bot.hq_loss_handled = True
                bot.logger.warn("All townhalls lost, loss is probably imminent!")
                if bot.enemy_start_locations:
                    for unit in bot.units(UnitTypeId.DRONE) | bot.units(UnitTypeId.QUEEN) | forces:
                        actions.append(unit.attack(bot.enemy_start_locations[0]))
                    await bot.do_actions(actions)
            except Exception as e:
                print(e)


    def get_simple_army_strength(self, units):
        # TODO maybe this should be based on mineral+gas cost instead of food? Roach and muta require same food but different cost
        half_food = units(UnitTypeId.ZERGLING).ready.amount
        double_food = units(UnitTypeId.ROACH).ready.amount + units(UnitTypeId.MUTALISK).ready.amount
        return (0.5 * half_food) + (2 * double_food)

    def guess_front_door(self):
        bot = self.bot
        # Bot has main_base_ramp but it sometimes points to the back door ramp if base has multiple ramps
        bot.ramps_distance_sorted = sorted(bot._game_info.map_ramps, key=lambda ramp: ramp.top_center.distance_to(bot.start_location))
        doors = []
        for ramp in bot.ramps_distance_sorted:
            if ramp.top_center.distance_to(bot.start_location) <= MAX_BASE_DOOR_RANGE:
                doors.append(ramp)
        if len(doors) == 1:
            bot.logger.log("This base seems to have only one ramp")
            return doors[0].top_center
        else:
            bot.logger.warn("This base seems to several ramps, let's wait for scout to determine front door")
            return bot.start_location.towards(bot.game_info.map_center, 5)


    def enemy_is_building_on_our_side_of_the_map(self):
        bot = self.bot
        if bot.known_enemy_structures:
            range = bot.start_location.distance_to(bot._game_info.map_center)
            if bot.start_location.distance_to_closest(bot.known_enemy_structures) < range:
                return True
        return False


    def _unit_dispersion(self, units):
        if units:
            center = units.center
            return statistics.median([unit.distance_to(center) for unit in units])
        else:
            return 0


    # Attack to enemy base
    def get_army_actions(self, timer, units, enemy_structures, enemy_start_locations, all_units, game_time, supply_used):
        bot = self.bot
        actions = []
        if units and timer.rings:
            bot.debugger.world_text("center", units.center)
            strength = self.get_simple_army_strength(all_units) # TODO all_units or just idle?
            enough = (ARMY_SIZE_BASE_LEVEL + ((game_time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
            if self.enemy_is_building_on_our_side_of_the_map():
                bot.logger.warn("Enemy is building on our side of the map!")
                enough = ARMY_SIZE_BASE_LEVEL
            towards = None
            if (strength >= enough or supply_used > ARMY_SIZE_MAX):
                dispersion = self._unit_dispersion(units)

                if dispersion < ARMY_DISPERSION_MAX: # Attack!
                    bot.logger.debug(f"Tight army advancing ({dispersion:.0f})")
                    towards = bot.opponent.get_next_potential_base_closest_to(bot.army_attack_point)
                    if towards is None:
                        bot.logger.error("Don't know where to go!")
                        return []  # FIXME This prevents a crash on win, but we should start scouting for enemy

                else: # Regroup, too dispersed
                    main_force = units.closer_than(ARMY_MAIN_FORCE_RADIUS, units.center)
                    if main_force:
                        bot.logger.debug(f"Army is slightly dispersed ({dispersion:.0f})")
                        towards = main_force.center
                    else:
                        bot.logger.debug(f"Army is TOTALLY scattered")
                        towards = units.center

            else: # Retreat, too weak!
                bot.logger.debug(f"Army is too small, retreating!")
                towards = bot.hq_front_door

            bot.army_attack_point = towards
            bot.debugger.world_text("towards", towards)
            # headless.render_army(bot, all_units)
            for unit in units:
                actions.append(unit.attack(bot.army_attack_point))
        return actions


    # Scout home base with overlords
    def patrol_with_overlords(self, overlords, front_door, start_location, enemy_start_locations):
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


    def is_worker_rush(self, town, enemies_approaching):
        enemies = enemies_approaching.closer_than(6, town)
        worker_enemies = enemies(UnitTypeId.DRONE) | enemies(UnitTypeId.PROBE) | enemies(UnitTypeId.SCV)
        if worker_enemies.amount > 1 and (worker_enemies.amount / enemies.amount) >= 0.8:
            return True
        return False


    # Base defend
    def base_defend(self, forces):
        bot = self.bot
        actions = []
        for town in bot.townhalls:
            enemies = bot.known_enemy_units.closer_than(20, town)
            if enemies:
                enemy = enemies.closest_to(town)
                defenders = forces.idle.closer_than(40, town)
                if defenders:
                    bot.logger.debug(f"Defending our base with {defenders.amount} units against {enemies.amount} enemies")
                    for unit in defenders:
                        actions.append(unit.attack(enemy.position))  # Attack the position, not the unit, to avoid being lured
                else:
                    bot.logger.debug(f"Enemy attacking our base with {enemies.amount} units but no defenders left!")

                if self.is_worker_rush(town, enemies):
                    bot.logger.warn("We are being worker rushed!")
                    for drone in bot.units(UnitTypeId.DRONE).closer_than(60, town):
                        actions.append(drone.attack(enemy.position))

                if len(enemies) == 1:
                    bot.logger.debug("Enemy is probably scouting our base")

        return actions
