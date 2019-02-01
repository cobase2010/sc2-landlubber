# LandLubber StarCraft 2 bot

Forked from [Overmind-Challenge-Template](https://gitlab.com/overmind-challenge/overmind-challenge-template).

- [Artificial Overmind Challenge Site](https://artificial-overmind.reaktor.com/)
- [Artificial Overmind Challenge Discord](https://discord.gg/D9XEhWY)

## Prerequisites

- Python 3.6
- [python-sc2](https://github.com/Dentosal/python-sc2/) 0.10.10

## Level

This bot:

- loses all the time against `Difficulty.VeryHard` (*"Elite"* in-game)
- wins most of the time against `Difficulty.Harder` (*"Very Hard"* in-game)
- wins all the time against `Difficulty.Hard` (*"Harder"* in-game)

Zerg and Protoss seem easiest, while Terran tech hardest.

Usual score against Difficulty.Harder:

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

More detailed scores:

    3.0  33/ 38 score  unit stru   minerals    gas      rate     idle
    3.0  33/ 38  3773  2100  675  2300/ 2405 225/268 1007/156 0/722
    5.0  59/ 60  6194  4000 1075  4325/ 4560 650/784 1483/313 0/1642
    6.0  75/ 76  7361  5600 1075  5925/ 6195 975/1116 1707/335 0/1943

    3.0  30/ 30  3673  2150  675  2375/ 2405 200/268  951/156 0/699
    5.0  52/ 52  5661  4100 1075  4350/ 4515 675/796 1455/335 0/1797
    6.0  73/ 76  7229  5350 1075  6050/ 6055 1025/1124 1567/335 0/2321
    8.0  83/106  9118  8750 1825  9475/ 9520 2100/2148 1931/627 0/3466
    10.0 122/122 11948 13700 1850 13675/13710 3450/3488 2155/828 0/5006
    11.0 123/130 12831 16300 1875 16000/16025 4225/4456 2407/1030 0/5944

    3.0  29/ 30  3632  2000  675  2175/ 2305 175/252  951/134 0/552
    5.0  60/ 60  6239  3900 1075  4200/ 4395 625/744 1287/246 0/1361
    6.0  71/ 76  6739  5300 1075  5925/ 5935 850/1004 1707/268 0/1927
    8.0 102/106  9422  9250 1425  9475/ 9490 1800/1932 1847/582 0/2991
    10.0 119/130 12006 13650 1875 13925/13950 3150/3256 2155/895 0/4622
    11.0 133/138 13809 16750 1875 15775/16305 4000/4204 2379/985 0/5660
    15.0 188/200 17489 31450 2225 27050/27285 8375/8404 2687/1276 0/9926

    3.0  33/ 38  3773  2100  675  2300/ 2405 225/268  923/156 0/715
    5.0  58/ 60  5616  4200 1075  4550/ 4570 675/796 1511/335 0/1628
    6.0  75/ 76  7274  5500 1075  6075/ 6200 925/1124 1679/313 0/1988
    8.0 119/130 11280  8900 1825  9575/ 9590 1850/2240 2071/649 0/3108


## Notes on performance and timing

**On non-real-time:** In the beginning of a match, the game tends to run on 30x speed, i.e. when 1 real-time second passes, 30 in-game seconds have passed. The speed then gradually slows down as players build larger forces. In the end-game the speed is around 10-15x. The game seems to run a fixed number of steps per in-game second, meaning that the execution time of a match grows if bots need more time for calculations. But, this means that it is safe to make assumptions on `on_step` iteration count and/or `self.time`.

**On real-time:** When running real-time, the iterations per game-time second fluctuates, 40-60 iterations per second (both real-time and game-time). We should definitely time things against `self.time`, to avoid unnecessary spam.

If the bot takes too long to process an iteration, it is put to penalty cooldown. I am yet to know if this means you skip iterations, or does the iteration count de-sync from `self.time`. It might be safer to calculate match timings against the game-time.

## Rules

- The competition will use [the official SEUL rules](https://seul.fi/e-urheilu/pelisaannot/turnaussaannot-starcraft-ii/#english-version) where applicable
- However, since there are no human players or real-time gameplay and because bots may be quite deterministic in their nature, we've made the following adjustments:
  * The "3. Other rules" section is not used
    + Bots should properly resign instead of just disconnecting
  * The "7. Fair play" section forbids insulting others. However, we not only allow, but actively encourage you to mock the opposing bot using the in-game chat
    + Please remember to keep it fun and good-natured - we're not trying to make anybody feel bad but are here to have fun
  * Games will be played with a time limit. This is initially 30 minutes of in-game time, and will be updated later if it causes any issues
  * Bot code crashing or exceeding the per-step time limit will automatically result in a loss
    + Per-step limit is currently 2 seconds, but will be lowered it that becomes an issue later
  * Draw situations will not be replayed and the games will be marked as draws instead
  * If score-based evaluation is implemented during the competition, it will be used to resolve draws
    + In the finals, draw situations will be resolved by who has the higher army value at the end of the game if scores are not available
  * Pausing the game is neither allowed or possible
  * The map pool is static and decided by the organizers
    + All maps will be selected from the official ladder map pool starting with the first season of 2017, available [here](https://github.com/Blizzard/s2client-proto#map-packs)
- The organizers reserve the right to change the rules and technical limitations during the competition
- Your git repo for the bot must not exceed one gigabyte in size
- Technical limitations:
  * IO is not allowed. Don't use filesystem or networking.
  * Starting threads or processes is not allowed.
- Please contact us (e.g. in Discord) if you have any questions
