from sc2 import Race, Difficulty
from sc2.ids.unit_typeid import UnitTypeId
from bot.opponent.strategy import Strategy


class Opponent:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger

        self.known_race = None
        self.known_hq_location = None
        self.known_natural = None
        self.unverified_hq_locations = bot.enemy_start_locations
        self.next_potential_location = None
        self.army_strength = 0
        self.units = None
        self.structures = None
        self.strategies = set()
        self.too_close_distance = 0

        if bot.enemy_race != Race.Random:
            self._set_race(bot.enemy_race)

    def _set_enemy_hq_and_natural(self, pos):
        self.known_hq_location = pos
        self.logger.log(f"Found enemy base {pos}")
        locs = list(self.bot.expansion_locations)
        locs.remove(pos)
        self.known_natural = pos.closest(locs)
        self.logger.log(f"Enemy natural {self.known_natural}")

    def _set_race(self, race):
        self.logger.log("Enemy is now known to be " + str(race))
        self.known_race = race

    def deferred_init(self):
        if len(self.bot.enemy_start_locations) == 1:
            self.logger.log("We know exactly where our enemy HQ is")
            self._set_enemy_hq_and_natural(self.bot.enemy_start_locations[0])
            self.unverified_hq_locations = []
            self.too_close_distance = self.bot.start_location.distance_to(self.bot._game_info.map_center)

    def refresh(self):
        if self.bot.known_enemy_units:
            self.units = self.bot.known_enemy_units
            if self.known_race is None:
                self._set_race(self.units.first.race)
        else:
            self.units = None

        if self.bot.known_enemy_structures:
            self.structures = self.bot.known_enemy_structures
            self.check_rush()
            self.check_cannon_rush()
        else:
            self.structures = None
        self.check_proxy()

        if self.unverified_hq_locations:
            for i, base in enumerate(self.unverified_hq_locations):
                if self.bot.units.closest_distance_to(base) < 10:
                    self.unverified_hq_locations.pop(i)
                    if self.structures and self.structures.closest_distance_to(base) < 20:
                        if not self.known_hq_location:
                            self._set_enemy_hq_and_natural(base)
                    else:
                        self.logger.log(f"Scouted potential enemy hq location {base} which turned out empty")

        if self.known_hq_location and self.bot.units.closest_distance_to(self.known_hq_location) < 3:
            if not self.structures or self.structures.closest_distance_to(self.known_hq_location) > 20:
                self.known_hq_location = None
                self.logger.log(f"Cleared enemy HQ")

    def is_too_close(self, distance=None):
        if not distance:
            distance = self.too_close_distance
        if self.bot.start_location.distance_to_closest(self.structures) < distance:
            return True
        return False

    def check_proxy(self):
        # Known issue: This does not clear proxy status until we find more enemy buildings (in their hq for example)
        # This is to circumvent the issues that in some steps the structure list might return empty (which seemed to be due to running locally bot vs. bot)
        if self.structures:
            if self.is_too_close() and Strategy.PROXY not in self.strategies:
                self.logger.warn("Enemy uses proxy strategy!")
                self.strategies.add(Strategy.PROXY)
            elif not self.is_too_close() and Strategy.PROXY in self.strategies:
                self.logger.log("Enemy proxy beaten for now")
                self.strategies.remove(Strategy.PROXY)

    def check_rush(self):
        if self.bot.time < 60 * 5 and self.known_race == Race.Zerg and Strategy.ZERGLING_RUSH not in self.strategies:
            opponent_pools = self.structures(UnitTypeId.SPAWNINGPOOL)
            if opponent_pools.exists:
                bot_pools = self.bot.units(UnitTypeId.SPAWNINGPOOL)
                if bot_pools.exists:
                    if opponent_pools.first.build_progress - bot_pools.first.build_progress > 0.2:
                        self.logger.warn("Enemy has an earlier pool than we do, probably a zergling rush!")
                        self.strategies.add(Strategy.ZERGLING_RUSH)
                else:
                    self.logger.warn("Enemy has a pool but we don't!")
                    self.strategies.add(Strategy.ZERGLING_RUSH)

    def check_cannon_rush(self):
        if self.known_race == Race.Protoss:
            if Strategy.CANNON_RUSH not in self.strategies and self.is_too_close(15):
                self.strategies.add(Strategy.CANNON_RUSH)
            elif Strategy.CANNON_RUSH in self.strategies and not self.is_too_close(15):
                self.strategies.remove(Strategy.CANNON_RUSH)

    def get_next_scoutable_location(self, source_location=None):
        if source_location is None:
            source_location = self.bot.start_location
        if self.known_hq_location:
            return self.known_hq_location
        elif self.next_potential_location:
            return self.next_potential_location
        elif self.unverified_hq_locations:
            return self.unverified_hq_locations.closest_to(source_location).position
        else:
            return None

    def get_next_potential_building_closest_to(self, source):
        if self.structures:
            return self.structures.closest_to(source).position
        return self.get_next_scoutable_location(source)
