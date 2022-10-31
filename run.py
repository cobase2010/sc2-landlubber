import random
import json
from sc2.data import Race, Difficulty
from sc2.main import run_game
from sc2 import maps
from sc2.player import Bot, Computer
from bot import MyBot


def pick_map(all_maps=False):
    if all_maps:
        # return random.choice(maps.get("CatalystLE"))
        return maps.get("CatalystLE")
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
        pick_map(True),
        [
            Bot(race, MyBot()),
            Computer(Race.Random, Difficulty.VeryHard)
        ],
        realtime=True,
        # step_time_limit=0.5,      # We use locally much stricter limit than in the competition
        # game_time_limit=(60*60),  # Challenge has 60min gametime limit
        save_replay_as="latest.SC2Replay"
    )


if __name__ == '__main__':
    main()
