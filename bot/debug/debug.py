import time
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point3

STEP_DURATION_WARNING_MILLIS = 50

class DebugPrinter:
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger

    def world_text(self, text, pos):
        if pos:
            self.bot._client.debug_text_world(text, Point3((pos.position.x, pos.position.y, 10)), None, 14)
        else:
            self.logger.error("Received None position to draw text")

    def print_running_speed(self):
        iteration = self.bot.iteration
        if iteration % 100 == 0:
            elapsed_realtime = time.time() - self.bot.match_start_time
            if self.bot.time > 0 and elapsed_realtime > 0:
                self.logger.debug("real={:.0f}s game={:.0f}s iter={} speed={:.0f}x it/rt={:.0f} it/gt={:.1f}".format(
                    elapsed_realtime,
                    self.bot.time,
                    iteration,
                    self.bot.time / elapsed_realtime,
                    iteration / elapsed_realtime,
                    iteration / self.bot.time
                ))

    def print_score(self):
        if self.bot.iteration % 5 == 0 and int(self.bot.time) % 60 == 0:
            s = self.bot.state.score
            self.logger.log("score  unit stru   minerals    gas      rate     idle")
            self.logger.log("{:5} {:5.0f} {:4.0f} {:5.0f}/{:5.0f} {:3.0f}/{:3.0f} {:4.0f}/{:3.0f} {:.0f}/{:.0f}".format(
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
        if self.bot.iteration % 10 == 0 and self.bot.units(UnitTypeId.LARVA).amount > 3:
            self.logger.log(f"{self.bot.units(UnitTypeId.LARVA).amount} unused larvae!")

        if self.bot.iteration % 80 == 0:
            if self.bot.vespene > 500:
                self.logger.warn("Too much gas!")
            if self.bot.supply_left == 0:
                self.logger.warn("Not enough overlords!")


    def warn_for_step_duration(self, step_start):
        duration_millis = (time.time() - step_start) * 1000
        if duration_millis > STEP_DURATION_WARNING_MILLIS:
            self.logger.warn(f"{duration_millis:.0f}ms step duration")
