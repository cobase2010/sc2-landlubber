import time
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point3

STEP_DURATION_WARNING_MILLIS = 50

class DebugPrinter:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.match_start_time = time.time()
        self.step_durations = []

    def world_text(self, text, pos):
        if pos:
            self.bot._client.debug_text_world(text, Point3((pos.position.x, pos.position.y, 10)), None, 14)
        else:
            self.logger.error("Received None position to draw text")

    def print_step_stats(self):
        self.logger.debug("Step durations lately min={:.3f} avg={:.3f} max={:.3f}. Total steps recorded {}".format(
            min(self.step_durations[-500:]),
            sum(self.step_durations[-500:]) / len(self.step_durations[-500:]),
            max(self.step_durations[-500:]),
            len(self.step_durations)
        ))

    # def print_running_speed(self):
    #     iteration = self.bot.iteration
    #     if iteration % 100 == 0:
    #         elapsed_realtime = time.time() - self.match_start_time
    #         if self.bot.time > 0 and elapsed_realtime > 0:
    #             self.logger.debug("real={:.0f}s game={:.0f}s iter={} speed={:.0f}x it/rt={:.0f} it/gt={:.1f}".format(
    #                 elapsed_realtime,
    #                 self.bot.time,
    #                 iteration,
    #                 self.bot.time / elapsed_realtime,
    #                 iteration / elapsed_realtime,
    #                 iteration / self.bot.time
    #             ))

    def print_score(self):
        s = self.bot.state.score
        self.logger.debug("score  unit stru   minerals    gas      rate     idle")
        self.logger.debug("{:5} {:5.0f} {:4.0f} {:5.0f}/{:5.0f} {:3.0f}/{:3.0f} {:4.0f}/{:3.0f} {:.0f}/{:.0f}".format(
            s.score,
            s.total_value_units,
            s.total_value_structures,
            s.spent_minerals,
            s.collected_minerals,
            s.spent_vespene,
            s.collected_vespene,
            s.collection_rate_minerals,
            s.collection_rate_vespene,
            s.idle_worker_time,
            s.idle_production_time
        ))

    def warn_unoptimal_play(self):
        if self.bot.units(UnitTypeId.LARVA).amount > 4:
            reason = f"UNKNOWN REASON (min={self.bot.minerals} gas={self.bot.vespene} supply={self.bot.supply_left})"
            if self.bot.minerals < 100:
                reason = "not enough minerals"
            elif self.bot.supply_left < 2:
                reason = "not enough overlords with supply: " + str(self.bot.supply_left)
            self.logger.debug(f"{self.bot.units(UnitTypeId.LARVA).amount} unused larvae because {reason}!")
            # self.logger.log(f"{self.bot.units(UnitTypeId.LARVA).amount} unused larvae because {reason}!")
        if self.bot.vespene > 500:
            self.logger.warn("Too much gas!")
        if self.bot.supply_left == 0 and self.bot.units(UnitTypeId.OVERLORD).amount > 1:
            # self.logger.warn("Not enough overlords!" + " Supply:" + str(self.bot.supply_left))
            self.logger.debug("Not enough overlords!" + " Supply:" + str(self.bot.supply_left))

    def warn_for_step_duration(self, step_start):
        duration_millis = (time.time() - step_start) * 1000
        if duration_millis > STEP_DURATION_WARNING_MILLIS:
            self.logger.warn(f"{duration_millis:.0f}ms step duration")
