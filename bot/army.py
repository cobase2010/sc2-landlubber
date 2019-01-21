import random


def nearest_enemy_building(rally, enemy_structures, enemy_start_locations):
    if enemy_structures.exists:
        return enemy_structures.closest_to(rally).position
    return rally.closest(enemy_start_locations)


# Attack to enemy base
# TODO rally first near enemy base/expansion, and then attack with a larger force
def get_army_actions(iteration, forces, rally, enemy_structures, enemy_start_locations):
    actions = []
    if len(forces) > 50 and iteration % 50 == 0:
        for unit in forces:
            actions.append(unit.attack(nearest_enemy_building(rally, enemy_structures, enemy_start_locations)))
    return actions


# Scout home base with overlords
def patrol_with_overlords(overlords, rally, start_location):
    actions = []
    for overlord in overlords.idle:
        if len(overlords) < 4:
            patrol = rally.random_on_distance(random.randrange(1, 5))
        else:
            patrol = start_location.random_on_distance(random.randrange(20, 30))
        actions.append(overlord.move(patrol))
    return actions
