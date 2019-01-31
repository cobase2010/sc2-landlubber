

class EnemyTracker:
    def __init__(self, bot):
        self.bot = bot
        self.initial_enemy_potential_start_locations = bot.enemy_start_locations
        self.initial_enemy_race = bot.enemy_race
        self.known_enemy_race = None
        self.known_enemy_hq_location = None

    def get_next_potential_enemy_location(self):
        raise NotImplementedError
