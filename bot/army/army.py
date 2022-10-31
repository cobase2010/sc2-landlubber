import random
import statistics
import time
# from sc2.helpers import ControlGroup
from sc2.ids.unit_typeid import UnitTypeId
from bot.util import util
from bot.opponent.strategy import Strategy

MAX_BASE_DOOR_RANGE = 30
ARMY_SIZE_BASE_LEVEL = 150
ARMY_SIZE_TIME_MULTIPLIER = 80
ARMY_SIZE_MAX = 180
ARMY_MAIN_FORCE_DISPERSION_MAX = 5
ARMY_MAIN_FORCE_RADIUS = 15

class ControlGroup(set):
    def __init__(self, units):
        super().__init__({unit.tag for unit in units})

    def __hash__(self):
        return hash(tuple(sorted(list(self))))

    def select_units(self, units):
        return units.filter(lambda unit: unit.tag in self)

    def missing_unit_tags(self, units):
        return {t for t in self if units.find_by_tag(t) is None}

    @property
    def amount(self) -> int:
        return len(self)

    @property
    def empty(self) -> bool:
        return self.amount == 0

    def add_unit(self, unit):
        self.add(unit.tag)

    def add_units(self, units):
        for unit in units:
            self.add_unit(unit)

    def remove_unit(self, unit):
        self.remove(unit.tag)

    def remove_units(self, units):
        for unit in units:
            self.remove(unit.tag)

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
        self.muta_flankers = ControlGroup([])
        self.base_defenders = ControlGroup([])

    def deferred_init(self):
        self.first_overlord_tag = self.bot.units(UnitTypeId.OVERLORD).first.tag

    def refresh(self):
        self.all_combat_units = self.bot.units(UnitTypeId.ZERGLING).ready | self.bot.units(UnitTypeId.ROACH).ready | self.bot.units(UnitTypeId.HYDRALISK).ready | self.bot.units(UnitTypeId.MUTALISK).ready
        self.strength = util.get_units_strength(self.bot, self.all_combat_units)
        """
        ControlGroup is actually just a set of unit tags. When units whose tag is added to a CG die, their tags remains in the CG. This is probably not
        a problem, but we could also cleanup the CGs by cycling tags into units and then back to tags. Not sure if worth it performance-wise.
        1) alive = self.bot.units.ready.tags_in(self.reserve)
        2) alive = self.reserve.select_units(self.all_combat_units)
        """

        # Add unassigned units to reserve
        unassigned = self.all_combat_units.tags_not_in(self.reserve | self.harassing_base_scouts | self.no_mans_expansions_scouts | self.muta_flankers | self.base_defenders)
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

        self._reinforce_from_reserve_if_empty(self.muta_flankers, UnitTypeId.MUTALISK, 10)
        self._reinforce_from_reserve_if_empty(self.harassing_base_scouts, UnitTypeId.ZERGLING, 1, True)
        if self.bot.time > 120:
            self._reinforce_from_reserve_if_empty(self.no_mans_expansions_scouts, UnitTypeId.ZERGLING, 1, True)

    def _reinforce_from_reserve_if_empty(self, group, unit_type, up_to=200, drone_fallback=False):
        survivors = group.select_units(self.bot.units)
        if not survivors:
            reserves = self.reserve.select_units(self.all_combat_units(unit_type)).take(up_to)
            for reserve in reserves:
                self.reserve.remove_unit(reserve)
                group.add_unit(reserve)
            if len(reserves) == 0 and drone_fallback:
                drones_available = self.bot.units(UnitTypeId.DRONE)  # TODO filter drones that have a special job
                if drones_available:
                    group.add_unit(drones_available.first)

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
            self.logger.warn("Base seems to have several ramps, scout will verify")
            return bot.start_location.towards(bot.game_info.map_center, 10)

    def _unit_dispersion(self, units):
        if units:
            center = units.center
            return statistics.median([unit.distance_to(center) for unit in units])
        else:
            return 0

    def get_seek_and_destroy_actions(self, units):
        # TODO sub-optimize by sending mutas to map corners
        actions = []
        for unit in units:
            if self.opponent.units:
                point = self.opponent.units.random.position.random_on_distance(random.randrange(5, 15))
            else:
                point = self.bot.map.get_random_point()
            actions.append(unit.attack(point))
        return actions

    def _large_enough_army(self, strength):
        enough = (ARMY_SIZE_BASE_LEVEL + ((self.bot.time / 60) * ARMY_SIZE_TIME_MULTIPLIER))
        if Strategy.PROXY in self.opponent.strategies:
            enough = 50
        return strength >= enough or self.bot.supply_used > ARMY_SIZE_MAX

    # Attack to enemy base
    def get_army_actions(self):
        bot = self.bot
        actions = []

        # TODO FIXME This should not manipulate reserve but only attack group
        units = self.reserve.select_units(bot.units)
        if units:
            bot.debugger.world_text("center", units.center)
            towards = None
            if self._large_enough_army(util.get_units_strength(bot, units)):

                towards = bot.opponent.get_next_potential_building_closest_to(bot.army_attack_point)
                if towards is None and Strategy.HIDDEN_BASE not in self.opponent.strategies:
                    self.logger.warn("Army does not know where to go, time to seek & destroy!")
                    self.opponent.strategies.add(Strategy.HIDDEN_BASE)
                elif towards and Strategy.HIDDEN_BASE in self.opponent.strategies:
                    self.logger.log("Found enemy from hiding!")
                    self.opponent.strategies.remove(Strategy.HIDDEN_BASE)

                if Strategy.HIDDEN_BASE in self.opponent.strategies:
                    return self.get_seek_and_destroy_actions(units.idle)

                if towards:
                    leader = units.closest_to(towards)
                    if leader:
                        bot.debugger.world_text("leader", leader.position)
                        main_pack = units.closer_than(ARMY_MAIN_FORCE_RADIUS, leader.position)
                        if main_pack.amount > 1:
                            bot.debugger.world_text("blob", main_pack.center)
                            dispersion = self._unit_dispersion(main_pack)
                            if dispersion < ARMY_MAIN_FORCE_DISPERSION_MAX: # Attack!
                                self.logger.debug(f"Tight main force advancing ({dispersion:.0f})")
                            else: # Regroup, too dispersed
                                self.logger.log(f"Main force is slightly dispersed ({dispersion:.0f})")
                                towards = leader.position
                        else:
                            self.logger.warning(f"Leader is too alone, pulling back!")
                            towards = units.center

            else: # Retreat, too weak!
                self.logger.debug(f"Army is too small, retreating!")
                towards = bot.hq_front_door

            bot.debugger.world_text("towards", towards)
            bot.army_attack_point = towards
            for unit in units:
                actions.append(unit.attack(bot.army_attack_point))

        return actions

    def flank(self):
        actions = []
        mutas = self.muta_flankers.select_units(self.bot.units).idle
        if mutas:
            for muta in mutas:
                actions.append(muta.move(self.bot.map.flanker_waypoint, queue=False))
                actions.append(muta.move(self.bot.map.opponent_corner, queue=True))
                actions.append(muta.attack(self.opponent.known_hq_location, queue=True))
                actions.append(muta.attack(self.opponent.known_natural, queue=True))
        return actions

    def scout_and_harass(self):
        actions = []
        scouts = self.harassing_base_scouts.select_units(self.bot.units)
        if scouts:
            for scout in scouts:
                # Harass workers
                if self.opponent.known_hq_location and scout.distance_to(self.opponent.known_hq_location) < 3:
                    worker_enemies = self.opponent.units(UnitTypeId.DRONE) | self.opponent.units(UnitTypeId.PROBE) | self.opponent.units(UnitTypeId.SCV)
                    if worker_enemies and not scout.is_attacking:
                        victim = worker_enemies.closest_to(scout.position)
                        actions.append(scout.attack(victim))
                else:
                    location = self.opponent.get_next_scoutable_location()
                    if location:
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
            if self.opponent.known_hq_location:
                exps.remove(self.opponent.known_hq_location)
            if self.opponent.known_natural:
                exps.remove(self.opponent.known_natural)
            for scout in scouts:
                self.logger.debug(f"Sending scout {scout} to no man's land")
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
            if Strategy.PROXY not in self.opponent.strategies:
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
                actions.append(early_warner.move(self.bot.start_location, queue=False))

        # Others will patrol around hq
        if len(overlords) < 4:
            patrol = self.bot.hq_front_door.random_on_distance(random.randrange(3, 8))
        else:
            patrol = self.bot.start_location.random_on_distance(40)
        for overlord in overlords.idle.tags_not_in([self.first_overlord_tag, self.early_warning_overlord_tag]):
            actions.append(overlord.move(patrol))
        return actions

    def is_worker_rush(self, town, enemies_approaching):
        enemies = enemies_approaching.closer_than(6, town)
        worker_enemies = enemies(UnitTypeId.DRONE) | enemies(UnitTypeId.PROBE) | enemies(UnitTypeId.SCV)
        if worker_enemies.amount > 1 and (worker_enemies.amount / enemies.amount) >= 0.8:
            return True
        return False

    def _get_enemies_that_should_be_evicted_from_base(self, town):
        enemies = self.opponent.units.closer_than(6, town).exclude_type(UnitTypeId.OVERLORD)
        if enemies:
            return enemies
        else:
            if self.opponent.structures:
                buildings = self.opponent.structures.closer_than(15, town)
                if buildings:
                    return buildings
        return None

    # Base defend
    def base_defend(self):
        actions = []
        for town in self.bot.townhalls:
            if self.opponent.units:
                enemies = self._get_enemies_that_should_be_evicted_from_base(town)
                if enemies and enemies.not_flying:  # Ground enemies are in this town
                    enemy = enemies.closest_to(town)

                    # Gather defenders
                    new_defenders = self.reserve.select_units(self.all_combat_units).idle.closer_than(30, town)
                    self.reserve.remove_units(new_defenders)
                    self.base_defenders.add_units(new_defenders)

                    armed_and_existing_defenders = self.base_defenders.select_units(self.bot.units)
                    if not armed_and_existing_defenders:
                        drones = self.bot.units(UnitTypeId.DRONE).closer_than(15, town)
                        if drones:
                            self.base_defenders.add_units(drones)
                            self.logger.log(f"Resorting to add {drones.amount} drones to defenders")

                    # TODO FIXME This will probably bug if several bases are under attack at the same time
                    all_defenders = self.base_defenders.select_units(self.bot.units)
                    if all_defenders:
                        self.logger.log(f"Defending our base against {enemies.amount} enemies with {all_defenders.amount} defenders: {all_defenders}")
                        for defender in all_defenders:
                            actions.append(defender.attack(enemy.position))

                    # if self.is_worker_rush(town, enemies) or Strategy.CANNON_RUSH in self.opponent.strategies:
                    #     self.logger.warn("We are being cheesed!")
                    #     for drone in bot.units(UnitTypeId.DRONE).closer_than(30, town):
                    #         actions.append(drone.attack(enemy.position))

                else:
                    if enemies and enemies.flying:
                        self.logger.warn("Enemies (not-overlords) flying in our base, not implemented!")

            # Base defenders back to work
            if self.base_defenders and not (self.opponent.units and self.opponent.units.closer_than(10, town).exclude_type(UnitTypeId.OVERLORD)):
                defenders = self.base_defenders.select_units(self.bot.units)
                self.logger.log(f"{defenders.amount} defenders calming down")
                for unit in defenders:
                    self.base_defenders.remove_unit(unit)
                    if unit.type_id == UnitTypeId.DRONE:
                        actions.append(unit.move(town.position))
                    else:
                        self.reserve.add_unit(unit)
                        actions.append(unit.move(self.bot.hq_front_door))

        return actions
