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

        self.first_overlord_tag = None
        self.first_overlord_ordered = False
        self.early_warning_overlord_tag = None
        self.early_warning_overlord_ordered = False

        self.has_verified_front_door = False
        self.all_combat_units = None
        self.reserve = ControlGroup([])
        self.harassing_base_scouts = ControlGroup([])
        self.no_mans_expansions_scouts = ControlGroup([])

    def deferred_init(self):
        self.first_overlord_tag = self.bot.units(UnitTypeId.OVERLORD).first.tag

    def refresh(self):
        self.all_combat_units = self.bot.units(UnitTypeId.ZERGLING).ready | self.bot.units(UnitTypeId.ROACH).ready | self.bot.units(UnitTypeId.HYDRALISK).ready | self.bot.units(UnitTypeId.MUTALISK).ready
        """
        ControlGroup is actually just a set of unit tags. When units whose tag is added to a CG die, their tags remains in the CG. This is probably not
        a problem, but we could also cleanup the CGs by cycling tags into units and then back to tags. Not sure if worth it performance-wise.
        1) alive = self.bot.units.ready.tags_in(self.reserve)
        2) alive = self.reserve.select_units(self.all_combat_units)
        """

        # Add unassigned units to reserve
        unassigned = self.all_combat_units.tags_not_in(self.reserve | self.harassing_base_scouts | self.no_mans_expansions_scouts)
        if unassigned:
            self.reserve.add_units(unassigned)

        # Early warning lookout against proxy rax
        overlords = self.bot.units(UnitTypeId.OVERLORD)
        early_warning = overlords.find_by_tag(self.early_warning_overlord_tag)
        if not early_warning:
            volunteers = overlords.ready.tags_not_in([self.first_overlord_tag])
            if volunteers:
                self.early_warning_overlord_tag = volunteers.first.tag
                self.early_warning_overlord_ordered = False
                self.logger.log("Found new volunteer to become early warning lookout")

        # Assign base and expansion scouts from reserve or drones
        self._assign_scout_if_none(self.harassing_base_scouts)
        if self.bot.time > 120:
            self._assign_scout_if_none(self.no_mans_expansions_scouts)

    # Assign new scout from reserve or from drones
    def _assign_scout_if_none(self, group):
        scouts = group.select_units(self.bot.units)
        if not scouts:
            lings_in_reserve = self.reserve.select_units(self.all_combat_units(UnitTypeId.ZERGLING))
            if lings_in_reserve:
                ling = lings_in_reserve.first
                self.reserve.remove_unit(ling)
                group.add_unit(ling)
            else:
                drones_available = self.bot.units(UnitTypeId.DRONE)  # TODO filter drones that have a special job
                if drones_available:
                    drone = drones_available.first
                    group.add_unit(drone)

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

        # TODO FIXME This should not manipulate reserve but only attack group
        units = self.reserve.select_units(bot.units)
        if units:
            bot.debugger.world_text("center", units.center)
            strength = util.get_units_strength(bot, units)
            enough = (ARMY_SIZE_BASE_LEVEL + ((bot.time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
            if self.opponent.proxying:
                enough = ARMY_SIZE_BASE_LEVEL
            towards = None
            if (strength >= enough or bot.supply_used > ARMY_SIZE_MAX):
                dispersion = self._unit_dispersion(units)

                if dispersion < ARMY_DISPERSION_MAX: # Attack!
                    self.logger.debug(f"Tight army advancing ({dispersion:.0f})")
                    towards = bot.opponent.get_next_potential_building_closest_to(bot.army_attack_point)
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

    def scout_and_harass(self):
        actions = []
        scouts = self.harassing_base_scouts.select_units(self.bot.units)
        if scouts:
            location = self.opponent.get_next_scoutable_location()
            for scout in scouts:
                # Harass workers
                if self.opponent.known_hq_location and scout.distance_to(self.opponent.known_hq_location) < 3:
                    worker_enemies = self.opponent.units(UnitTypeId.DRONE) | self.opponent.units(UnitTypeId.PROBE) | self.opponent.units(UnitTypeId.SCV)
                    if worker_enemies and not scout.is_attacking:
                        victim = worker_enemies.closest_to(scout.position)
                        actions.append(scout.attack(victim))
                else:
                    actions.append(scout.move(location))
                # Kite
                if self.opponent.units:
                    enemies_closeby = self.opponent.units.filter(lambda unit: unit.can_attack_ground).closer_than(2, scout)
                    if enemies_closeby and scout.health_percentage < 0.4:
                        closest_enemy = enemies_closeby.closest_to(scout)
                        actions.append(scout.move(util.away(scout.position, closest_enemy.position, 4)))

                # Home base door verification
                if not self.has_verified_front_door:
                    for ramp in self.bot._game_info.map_ramps:
                        if scout.distance_to(ramp.top_center) < 6:
                            self.has_verified_front_door = True
                            self.bot.hq_front_door = ramp.top_center
                            self.logger.log("Scout verified front door")
        return actions

    def scout_no_mans_expansions(self):
        actions = []
        scouts = self.no_mans_expansions_scouts.select_units(self.bot.units)
        if scouts.idle:
            exps = list(self.bot.expansion_locations)
            exps.remove(self.opponent.known_hq_location)
            exps.remove(self.opponent.known_natural)
            for scout in scouts:
                self.logger.log(f"Sending scout {scout} to no man's land")
                actions.append(scout.move(self.bot.hq_front_door, queue=False))
                for exp in exps:
                    actions.append(scout.move(exp, queue=True))
        return actions

    # Scout home base with overlords
    def patrol_with_overlords(self):
        actions = []
        overlords = self.bot.units(UnitTypeId.OVERLORD)

        # First overlord will scout enemy natural
        firstborn = overlords.find_by_tag(self.first_overlord_tag)
        if firstborn and not self.first_overlord_ordered:
            if self.opponent.known_natural:
                near_enemy_front_door = self.opponent.known_natural.towards(self.opponent.known_hq_location, 4)
                safepoint_near_natural = util.away(self.opponent.known_natural, self.opponent.known_hq_location, 10)
                actions += [firstborn.move(near_enemy_front_door), firstborn.move(safepoint_near_natural, queue=True)]
            else:
                for enemy_loc in self.bot.enemy_start_locations:
                    actions.append(firstborn.move(enemy_loc, queue=True))
                actions.append(firstborn.move(self.bot.start_location, queue=True))
            self.first_overlord_ordered = True

        # Second overlord will scout proxy rax
        early_warner = overlords.find_by_tag(self.early_warning_overlord_tag)
        if early_warner:
            if not self.opponent.proxying:
                if not self.early_warning_overlord_ordered:
                    hq = self.bot.start_location
                    center = self.bot.game_info.map_center
                    dist_between_hq_and_center = hq.distance_to(center)
                    halfway = hq.towards(center, dist_between_hq_and_center * 0.7)
                    actions.append(early_warner.move(halfway, queue=False))
                    actions.append(early_warner.patrol(halfway.random_on_distance(5), queue=True))
                    actions.append(early_warner.patrol(halfway.random_on_distance(5), queue=True))
                    self.early_warning_overlord_ordered = True
            else:
                self.logger.warn("Enemy is proxy raxing, RTB with early warner!")
                actions.append(early_warner.move(self.bot.start_location, queue=False))

        # Others will patrol around hq
        if len(overlords) < 4:
            patrol = self.bot.hq_front_door.random_on_distance(random.randrange(3, 6))
        else:
            patrol = self.bot.start_location.random_on_distance(30)
        for overlord in overlords.idle.tags_not_in([self.first_overlord_tag, self.early_warning_overlord_tag]):
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
