import random
from sc2.position import Point2


class Map:
    def __init__(self, bot):
        self.bot = bot
        self.corners = []
        self.my_corner = None
        self.opponent_corner = None
        self.helper_corner = None  # the corner furthest away from enemy natural
        self.flanker_waypoint = None  # point outside enemy base at the edge of the map

    def deferred_init(self):
        r = self.bot.game_info.playable_area
        self.corners = [
            Point2((r.x, r.y)),
            Point2((r.x + r.width, r.y)),
            Point2((r.x, r.y + r.height)),
            Point2((r.x + r.width, r.y + r.height))
        ]
        enemy_base = self.bot.opponent.known_hq_location
        enemy_natural = self.bot.opponent.known_natural
        my_base = self.bot.start_location
        self.opponent_corner = enemy_base.closest(self.corners)
        self.my_corner = my_base.closest(self.corners)
        sorted_from_enemy_nat = enemy_natural.sort_by_distance(self.corners)
        self.helper_corner = sorted_from_enemy_nat[2]

        distance = self.helper_corner.distance_to(self.opponent_corner)
        self.flanker_waypoint = self.helper_corner.towards(self.opponent_corner, distance * 0.7)

    def get_random_point(self):
        r = self.bot.game_info.playable_area
        x = random.randrange(r.x, r.x + r.width)
        y = random.randrange(r.y, r.y + r.height)
        return Point2((x, y))
