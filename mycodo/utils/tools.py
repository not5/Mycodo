# coding=utf-8
import csv
import datetime
import logging
import time
from collections import OrderedDict

import os
from dateutil import relativedelta

from mycodo.config import USAGE_REPORTS_PATH
from mycodo.databases.models import Misc
from mycodo.databases.models import Output
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.influx import output_sec_on
from mycodo.utils.outputs import parse_output_information
from mycodo.utils.system_pi import assure_path_exists
from mycodo.utils.system_pi import set_user_grp

logger = logging.getLogger("mycodo.tools")


def next_schedule(time_span='daily', set_day=None, set_hour=None):
    """
    Return the next local epoch to schedule a task
    Returns the epoch of the next day or nth day of the week or month

    :param time_span: str, 'daily', 'weekly', or 'monthly'
    :param set_hour: int, hour of the day
    :param set_day: int, day of the week (0 = Monday) or month (1-28)
    :return: float, local epoch of next schedule
    """
    now = time.time()

    time_now = datetime.datetime.now()
    current_day = time_now.day
    current_month = time_now.month
    current_year = time_now.year

    if time_span == 'monthly':
        new_month = current_month
        new_year = current_year
        future_time_test = time.mktime(datetime.datetime(
            year=current_year,
            month=current_month,
            day=set_day,
            hour=set_hour).timetuple())
        if future_time_test < now:
            if current_month == 12:
                new_month = 1
                new_year += 1
            else:
                new_month += 1
            future_time_test = time.mktime(datetime.datetime(
                year=new_year,
                month=new_month,
                day=set_day,
                hour=set_hour).timetuple())
        return future_time_test

    elif time_span == 'weekly':
        today_weekday = datetime.datetime.today().weekday()
        if today_weekday < (set_day - 1):
            days_to_add = (set_day - 1) - today_weekday
        else:
            days_to_add = 7 - (today_weekday - (set_day - 1))

        future_time_test = time.mktime(
            (datetime.date.today() +
             relativedelta.relativedelta(days=days_to_add)).timetuple()) + (3600 * set_hour)
        return future_time_test

    elif time_span == 'daily':
        future_time_test = time.mktime(datetime.datetime(
            year=current_year,
            month=current_month,
            day=current_day,
            hour=set_hour).timetuple())
        if future_time_test < now:
            future_time_test = time.mktime(
                (datetime.date.today() +
                 relativedelta.relativedelta(days=1)).timetuple()) + (3600 * set_hour)

        return future_time_test


def return_output_usage(table_misc, table_outputs):
    """ Return output usage and cost """
    dict_outputs = parse_output_information()
    date_now = datetime.date.today()
    time_now = datetime.datetime.now()
    past_month_seconds = 0

    if table_misc.output_usage_dayofmonth == datetime.datetime.today().day:
        past_month_seconds = (time_now - time_now.replace(
            hour=0, minute=0, second=0, microsecond=0)).total_seconds()
    elif table_misc.output_usage_dayofmonth > datetime.datetime.today().day:
        first_day = date_now.replace(day=1)
        last_month = first_day - datetime.timedelta(days=1)
        past_month = last_month.replace(day=table_misc.output_usage_dayofmonth)
        past_month_seconds = (date_now - past_month).total_seconds()
    elif table_misc.output_usage_dayofmonth < datetime.datetime.today().day:
        past_month = date_now.replace(day=table_misc.output_usage_dayofmonth)
        past_month_seconds = (date_now - past_month).total_seconds()

    output_stats = OrderedDict()

    # Calculate output on duration for different time periods
    # Use OrderedDict to ensure proper order when saved to csv file
    output_stats['total_duration'] = dict.fromkeys(['1d', '1w', '1m', '1m_date', '1y'], 0)
    output_stats['total_kwh'] = dict.fromkeys(['1d', '1w', '1m', '1m_date', '1y'], 0)
    output_stats['total_cost'] = dict.fromkeys(['1d', '1w', '1m', '1m_date', '1y'], 0)

    for each_output in table_outputs:
        if ('output_types' in dict_outputs[each_output.output_type] and
                'on_off' in dict_outputs[each_output.output_type]['output_types']):
            past_1d_hours = output_sec_on(each_output.unique_id, 86400) / 3600
            past_1w_hours = output_sec_on(each_output.unique_id, 604800) / 3600
            past_1m_hours = output_sec_on(each_output.unique_id, 2629743) / 3600
            past_1m_date_hours = output_sec_on(each_output.unique_id, int(past_month_seconds)) / 3600
            past_1y_hours = output_sec_on(each_output.unique_id, 31556926) / 3600

            past_1d_kwh = table_misc.output_usage_volts * each_output.amps * past_1d_hours / 1000
            past_1w_kwh = table_misc.output_usage_volts * each_output.amps * past_1w_hours / 1000
            past_1m_kwh = table_misc.output_usage_volts * each_output.amps * past_1m_hours / 1000
            past_1m_date_kwh = table_misc.output_usage_volts * each_output.amps * past_1m_date_hours / 1000
            past_1y_kwh = table_misc.output_usage_volts * each_output.amps * past_1y_hours / 1000

            output_stats[each_output.unique_id] = {
                '1d': {
                    'hours_on': past_1d_hours,
                    'kwh': past_1d_kwh,
                    'cost': table_misc.output_usage_cost * past_1d_kwh
                },
                '1w': {
                    'hours_on': past_1w_hours,
                    'kwh': past_1w_kwh,
                    'cost': table_misc.output_usage_cost * past_1w_kwh
                },
                '1m': {
                    'hours_on': past_1m_hours,
                    'kwh': past_1m_kwh,
                    'cost': table_misc.output_usage_cost * past_1m_kwh
                },
                '1m_date': {
                    'hours_on': past_1m_date_hours,
                    'kwh': past_1m_date_kwh,
                    'cost': table_misc.output_usage_cost * past_1m_date_kwh
                },
                '1y': {
                    'hours_on': past_1y_hours,
                    'kwh': past_1y_kwh,
                    'cost': table_misc.output_usage_cost * past_1y_kwh
                }
            }

            output_stats['total_duration']['1d'] += past_1d_hours
            output_stats['total_duration']['1w'] += past_1w_hours
            output_stats['total_duration']['1m'] += past_1m_hours
            output_stats['total_duration']['1m_date'] += past_1m_date_hours
            output_stats['total_duration']['1y'] += past_1y_hours

            output_stats['total_kwh']['1d'] += past_1d_kwh
            output_stats['total_kwh']['1w'] += past_1w_kwh
            output_stats['total_kwh']['1m'] += past_1m_kwh
            output_stats['total_kwh']['1m_date'] += past_1m_date_kwh
            output_stats['total_kwh']['1y'] += past_1y_kwh

            output_stats['total_cost']['1d'] += table_misc.output_usage_cost * past_1d_kwh
            output_stats['total_cost']['1w'] += table_misc.output_usage_cost * past_1w_kwh
            output_stats['total_cost']['1m'] += table_misc.output_usage_cost * past_1m_kwh
            output_stats['total_cost']['1m_date'] += table_misc.output_usage_cost * past_1m_date_kwh
            output_stats['total_cost']['1y'] += table_misc.output_usage_cost * past_1y_kwh

    return output_stats


