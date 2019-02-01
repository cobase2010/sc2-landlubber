import time
from sc2.ids.unit_typeid import UnitTypeId

STEP_DURATION_WARNING_MILLIS = 50


def print_running_speed(bot, iteration):
    if iteration % 100 == 0:
        elapsed_realtime = time.time() - bot.match_start_time
        if bot.time > 0 and elapsed_realtime > 0:
            bot.logger.debug("real={:.0f}s game={:.0f}s iter={} speed={:.0f}x it/rt={:.0f} it/gt={:.1f}".format(
                elapsed_realtime,
                bot.time,
                iteration,
                bot.time / elapsed_realtime,
                iteration / elapsed_realtime,
                iteration / bot.time
            ))


def print_score(bot, iteration):
    if iteration % 5 == 0 and int(bot.time) % 60 == 0:
        s = bot.state.score
        bot.logger.log("score  unit stru   minerals    gas      rate     idle")
        bot.logger.log("{:5} {:5.0f} {:4.0f} {:5.0f}/{:5.0f} {:3.0f}/{:3.0f} {:4.0f}/{:3.0f} {:.0f}/{:.0f}".format(
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


def warn_unoptimal_play(bot, iteration):
    if iteration % 10 == 0 and bot.units(UnitTypeId.LARVA).amount > 3:
        bot.logger.log(f"{bot.units(UnitTypeId.LARVA).amount} unused larvae!")

    if iteration % 80 == 0:
        if bot.vespene > 500:
            bot.logger.warn("Too much gas!")
        if bot.supply_left == 0:
            bot.logger.warn("Not enough overlords!")


def warn_for_step_duration(bot, step_start):
    duration_millis = (time.time() - step_start) * 1000
    if duration_millis > STEP_DURATION_WARNING_MILLIS:
        bot.logger.warn(f"{duration_millis:.0f}ms step duration")
