import random
import json
from sc2.data import Race, Difficulty
from sc2.main import run_game
from sc2 import maps
from sc2.player import Bot, Computer
from bot import MyBot
import sys
import os
from datetime import datetime



SAVE_REPLAY = True
BOT_DIFFICULTY = Difficulty.VeryHard
# BOT_DIFFICULTY = Difficulty.CheatMoney
# BOT_DIFFICULTY = Difficulty.CheatInsane
# BOT_RACE = Race.Zerg
BOT_RACE = Race.Zerg


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

    # run_game(
    #     pick_map(True),
    #     [
    #         Bot(race, MyBot()),
    #         Computer(Race.Random, Difficulty.VeryHard)
    #     ],
    #     realtime=False,
    #     # step_time_limit=0.5,      # We use locally much stricter limit than in the competition
    #     # game_time_limit=(60*60),  # Challenge has 60min gametime limit
    #     save_replay_as="latest.SC2Replay"
    # )

    episode = 0
    while episode < 30:
        replay_file = None
        if SAVE_REPLAY:
            replay_file = f"./replays/zergbot_{BOT_RACE}_{BOT_DIFFICULTY}_{episode}"
        result = run_game(
            maps.get("AbyssalReefLE"),
            [
            Bot(race, MyBot()), 
            # Bot(Race.Protoss, IncrediBot()),
            # Bot(Race.Zerg, ZergRushBot())
            # ],
            Computer(
                # Race.Zerg, Difficulty.VeryHard)],
                BOT_RACE, BOT_DIFFICULTY)],
            
            realtime=False,
            save_replay_as=replay_file,
        )
        if SAVE_REPLAY:
            os.rename(replay_file, f"{replay_file}_{result}.SC2Replay")
        
        with open("results.txt","a") as f:
            f.write(f"{str(datetime.now())}: Episode: {episode} vs {BOT_RACE}({BOT_DIFFICULTY}): {result}\n")

        print(f"Episode: {episode}: Game finished at: {str(datetime.now())} with result: {result}\n")
        episode += 1


if __name__ == '__main__':
    main()
