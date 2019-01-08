# LandLubber StarCraft 2 bot

- [Discord](https://discord.gg/D9XEhWY)
- [Artificial Overmind Challenge site](https://artificial-overmind.reaktor.com/)
- [python-sc2](https://github.com/Dentosal/python-sc2/)
- [The BotAI-class](https://github.com/Dentosal/python-sc2/wiki/The-BotAI-class)
- [Units and actions](https://github.com/Dentosal/python-sc2/wiki/Units-and-actions)

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
