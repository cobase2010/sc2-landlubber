import logging


class TerminalLogger:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        log_format = logging.Formatter('%(levelname)-7s %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(log_format)
        self.logger.addHandler(handler)

    def log(self, msg, level=logging.INFO):
        try:
            if hasattr(self.bot, "state"):
                self.logger.log(level, "{:4.1f} {:3.0f} {:3}/{:<3} {}".format(
                    self.bot.time / 60,
                    self.bot.previous_step_duration_millis,
                    self.bot.supply_used, 
                    self.bot.supply_cap,
                    msg))
            else:
                self.logger.log(level, "--.- --- ---/--- {}".format(msg))
        except Exception as e:
            print("ERROR WHILE LOGGING:", level, msg, e)

    def error(self, msg):
        self.log(msg, logging.ERROR)

    def warn(self, msg):
        self.log(msg, logging.WARNING)

    def debug(self, msg):
        self.log(msg, logging.DEBUG)
