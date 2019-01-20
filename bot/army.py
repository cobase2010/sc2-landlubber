
def nearest_enemy_building(rally, enemy_structures, enemy_start_locations):
    if enemy_structures.exists:
        return enemy_structures.closest_to(rally).position
    return enemy_start_locations.closest_to(rally)

# Attack to enemy base
# TODO rally first near enemy base/expansion, and then attack with a larger force
def get_army_actions(iteration, forces, rally, enemy_structures, enemy_start_locations):
    actions = []
    if len(forces) > 50 and iteration % 50 == 0:
        for unit in forces:
            actions.append(unit.attack(nearest_enemy_building(rally, enemy_structures, enemy_start_locations)))
    return actions
