import emoji

DRAW_WIDTH = 200

def render_army(bot, forces_idle):
    row = [" "] * DRAW_WIDTH
    line_start = bot.start_location
    if bot.enemy_known_base_locations:
        line_end = bot.enemy_known_base_locations[0]
    else:
        line_end = bot.enemy_start_locations[0]
    total_distance = line_end.distance_to(line_start)  # e.g. 138
    distance_per_pixel = total_distance / DRAW_WIDTH  # e.g. 0.69

    def px(point):
        distance = line_start.distance_to(point)
        pixel = int(distance / distance_per_pixel)
        return pixel

    row[px(bot.hq_front_door)] = ":house:"
    row[px(bot.army_spawn_rally_point)] = "s"
    row[px(bot.army_attack_point)] = "X"

    if forces_idle:
        row[px(forces_idle.center)] = ":pig:"

    row_string = ""
    for c in row:
        row_string += c
    print(emoji.emojize(row_string))
