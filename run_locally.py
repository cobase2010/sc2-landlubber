import random
import json
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from bot import MyBot

def pick_map(all_maps=False):
    if all_maps:
        return random.choice(maps.get())
    else:
        mapset = [
            "(2)DreamcatcherLE",
            "(2)LostandFoundLE",
            "(2)RedshiftLE"
        ]
        return maps.get(random.choice(mapset))


def main():
    with open("botinfo.json") as f:
        info = json.load(f)
    race = Race[info["race"]]

    run_game(
        pick_map(),
        [
            Bot(race, MyBot()),
            Computer(Race.Random, Difficulty.Harder)
        ],
        realtime=False,
        step_time_limit=0.5,
        game_time_limit=(60*20),
        save_replay_as="latest.SC2Replay"
    )


if __name__ == '__main__':
    main()
