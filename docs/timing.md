## Notes on performance and timing

**On non-real-time:** In the beginning of a match, the game tends to run on 30x speed, i.e. when 1 real-time second passes, 30 in-game seconds have passed. The speed then gradually slows down as players build larger forces. In the end-game the speed is around 10-15x. The game seems to run a fixed number of steps per in-game second, meaning that the execution time of a match grows if bots need more time for calculations. But, this means that it is safe to make assumptions on `on_step` iteration count and/or `self.time`.

**On real-time:** When running real-time, the iterations per game-time second fluctuates, 40-60 iterations per second (both real-time and game-time). We should definitely time things against `self.time`, to avoid unnecessary spam.

If the bot takes too long to process an iteration, it is put to penalty cooldown. I am yet to know if this means you skip iterations, or does the iteration count de-sync from `self.time`.

=> It is more consistent to time play-related things against game-time instead of iterations.
