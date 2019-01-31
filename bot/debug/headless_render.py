# import emoji
from sc2.ids.unit_typeid import UnitTypeId

DRAW_WIDTH = 80

class color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD_RED = '\033[1;31m'
    END = '\033[0m'

def green(str):
    return color.GREEN + str + color.END

def red(str):
    return color.BOLD_RED + str + color.END

def yellow(str):
    return color.YELLOW + str + color.END

ICON_DOOR = "|"
ICON_RALLY = "r"
ICON_WAYPOINT = "v"
ICON_ARMY_FRIENDLY = green(">")
ICON_ARMY_ENEMY = red("<")
ICON_ARMY_CONTESTED = yellow("X")

# ICON_DOOR = ":construction:"
# ICON_RALLY = ":anchor:"
# ICON_WAYPOINT = ":round_pushpin:"
# ICON_ARMY_FRIENDLY = ":octopus:"
# ICON_ARMY_ENEMY = ":panda_face:"
# ICON_ARMY_CONTESTED = ":fire:"
# ICON_FIGHTING = ":collision:"

def render_army(bot, forces_idle):
    # try:
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
        if pixel > DRAW_WIDTH - 1:
            return DRAW_WIDTH - 1
        else:
            return pixel

    # row[0] = ":house:"
    # row[-1] = ":post_office:"

    forces = bot.units(UnitTypeId.ZERGLING) | bot.units(UnitTypeId.ROACH) | bot.units(UnitTypeId.HYDRALISK) | bot.units(UnitTypeId.MUTALISK)
    for unit in forces:
        pos = px(unit.position)
        row[pos] = ICON_ARMY_FRIENDLY

    for enemy in bot.known_enemy_units:
        pos = px(enemy.position)
        if row[pos] == ICON_ARMY_FRIENDLY:
            row[pos] = ICON_ARMY_CONTESTED
        elif row[pos] == ICON_ARMY_CONTESTED:
            pass
        else:
            row[pos] = ICON_ARMY_ENEMY

    row[px(bot.hq_front_door)] = ICON_DOOR
    row[px(bot.army_spawn_rally_point)] = ICON_RALLY
    row[px(bot.army_attack_point)] = ICON_WAYPOINT

    row_string = ""
    for c in row:
        row_string += c

    print(row_string)
    # print(emoji.emojize(row_string))
    # except Exception as e:
    #     print(e)
