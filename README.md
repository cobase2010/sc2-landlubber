# LandLubber StarCraft 2 bot

Forked from [Overmind-Challenge-Template](https://gitlab.com/overmind-challenge/overmind-challenge-template).

- [Artificial Overmind Challenge Site](https://artificial-overmind.reaktor.com/)
- [Artificial Overmind Challenge Discord](https://discord.gg/D9XEhWY)

## Prerequisites

- [python-sc2](https://github.com/Dentosal/python-sc2/)

## Level

The bot wins all races some of the time against Difficulty.Harder (called "Very Hard" in-game) and all the time against Difficulty.Hard (called "Harder" in-game). Zerg seems to be the easiest.

Usual score at 5/10/19 minutes game time:

    5.0 59/60   score unit  stru minerals    gas       rate     idle
    5.0 59/60   6363  3500  1075 4325/ 4335  550/1028  1287/313 0/2361
    10.0 115/130 10914 13450 1375 13875/13940 2600/2624 2519/335 0/10882
    19.1 169/192 16348 36400 1675 34950/36660 4475/4488 1847/0   3435/64582


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
