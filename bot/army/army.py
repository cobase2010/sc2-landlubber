import random
import statistics
import time
from sc2.helpers import ControlGroup
from sc2.ids.unit_typeid import UnitTypeId
from bot.util import util

MAX_BASE_DOOR_RANGE = 30
ARMY_SIZE_BASE_LEVEL = 200
ARMY_SIZE_TIME_MULTIPLIER = 80
ARMY_SIZE_MAX = 180
ARMY_DISPERSION_MAX = 15
ARMY_MAIN_FORCE_RADIUS = 25 # 15 yo-yos too much back and forth, 30 is almost slightly too string-like march.


class ArmyManager:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.opponent = bot.opponent

        self.overlords = None
        self.active_scout_tag = None  # Legacy
        self.all_combat_units = None
        self.reserve = ControlGroup([])
        self.scouts = ControlGroup([])

    def refresh(self):
        self.all_combat_units = self.bot.units(UnitTypeId.ZERGLING).ready | self.bot.units(UnitTypeId.ROACH).ready | self.bot.units(UnitTypeId.HYDRALISK).ready | self.bot.units(UnitTypeId.MUTALISK).ready
        self.overlords = self.bot.units(UnitTypeId.OVERLORD)
        """
        ControlGroup is actually just a set of unit tags. When units whose tag is added to a CG die, their tags remains in the CG. This is probably not
        a problem, but we could also cleanup the CGs by cycling tags into units and then back to tags. Not sure if worth it performance-wise.
        1) alive = self.bot.units.ready.tags_in(self.reserve)
        2) alive = self.reserve.select_units(self.all_combat_units)
        """

        unassigned = self.all_combat_units.tags_not_in(self.reserve | self.scouts)
        if unassigned:
            self.reserve.add_units(unassigned)
        
    async def kamikaze(self):
        bot = self.bot
        if not bot.hq_loss_handled:
            try:
                actions = []
                bot.hq_loss_handled = True
                self.logger.warn("All townhalls lost, loss is probably imminent!")
                if bot.enemy_start_locations:
                    for unit in bot.units(UnitTypeId.DRONE) | bot.units(UnitTypeId.QUEEN) | self.all_combat_units:
                        actions.append(unit.attack(bot.enemy_start_locations[0]))
                    await bot.do_actions(actions)
            except Exception as e:
                print(e)

    def guess_front_door(self):
        bot = self.bot
        # Bot has main_base_ramp but it sometimes points to the back door ramp if base has multiple ramps
        bot.ramps_distance_sorted = sorted(bot._game_info.map_ramps, key=lambda ramp: ramp.top_center.distance_to(bot.start_location))
        doors = []
        for ramp in bot.ramps_distance_sorted:
            if ramp.top_center.distance_to(bot.start_location) <= MAX_BASE_DOOR_RANGE:
                doors.append(ramp)
        if len(doors) == 1:
            self.logger.log("This base seems to have only one ramp")
            return doors[0].top_center
        else:
            self.logger.warn("This base seems to several ramps, let's wait for scout to determine front door")
            return bot.start_location.towards(bot.game_info.map_center, 10)

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
    def get_army_actions(self):
        bot = self.bot
        actions = []
        units = self.all_combat_units  # TEMP
        if units:
            bot.debugger.world_text("center", units.center)
            strength = util.get_units_strength(bot, self.all_combat_units) # TODO all_units or just idle?
            enough = (ARMY_SIZE_BASE_LEVEL + ((bot.time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
            if self.enemy_is_building_on_our_side_of_the_map():
                self.logger.warn("Enemy is building on our side of the map!")
                enough = ARMY_SIZE_BASE_LEVEL
            towards = None
            if (strength >= enough or bot.supply_used > ARMY_SIZE_MAX):
                dispersion = self._unit_dispersion(units)

                if dispersion < ARMY_DISPERSION_MAX: # Attack!
                    self.logger.debug(f"Tight army advancing ({dispersion:.0f})")
                    towards = bot.opponent.get_next_potential_base_closest_to(bot.army_attack_point)
                    if towards is None:
                        self.logger.error("Don't know where to go!")
                        return []  # FIXME This prevents a crash on win, but we should start scouting for enemy

                else: # Regroup, too dispersed
                    main_force = units.closer_than(ARMY_MAIN_FORCE_RADIUS, units.center)
                    if main_force:
                        self.logger.debug(f"Army is slightly dispersed ({dispersion:.0f})")
                        towards = main_force.center
                    else:
                        self.logger.debug(f"Army is TOTALLY scattered")
                        towards = units.center

            else: # Retreat, too weak!
                self.logger.debug(f"Army is too small, retreating!")
                towards = bot.hq_front_door

            bot.army_attack_point = towards
            bot.debugger.world_text("towards", towards)
            for unit in units:
                actions.append(unit.attack(bot.army_attack_point))
        return actions

    def legacy_scouting(self):
        bot = self.bot
        actions = []
        scout = bot.units.find_by_tag(self.active_scout_tag)
        if not scout:
            if bot.units(UnitTypeId.ZERGLING).ready.exists:
                scout = bot.units(UnitTypeId.ZERGLING).ready.first
                self.active_scout_tag = scout.tag
                self.logger.log("Assigned a new zergling scout " + str(scout.tag))
            elif bot.units(UnitTypeId.ROACHWARREN).exists and bot.units(UnitTypeId.DRONE).ready.exists:
                scout = bot.units(UnitTypeId.DRONE).ready.random
                self.active_scout_tag = scout.tag
                self.logger.log("Assigned a new drone scout " + str(scout.tag))
        if scout:
            if scout.is_idle:
                if bot.opponent.unverified_hq_locations:
                    targets = bot.opponent.unverified_hq_locations
                else:
                    targets = bot.expansions_sorted
                for location in targets:
                    actions.append(scout.move(location, queue=True))
            else:
                if not bot.hq_scout_found_front_door:
                    for ramp in bot._game_info.map_ramps:
                        if scout.distance_to(ramp.top_center) < 5:
                            bot.hq_scout_found_front_door = True
                            bot.hq_front_door = ramp.top_center
                            self.logger.log("Scout verified front door")
        return actions

    # Scout home base with overlords
    def patrol_with_overlords(self):
        actions = []
        for overlord in self.overlords.idle:
            if len(self.overlords) == 1:
                for enemy_loc in self.bot.enemy_start_locations:
                    actions.append(overlord.move(enemy_loc, queue=True))
                actions.append(overlord.move(self.bot.start_location, queue=True))
                return actions
            elif len(self.overlords) < 4:
                patrol = self.bot.hq_front_door.random_on_distance(random.randrange(3, 6))
            else:
                patrol = self.bot.start_location.random_on_distance(30)
            actions.append(overlord.move(patrol))
        return actions

    def is_worker_rush(self, town, enemies_approaching):
        enemies = enemies_approaching.closer_than(6, town)
        worker_enemies = enemies(UnitTypeId.DRONE) | enemies(UnitTypeId.PROBE) | enemies(UnitTypeId.SCV)
        if worker_enemies.amount > 1 and (worker_enemies.amount / enemies.amount) >= 0.8:
            return True
        return False

    # Base defend
    def base_defend(self):
        bot = self.bot
        actions = []
        for town in bot.townhalls:
            enemies = bot.known_enemy_units.closer_than(20, town)
            if enemies:
                enemy = enemies.closest_to(town)
                defenders = self.all_combat_units.idle.closer_than(40, town)
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
