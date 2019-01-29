import logging
import time
from sc2.constants import *

STEP_DURATION_WARNING_MILLIS = 40


def print_running_speed(bot, iteration):
    elapsed_realtime = time.time() - bot.match_start_time
    if bot.time > 0 and elapsed_realtime > 0:
        bot.log("real={:.0f}s game={:.0f}s iter={} speed={:.0f}x it/rt={:.0f} it/gt={:.1f}".format(
            elapsed_realtime,
            bot.time,
            iteration,
            bot.time / elapsed_realtime,
            iteration / elapsed_realtime,
            iteration / bot.time
        ), logging.DEBUG)


def print_score(bot):
    if int(bot.time) in [300, 600, 900, 1145]:
        s = bot.state.score
        bot.log("score  unit stru   minerals    gas      rate     idle")
        bot.log("{:5} {:5.0f} {:4.0f} {:5.0f}/{:5.0f} {:3.0f}/{:3.0f} {:4.0f}/{:3.0f} {:.0f}/{:.0f}".format(
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
    if iteration % 10 == 0 and bot.units(LARVA).amount > 2:
        bot.log(f"{bot.units(LARVA).amount} unused larvae!", logging.WARNING)

    if iteration % 80 == 0:
        if bot.vespene > 600:
            bot.log("Too much gas!", logging.WARNING)
        if bot.supply_left == 0:
            bot.log("Not enough overlords!", logging.WARNING)


def warn_for_step_duration(bot, step_start):
    duration_millis = (time.time() - step_start) * 1000
    if duration_millis > STEP_DURATION_WARNING_MILLIS:
        bot.log(f"{duration_millis:.0f}ms step duration", logging.WARNING)