def generate_output_usage_report():
    """
    Generate output usage report in a csv file

    """
    logger.debug("Generating output usage report...")
    try:
        assure_path_exists(USAGE_REPORTS_PATH)

        misc = db_retrieve_table_daemon(Misc, entry='first')
        output = db_retrieve_table_daemon(Output)
        output_usage = return_output_usage(misc, output.all())

        timestamp = time.strftime("%Y-%m-%d_%H-%M")
        file_name = 'output_usage_report_{ts}.csv'.format(ts=timestamp)
        report_path_file = os.path.join(USAGE_REPORTS_PATH, file_name)

        with open(report_path_file, 'wb') as f:
            w = csv.writer(f)
            # Header row
            w.writerow([
                 'Relay ID',
                 'Relay Unique ID',
                 'Relay Name',
                 'Type',
                 'Past Day',
                 'Past Week',
                 'Past Month',
                 'Past Month (from {})'.format(misc.output_usage_dayofmonth),
                 'Past Year'
            ])
            for key, value in output_usage.items():
                if key in ['total_duration', 'total_cost', 'total_kwh']:
                    # Totals rows
                    w.writerow(['', '', '',
                                key,
                                value['1d'],
                                value['1w'],
                                value['1m'],
                                value['1m_date'],
                                value['1y']])
                else:
                    # Each output rows
                    each_output = output.filter(Output.unique_id == key).first()
                    w.writerow([each_output.unique_id,
                                each_output.unique_id,
                                str(each_output.name).encode("utf-8"),
                                'hours_on',
                                value['1d']['hours_on'],
                                value['1w']['hours_on'],
                                value['1m']['hours_on'],
                                value['1m_date']['hours_on'],
                                value['1y']['hours_on']])
                    w.writerow([each_output.unique_id,
                                each_output.unique_id,
                                str(each_output.name).encode("utf-8"),
                                'kwh',
                                value['1d']['kwh'],
                                value['1w']['kwh'],
                                value['1m']['kwh'],
                                value['1m_date']['kwh'],
                                value['1y']['kwh']])
                    w.writerow([each_output.unique_id,
                                each_output.unique_id,
                                str(each_output.name).encode("utf-8"),
                                'cost',
                                value['1d']['cost'],
                                value['1w']['cost'],
                                value['1m']['cost'],
                                value['1m_date']['cost'],
                                value['1y']['cost']])

        set_user_grp(report_path_file, 'mycodo', 'mycodo')
    except Exception:
        logger.exception("Energy Usage Report Generation ERROR")
