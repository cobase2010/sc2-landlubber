
class Timer:
    def __init__(self, bot, ring_every=1.0):
        self.bot = bot
        self.last_ring = 0.0
        self.ring_every = ring_every

    @property
    def rings(self):
        if (self.bot.time - self.last_ring) >= self.ring_every:
            self.last_ring = self.bot.time
            return True
        else:
            return False
