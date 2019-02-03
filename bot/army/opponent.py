from sc2 import Race, Difficulty


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

    def refresh(self):
        if self.bot.known_enemy_units:
            self.units = self.bot.known_enemy_units
            if self.known_race is None:
                self._set_race(self.units.first.race)

        if self.bot.known_enemy_structures:
            self.structures = self.bot.known_enemy_structures

        if self.unverified_hq_locations:
            for i, base in enumerate(self.unverified_hq_locations):
                if self.bot.units.closest_distance_to(base) < 10:
                    self.unverified_hq_locations.pop(i)
                    if self.structures and self.structures.closest_distance_to(base) < 20:
                        if not self.known_hq_location:
                            self._set_enemy_hq_and_natural(base)
                    else:
                        self.logger.log(f"Scouted potential enemy hq location {base} which turned out empty")

        if self.known_hq_location and self.bot.units.closest_distance_to(self.known_hq_location) < 5:
            if not self.structures or self.structures.closest_distance_to(self.known_hq_location) > 20:
                self.known_hq_location = None
                self.logger.log(f"Cleared enemy HQ")

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
            self.logger.error("Our army has no idea where to go")
            return None


    def get_next_potential_building_closest_to(self, source):
        if self.structures:
            return self.structures.closest_to(source).position
        return self.get_next_scoutable_location(source)
