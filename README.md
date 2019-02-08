# LandLubber StarCraft 2 bot

This bot plays [StarCraft 2](https://starcraft2.com/). This bot came 11th out of 94 teams in the 2019 [Artificial Overmind Challenge](https://artificial-overmind.reaktor.com/).

## Prerequisites

- Python 3.6
- [python-sc2](https://github.com/Dentosal/python-sc2/) 0.10.11

## Level against default AI

This bot wins:

- often against `Difficulty.VeryHard` (*"Elite"* in-game)
- most of the time against `Difficulty.Harder` (*"Very Hard"* in-game)
- all the time against `Difficulty.Hard` (*"Harder"* in-game)

Zerg and Protoss opponents seem easiest, while Terran tech hardest.

Average score against Difficulty.Harder at various points of a match:

    time  points
    3:00  3600-3800
    5:00  5500-6400
    6:00  6700-8100
    8:00  9100-11500
    10:00 10800-12000
    11:00 12800-14800
    13:00 14700-16000
    15:00 16300-17700
    16:00 14000-18300
    18:00 22300
