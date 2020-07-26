# coding=utf-8
#
# controller_output.py - Output controller to manage turning outputs on/off
#
#  Copyright (C) 2017  Kyle T. Gabriel
#
#  This file is part of Mycodo
#
#  Mycodo is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mycodo is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mycodo. If not, see <http://www.gnu.org/licenses/>.
#
#  Contact at kylegabriel.com
import datetime
import threading
import time
import timeit

from sqlalchemy import and_
from sqlalchemy import or_

from mycodo.config import SQL_DATABASE_MYCODO
from mycodo.controllers.base_controller import AbstractController
from mycodo.databases.models import DeviceMeasurements
from mycodo.databases.models import Misc
from mycodo.databases.models import Output
from mycodo.databases.models import SMTP
from mycodo.databases.models import Trigger
from mycodo.databases.utils import session_scope
from mycodo.mycodo_client import DaemonControl
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.influx import read_last_influxdb
from mycodo.utils.influx import write_influxdb_value
from mycodo.utils.modules import load_module_from_file
from mycodo.utils.outputs import output_types
from mycodo.utils.outputs import parse_output_information
from mycodo.utils.system_pi import return_measurement_info

MYCODO_DB_PATH = 'sqlite:///' + SQL_DATABASE_MYCODO


class OutputController(AbstractController, threading.Thread):
    """
    class for controlling outputs

    """
    def __init__(self, ready, debug):
        threading.Thread.__init__(self)
        super(OutputController, self).__init__(ready, unique_id=None, name=__name__)

        self.set_log_level_debug(debug)
        self.control = DaemonControl()

        self.button_pressed = None
        self.button_args_dict = None
        self.button_output_id = None

        # SMTP options
        self.smtp_max_count = None
        self.smtp_wait_time = None
        self.smtp_timer = None
        self.email_count = None
        self.allowed_to_send_notice = None

        self.sample_rate = None
        self.output = {}
        self.dict_outputs = {}
        self.output_unique_id = {}
        self.output_type = {}
        self.output_name = {}
        self.output_amps = {}
        self.output_state_startup = {}
        self.output_startup_value = {}
        self.output_state_shutdown = {}
        self.output_shutdown_value = {}
        self.trigger_functions_at_start = {}
        self.output_on_until = {}
        self.output_last_duration = {}
        self.output_on_duration = {}
        self.output_off_triggered = {}
        self.output_force_command = {}
        self.output_time_turned_on = {}
        self.output_types = []

    def initialize_variables(self):
        """ Begin initializing output parameters """
        self.sample_rate = db_retrieve_table_daemon(
            Misc, entry='first').sample_rate_controller_output

        self.logger.debug("Initializing Outputs")
        try:
            smtp = db_retrieve_table_daemon(SMTP, entry='first')
            self.smtp_max_count = smtp.hourly_max
            self.smtp_wait_time = time.time() + 3600
            self.smtp_timer = time.time()
            self.email_count = 0
            self.allowed_to_send_notice = True

            outputs = db_retrieve_table_daemon(Output, entry='all')
            self.all_outputs_initialize(outputs)
            self.all_outputs_set_state()  # Turn outputs on that are set to be on at start
            self.logger.debug("Outputs Initialized")
        except Exception as except_msg:
            self.logger.exception(
                "Problem initializing outputs: {err}".format(err=except_msg))

    def loop(self):
        """ Main loop of the output controller """
        if self.button_pressed:
            try:
                getattr(self.output[self.button_output_id], self.button_pressed)(self.button_args_dict)
            except:
                self.logger.exception("Error executing button press function '{}'".format(
                    self.button_pressed))
            self.button_args_dict = None
            self.button_output_id = None
            self.button_pressed = None

        for output_id in self.output_unique_id:
            # Execute if past the time the output was supposed to turn off
            if (self.output_on_until[output_id] < datetime.datetime.now() and
                    self.output_on_duration[output_id] and
                    not self.output_off_triggered[output_id]):

                # Use a thread to prevent blocking the loop
                self.output_off_triggered[output_id] = True
                turn_output_off = threading.Thread(
                    target=self.output_on_off,
                    args=(output_id,
                          'off',))
                turn_output_off.start()

    def run_finally(self):
        """ Run when the controller is shutting down """
        # Turn all outputs to their shutdown state
        for each_output_id in self.output_unique_id:
            shutdown_timer = timeit.default_timer()
            if self.output_state_shutdown[each_output_id] == '0':
                self.logger.info(
                    "Setting Output {id} shutdown state to OFF".format(
                        id=each_output_id.split('-')[0]))
                self.output_on_off(
                    each_output_id, 'off', trigger_conditionals=False)

            elif self.output_state_shutdown[each_output_id] == '1':
                self.logger.info(
                    "Setting Output {id} shutdown state to ON".format(
                        id=each_output_id.split('-')[0]))
                self.output_on_off(
                    each_output_id, 'on', trigger_conditionals=False)

            elif self.output_state_shutdown[each_output_id] == 'set_duty_cycle':
                self.logger.info(
                    "Setting Output {id} shutdown duty cycle to user-set value "
                    "of {dc} %".format(
                        id=each_output_id.split('-')[0],
                        dc=self.output_shutdown_value[each_output_id]))
                self.output_on_off(
                    each_output_id,
                    'on',
                    duty_cycle=self.output_shutdown_value[each_output_id],
                    trigger_conditionals=self.trigger_functions_at_start[each_output_id])

            # instruct each output to shutdown
            self.output[each_output_id].shutdown(shutdown_timer)

    def all_outputs_initialize(self, outputs):
        """ Initialize all output variables and classes """
        self.dict_outputs = parse_output_information()
        self.output_types = output_types()

        for each_output in outputs:
            try:
                self.output_unique_id[each_output.unique_id] = each_output.unique_id
                self.output_type[each_output.unique_id] = each_output.output_type
                self.output_name[each_output.unique_id] = each_output.name
                self.output_amps[each_output.unique_id] = each_output.amps
                self.output_state_startup[each_output.unique_id] = each_output.state_startup
                self.output_startup_value[each_output.unique_id] = each_output.startup_value
                self.output_state_shutdown[each_output.unique_id] = each_output.state_shutdown
                self.output_shutdown_value[each_output.unique_id] = each_output.shutdown_value
                self.output_on_until[each_output.unique_id] = datetime.datetime.now()
                self.output_last_duration[each_output.unique_id] = 0
                self.output_on_duration[each_output.unique_id] = False
                self.output_off_triggered[each_output.unique_id] = False
                self.output_time_turned_on[each_output.unique_id] = None
                self.output_force_command[each_output.unique_id] = each_output.force_command
                self.trigger_functions_at_start[each_output.unique_id] = each_output.trigger_functions_at_start

                if each_output.output_type in self.dict_outputs:
                    output_loaded = load_module_from_file(
                        self.dict_outputs[each_output.output_type]['file_path'],
                        'outputs')
                    self.output[each_output.unique_id] = output_loaded.OutputModule(each_output)
                    self.output[each_output.unique_id].setup_output()
                    self.output[each_output.unique_id].init_post()

                self.logger.debug("{id} ({name}) Initialized".format(
                    id=each_output.unique_id.split('-')[0], name=each_output.name))
            except:
                self.logger.exception("Could not initialize output {}".format(
                    each_output.unique_id))

    def add_mod_output(self, output_id):
        """
        Add or modify local dictionary of output settings form SQL database

        When a output is added or modified while the output controller is
        running, these local variables need to also be modified to
        maintain consistency between the SQL database and running controller.

        :param output_id: Unique ID for each output
        :type output_id: str

        :return: 0 for success, 1 for fail, with success for fail message
        :rtype: int, str
        """
        try:
            self.dict_outputs = parse_output_information()

            output = db_retrieve_table_daemon(Output, unique_id=output_id)

            self.output_unique_id[output_id] = output.unique_id
            self.output_type[output_id] = output.output_type
            self.output_name[output_id] = output.name
            self.output_amps[output_id] = output.amps
            self.output_state_startup[output_id] = output.state_startup
            self.output_startup_value[output_id] = output.startup_value
            self.output_state_shutdown[output_id] = output.state_shutdown
            self.output_shutdown_value[output_id] = output.shutdown_value
            self.output_on_until[output_id] = datetime.datetime.now()
            self.output_time_turned_on[output_id] = None
            self.output_last_duration[output_id] = 0
            self.output_on_duration[output_id] = False
            self.output_off_triggered[output_id] = False
            self.output_force_command[output_id] = output.force_command
            self.trigger_functions_at_start[output_id] = output.trigger_functions_at_start

            if self.output_type[output_id] in self.dict_outputs:
                output_loaded = load_module_from_file(
                    self.dict_outputs[self.output_type[output_id]]['file_path'],
                    'outputs')
                self.output[output_id] = output_loaded.OutputModule(output)
                self.output[output_id].setup_output()
                self.output[output_id].init_post()

            return 0, "add_mod_output() Success"
        except Exception as e:
            return 1, "add_mod_output() Error: {id}: {e}".format(id=output_id, e=e)

    def del_output(self, output_id):
        """
        Delete output from being managed by Output controller

        :param output_id: Unique ID for output
        :type output_id: str

        :return: 0 for success, 1 for fail (with error message)
        :rtype: int, str
        """
        try:
            self.logger.debug("Output {id} ({name}) Deleted.".format(
                id=self.output_unique_id[output_id],
                name=self.output_name[output_id]))

            # instruct output to shutdown
            shutdown_timer = timeit.default_timer()
            self.output[output_id].shutdown(shutdown_timer)

            self.output_unique_id.pop(output_id, None)
            self.output_name.pop(output_id, None)
            self.output_amps.pop(output_id, None)
            self.output_state_startup.pop(output_id, None)
            self.output_startup_value.pop(output_id, None)
            self.output_state_shutdown.pop(output_id, None)
            self.output_shutdown_value.pop(output_id, None)
            self.output_on_until.pop(output_id, None)
            self.output_last_duration.pop(output_id, None)
            self.output_on_duration.pop(output_id, None)
            self.output_off_triggered.pop(output_id, None)
            self.output_force_command.pop(output_id, None)
            self.trigger_functions_at_start.pop(output_id, None)
            self.output_type.pop(output_id, None)
            self.output.pop(output_id, None)

            return 0, "del_output() Success"
        except Exception as e:
            return 1, "del_output() Error: {id}: {e}".format(id=output_id, e=e)

    def all_outputs_set_state(self):
        """Turn all outputs on that are set to be on at startup"""
        for each_output_id in self.output_unique_id:
            try:
                if self.output_state_startup[each_output_id] is None:
                    pass  # Don't turn on or off

                # PWM Outputs
                elif self.output_type[each_output_id] in self.output_types['pwm']:
                    if self.output_state_startup[each_output_id] == '0':
                        self.logger.info(
                            "Setting Output {id} startup duty cycle to 0 %".format(
                                id=each_output_id.split('-')[0]))
                        self.output_on_off(
                            each_output_id,
                            'off',
                            trigger_conditionals=self.trigger_functions_at_start[each_output_id])

                    elif self.output_state_startup[each_output_id] == 'set_duty_cycle':
                        self.logger.info(
                            "Setting Output {id} startup duty cycle to user-set"
                            " value of {dc} %".format(
                                id=each_output_id.split('-')[0],
                                dc=self.output_startup_value[each_output_id]))
                        self.output_on_off(
                            each_output_id,
                            'on',
                            duty_cycle=self.output_startup_value[each_output_id],
                            trigger_conditionals=self.trigger_functions_at_start[each_output_id])

                    elif self.output_state_startup[each_output_id] == 'last_duty_cycle':
                        device_measurement = db_retrieve_table_daemon(
                            DeviceMeasurements).filter(
                            DeviceMeasurements.device_id == each_output_id).all()
                        measurement = None
                        for each_meas in device_measurement:
                            if each_meas.measurement == 'duty_cycle':
                                measurement = each_meas
                        channel, unit, measurement = return_measurement_info(
                            measurement, None)

                        last_measurement = read_last_influxdb(
                            each_output_id,
                            unit,
                            channel,
                            measure=measurement,
                            duration_sec=None)

                        if last_measurement:
                            self.logger.info(
                                "Setting Output {id} startup duty cycle to last"
                                " known value of {dc} %".format(
                                    id=each_output_id.split('-')[0],
                                    dc=last_measurement[1]))
                            self.output_on_off(
                                each_output_id,
                                'on',
                                duty_cycle=last_measurement[1],
                                trigger_conditionals=self.trigger_functions_at_start[each_output_id])
                        else:
                            self.logger.error(
                                "Output {id} instructed at startup to be set to "
                                "the last known duty cycle, but a last known "
                                "duty cycle could not be found in the measurement "
                                "database".format(
                                    id=each_output_id.split('-')[0]))

                # Non-PWM outputs
                elif self.output_state_startup[each_output_id] == '1':
                    self.logger.info(
                        "Setting Output {id} startup state to ON".format(
                            id=each_output_id.split('-')[0]))
                    self.output_on_off(
                        each_output_id,
                        'on',
                        trigger_conditionals=self.trigger_functions_at_start[each_output_id])

                elif self.output_state_startup[each_output_id] == '0':
                    self.logger.info(
                        "Setting Output {id} startup state to OFF".format(
                            id=each_output_id.split('-')[0]))
                    self.output_on_off(
                        each_output_id,
                        'off',
                        trigger_conditionals=False)
            except:
                self.logger.error("Could not set state for output {}".format(
                    each_output_id))

    def output_on_off(self, output_id, state,
                      amount=0.0,
                      output_type=None,
                      min_off=0.0,
                      duty_cycle=0.0,
                      trigger_conditionals=True):
        """
        Manipulate an output by passing on/off, a volume, or a PWM duty cycle
        to the output module.

        :param output_id: ID for output
        :type output_id: str
        :param state: What state is desired? 'on', 1, True or 'off', 0, False
        :type state: str or int or bool
        :param amount: If state is 'on', an amount can be set (e.g. duration to stay on, volume to output, etc.)
        :type amount: float
        :param output_type: The type of output ('sec', 'vol', 'pwm')
        :type output_type: str
        :param min_off: Don't allow on again for at least this amount (0 = disabled)
        :type min_off: float
        :param duty_cycle: If state is 'on', set the duty cycle of PWM output
        :type duty_cycle: float
        :param trigger_conditionals: Whether to allow trigger conditionals to act or not
        :type trigger_conditionals: bool
        """
        msg = ''

        self.logger.debug("output_on_off({}, {}, {}, {}, {}, {}, {})".format(
            output_id,
            state,
            amount,
            output_type,
            min_off,
            duty_cycle,
            trigger_conditionals))

        if state not in ['on', 1, True, 'off', 0, False]:
            return 1, 'state not "on", 1, True, "off", 0, or False'
        elif state in ['on', 1, True]:
            state = 'on'
        elif state in ['off', 0, False]:
            state = 'off'

        current_time = datetime.datetime.now()

        if amount is None:
            amount = 0

        output_is_on = self.is_on(output_id)

        # Check if output exists
        if output_id not in self.output_unique_id:
            msg = "Cannot manipulate Output {id}: It doesn't exist.".format(
                id=output_id)
            self.logger.error(msg)
            return 1, msg

        # Check if output is set up
        if not self.is_setup(output_id):
            msg = "Cannot manipulate Output {id}: Output not set up.".format(
                id=output_id)
            self.logger.error(msg)
            return 1, msg

        #
        # Signaled to turn output on
        #
        if state == 'on':

            # Checks if device is not on and is instructed to turn on
            if ('output_types' in self.dict_outputs[self.output_type[output_id]] and
                    output_type == 'on_off' and
                    not output_is_on):

                # Check if max amperage will be exceeded if turned on
                current_amps = self.current_amp_load()
                max_amps = db_retrieve_table_daemon(
                    Misc, entry='first').max_amps
                if current_amps + self.output_amps[output_id] > max_amps:
                    msg = "Cannot turn output {} ({}) On. If this output " \
                          "turns on, there will be {} amps being drawn, " \
                          "which exceeds the maximum set draw of {} " \
                          "amps.".format(
                            self.output_unique_id[output_id],
                            self.output_name[output_id],
                            current_amps,
                            max_amps)
                    self.logger.warning(msg)
                    return 1, msg

                # Check if time is greater than off_until to allow an output on.
                # If the output is supposed to be off for a minimum duration and that amount
                # of time has not passed, do not allow the output to be turned on.
                off_until_datetime = db_retrieve_table_daemon(
                    Output, unique_id=self.output_unique_id[output_id]).off_until
                if off_until_datetime and off_until_datetime > current_time:
                    off_seconds = (
                        off_until_datetime - current_time).total_seconds()
                    msg = "Output {id} ({name}) instructed to turn on, " \
                          "however the output has been instructed to stay " \
                          "off for {off_sec:.2f} more seconds.".format(
                            id=self.output_unique_id[output_id],
                            name=self.output_name[output_id],
                            off_sec=off_seconds)
                    self.logger.debug(msg)
                    return 1, msg

            # Output type: Volume, set amount
            if (self.output_type[output_id] in self.output_types['volume'] and
                    output_type == 'vol'):
                self.output[output_id].output_switch(state, output_type=output_type, amount=amount)

                msg = "Command sent: Output {id} ({name}) volume: {v:.1f} ".format(
                    id=self.output_unique_id[output_id],
                    name=self.output_name[output_id],
                    v=amount)

            # Output type: PWM, set duty cycle
            elif self.output_type[output_id] in self.output_types['pwm'] and output_type == 'pwm':
                self.output_switch(output_id, 'on', output_type=output_type, duty_cycle=duty_cycle)

                msg = "Command sent: Output {id} ({name}) duty cycle: {dc:.2f} ".format(
                    id=self.output_unique_id[output_id],
                    name=self.output_name[output_id],
                    dc=duty_cycle)

            # Output type: On/Off, set duration for on state
            elif (self.output_type[output_id] in self.output_types['on_off'] and
                    amount != 0 and
                    output_type in ['sec', None]):
                # If a minimum off duration is set, determine the time the output is allowed to turn on again
                if min_off:
                    dt_off_until = current_time + datetime.timedelta(seconds=abs(amount) + min_off)
                    self.set_off_until(dt_off_until, output_id)

                # Output is already on for an amount, update duration on with new end time
                if output_is_on and self.output_on_duration[output_id]:

                    if self.output_on_until[output_id] > current_time:
                        remaining_time = (self.output_on_until[output_id] -
                                          current_time).total_seconds()
                    else:
                        remaining_time = 0

                    time_on = abs(self.output_last_duration[output_id]) - remaining_time
                    msg = "Output {id} ({name}) is already on for an " \
                          "amount of {on:.2f} seconds (with {remain:.2f} " \
                          "seconds remaining). Recording the amount of time " \
                          "the output has been on ({beenon:.2f} sec) and " \
                          "updating the amount to {newon:.2f} " \
                          "seconds.".format(
                            id=self.output_unique_id[output_id],
                            name=self.output_name[output_id],
                            on=abs(self.output_last_duration[output_id]),
                            remain=remaining_time,
                            beenon=time_on,
                            newon=abs(amount))
                    self.logger.debug(msg)
                    self.output_on_until[output_id] = (
                        current_time + datetime.timedelta(seconds=abs(amount)))
                    self.output_last_duration[output_id] = amount

                    # Write the amount the output was ON to the
                    # database at the timestamp it turned ON
                    if time_on > 0:
                        # Make sure the recorded value is recorded negative
                        # if instructed to do so
                        if self.output_last_duration[output_id] < 0:
                            duration_on = float(-time_on)
                        else:
                            duration_on = float(time_on)
                        timestamp = (
                            datetime.datetime.utcnow() -
                            datetime.timedelta(seconds=abs(duration_on)))

                        write_db = threading.Thread(
                            target=write_influxdb_value,
                            args=(self.output_unique_id[output_id],
                                  's',
                                  duration_on,),
                            kwargs={'measure': 'duration_time',
                                    'channel': 0,
                                    'timestamp': timestamp})
                        write_db.start()

                    return 0, msg

                # Output is on, but not for an amount
                elif output_is_on and not self.output_on_duration:

                    self.output_on_duration[output_id] = True
                    self.output_on_until[output_id] = (
                        current_time + datetime.timedelta(seconds=abs(amount)))
                    self.output_last_duration[output_id] = amount
                    msg = "Output {id} ({name}) is currently on without an " \
                          "amount. Turning into an amount of {dur:.1f} " \
                          "seconds.".format(
                            id=self.output_unique_id[output_id],
                            name=self.output_name[output_id],
                            dur=abs(amount))
                    self.logger.debug(msg)
                    return 0, msg

                # Output is not already on
                else:
                    msg = "Output {id} ({name}) on for {dur:.1f} " \
                          "seconds.".format(
                            id=self.output_unique_id[output_id],
                            name=self.output_name[output_id],
                            dur=abs(amount))
                    self.logger.debug(msg)
                    self.output_switch(output_id, 'on', output_type=output_type, amount=amount)
                    self.output_on_until[output_id] = (
                        current_time + datetime.timedelta(seconds=abs(amount)))
                    self.output_last_duration[output_id] = amount
                    self.output_on_duration[output_id] = True

            # No duration specific, so just turn output on
            elif ('output_types' in self.dict_outputs[self.output_type[output_id]] and
                    'on_off' in self.dict_outputs[self.output_type[output_id]]['output_types'] and
                    (amount is None or amount == 0) and
                    output_type in ['sec', None]):

                # Don't turn on if already on, except if it can be forced on
                if output_is_on and not self.output_force_command[output_id]:
                    msg = "Output {id} ({name}) is already on.".format(
                            id=self.output_unique_id[output_id],
                            name=self.output_name[output_id])
                    self.logger.debug(msg)
                    return 1, msg
                else:
                    # Record the time the output was turned on in order to
                    # calculate and log the total amount is was on, when
                    # it eventually turns off.
                    if not self.output_time_turned_on[output_id]:
                        self.output_time_turned_on[output_id] = current_time
                    msg = "Output {id} ({name}) ON at {timeon}.".format(
                            id=self.output_unique_id[output_id],
                            name=self.output_name[output_id],
                            timeon=self.output_time_turned_on[output_id])
                    self.logger.debug(msg)
                    self.output_switch(output_id, 'on', output_type=output_type)

        #
        # Signaled to turn output off
        #
        elif state == 'off':

            self.output_switch(output_id, 'off', output_type=output_type)

            timestamp = datetime.datetime.fromtimestamp(
                time.time()).strftime('%Y-%m-%d %H:%M:%S')
            msg = "Output {id} ({name}) OFF at {timeoff}.".format(
                id=self.output_unique_id[output_id],
                name=self.output_name[output_id],
                timeoff=timestamp)
            self.logger.debug(msg)

            # Write output amount to database
            if (self.output_time_turned_on[output_id] is not None or
                    self.output_on_duration[output_id]):

                duration_sec = None
                timestamp = None
                if self.output_on_duration[output_id]:
                    remaining_time = 0

                    if self.output_on_until[output_id] > current_time:
                        remaining_time = (self.output_on_until[output_id] -
                                          current_time).total_seconds()
                    duration_sec = (abs(self.output_last_duration[output_id]) -
                                    remaining_time)
                    timestamp = (datetime.datetime.utcnow() -
                                 datetime.timedelta(seconds=duration_sec))

                    # Store negative amount if a negative amount is received
                    if self.output_last_duration[output_id] < 0:
                        duration_sec = -duration_sec

                    self.output_on_duration[output_id] = False
                    self.output_on_until[output_id] = current_time

                if self.output_time_turned_on[output_id] is not None:
                    # Write the amount the output was ON to the database
                    # at the timestamp it turned ON
                    duration_sec = (current_time -
                                    self.output_time_turned_on[output_id]).total_seconds()
                    timestamp = (datetime.datetime.utcnow() -
                                 datetime.timedelta(seconds=duration_sec))
                    self.output_time_turned_on[output_id] = None

                write_db = threading.Thread(
                    target=write_influxdb_value,
                    args=(self.output_unique_id[output_id],
                          's',
                          duration_sec,),
                    kwargs={'measure': 'duration_time',
                            'channel': 0,
                            'timestamp': timestamp})
                write_db.start()

            self.output_off_triggered[output_id] = False

        if trigger_conditionals:
            self.check_triggers(output_id, on_duration=amount)

        return 0, msg

    def output_switch(self, output_id, state, output_type=None, amount=None, duty_cycle=None):
        """Instruct the output module to modulate the output"""
        if state not in ['on', 1, True, 'off', 0, False]:
            return 1, 'state not "on", 1, True, "off", 0, or False'
        elif state in ['on', 1, True]:
            state = 'on'
        elif state in ['off', 0, False]:
            state = 'off'
        self.output[output_id].output_switch(state, output_type=output_type, amount=amount, duty_cycle=duty_cycle)

    def check_triggers(self, output_id, on_duration=None):
        """
        This function is executed whenever an output is turned on or off
        It is responsible for executing Output Triggers
        """
        #
        # Check On/Off Outputs
        #
        trigger_output = db_retrieve_table_daemon(Trigger)
        trigger_output = trigger_output.filter(
            Trigger.trigger_type == 'trigger_output')
        trigger_output = trigger_output.filter(
            Trigger.unique_id_1 == output_id)
        trigger_output = trigger_output.filter(
            Trigger.is_activated == True)

        # Find any Output Triggers with the output_id of the output that
        # just changed its state
        if self.is_on(output_id):
            trigger_output = trigger_output.filter(
                or_(Trigger.output_state == 'on_duration_none',
                    Trigger.output_state == 'on_duration_any',
                    Trigger.output_state == 'on_duration_none_any',
                    Trigger.output_state == 'on_duration_equal',
                    Trigger.output_state == 'on_duration_greater_than',
                    Trigger.output_state == 'on_duration_equal_greater_than',
                    Trigger.output_state == 'on_duration_less_than',
                    Trigger.output_state == 'on_duration_equal_less_than'))

            on_duration_none = and_(
                Trigger.output_state == 'on_duration_none',
                on_duration == 0.0)

            on_duration_any = and_(
                Trigger.output_state == 'on_duration_any',
                bool(on_duration))

            on_duration_none_any = Trigger.output_state == 'on_duration_none_any'

            on_duration_equal = and_(
                Trigger.output_state == 'on_duration_equal',
                Trigger.output_duration == on_duration)

            on_duration_greater_than = and_(
                Trigger.output_state == 'on_duration_greater_than',
                on_duration > Trigger.output_duration)

            on_duration_equal_greater_than = and_(
                Trigger.output_state == 'on_duration_equal_greater_than',
                on_duration >= Trigger.output_duration)

            on_duration_less_than = and_(
                Trigger.output_state == 'on_duration_less_than',
                on_duration < Trigger.output_duration)

            on_duration_equal_less_than = and_(
                Trigger.output_state == 'on_duration_equal_less_than',
                on_duration <= Trigger.output_duration)

            trigger_output = trigger_output.filter(
                or_(on_duration_none,
                    on_duration_any,
                    on_duration_none_any,
                    on_duration_equal,
                    on_duration_greater_than,
                    on_duration_equal_greater_than,
                    on_duration_less_than,
                    on_duration_equal_less_than))
        else:
            trigger_output = trigger_output.filter(
                Trigger.output_state == 'off')

        # Execute the Trigger Actions for each Output Trigger
        # for this particular Output device
        for each_trigger in trigger_output.all():
            timestamp = datetime.datetime.fromtimestamp(
                time.time()).strftime('%Y-%m-%d %H:%M:%S')
            message = "{ts}\n[Trigger {cid} ({cname})] Output {oid} ({name}) {state}".format(
                ts=timestamp,
                cid=each_trigger.unique_id.split('-')[0],
                cname=each_trigger.name,
                name=each_trigger.name,
                oid=output_id,
                state=each_trigger.output_state)

            self.control.trigger_all_actions(
                each_trigger.unique_id, message=message)

        #
        # Check PWM Outputs
        #
        trigger_output_pwm = db_retrieve_table_daemon(Trigger)
        trigger_output_pwm = trigger_output_pwm.filter(
            Trigger.trigger_type == 'trigger_output_pwm')
        trigger_output_pwm = trigger_output_pwm.filter(
            Trigger.unique_id_1 == output_id)
        trigger_output_pwm = trigger_output_pwm.filter(
            Trigger.is_activated == True)

        # Execute the Trigger Actions for each Output Trigger
        # for this particular Output device
        for each_trigger in trigger_output_pwm.all():
            trigger_trigger = False
            duty_cycle = self.output_state(output_id)

            if duty_cycle == 'off':
                if (
                        (each_trigger.output_state == 'equal' and
                         each_trigger.output_duty_cycle == 0) or
                        (each_trigger.output_state == 'below' and
                         each_trigger.output_duty_cycle != 0)
                        ):
                    trigger_trigger = True
            elif (
                    (each_trigger.output_state == 'above' and
                     duty_cycle > each_trigger.output_duty_cycle) or
                    (each_trigger.output_state == 'below' and
                     duty_cycle < each_trigger.output_duty_cycle) or
                    (each_trigger.output_state == 'equal' and
                     duty_cycle == each_trigger.output_duty_cycle)
                    ):
                trigger_trigger = True

            if not trigger_trigger:
                continue

            timestamp = datetime.datetime.fromtimestamp(
                time.time()).strftime('%Y-%m-%d %H:%M:%S')
            message = "{ts}\n[Trigger {cid} ({cname})] Output {oid} " \
                      "({name}) Duty Cycle {actual_dc} {state} {duty_cycle}".format(
                        ts=timestamp,
                        cid=each_trigger.unique_id.split('-')[0],
                        cname=each_trigger.name,
                        name=each_trigger.name,
                        oid=output_id,
                        actual_dc=duty_cycle,
                        state=each_trigger.output_state,
                        duty_cycle=each_trigger.output_duty_cycle)

            # Check triggers whenever an output is manipulated
            self.control.trigger_all_actions(
                each_trigger.unique_id, message=message)

    def output_sec_currently_on(self, output_id):
        """ Return how many seconds an output has been currently on for """
        if not self.is_on(output_id):
            return 0
        else:
            now = datetime.datetime.now()
            sec_currently_on = 0
            if self.output_on_duration[output_id]:
                left = 0
                if self.output_on_until[output_id] > now:
                    left = (self.output_on_until[output_id] - now).total_seconds()
                sec_currently_on = (
                    abs(self.output_last_duration[output_id]) - left)
            elif self.output_time_turned_on[output_id]:
                sec_currently_on = (
                    now - self.output_time_turned_on[output_id]).total_seconds()
            return sec_currently_on

    def output_setup(self, action, output_id):
        """ Add, delete, or modify a specific output """
        if action in ['Add', 'Modify']:
            return self.add_mod_output(output_id)
        elif action == 'Delete':
            return self.del_output(output_id)
        else:
            return [1, 'Invalid output_setup action']

    def current_amp_load(self):
        """
        Calculate the sum of amps drawn from all outputs currently on

        :return: total Amperage draw
        :rtype: float
        """
        amp_load = 0.0
        for each_output_id, each_output_amps in self.output_amps.items():
            if self.is_on(each_output_id) and each_output_amps:
                amp_load += each_output_amps
        return amp_load

    def output_state(self, output_id):
        """
        Return the state of an output

        :param output_id: Unique ID for the output
        :type output_id: str

        :return: "on", "off", or duty cycle (for PWM output)
        :rtype: str
        """
        if output_id in self.output_type:
            state = self.is_on(output_id)
            if state is not None:
                if self.output_type[output_id] in self.output_types['pwm']:
                    if state:
                        return state
                    elif state == 0 or state is False:
                        return 'off'
                elif state:
                    return 'on'
                else:
                    return 'off'

    def output_states_all(self):
        """
        Return a dictionary of all output states
        :rtype: dict
        """
        states = []
        for output_id in self.output_unique_id:
            states.append({
                'unique_id': output_id,
                'state': self.output_state(output_id)
            })
        return states

    def is_on(self, output_id):
        """
        CHeck if the output is on or off

        :param output_id: Unique ID for each output
        :type output_id: str

        :return: Whether the output is currently On (True) or Off (False)
        :rtype: bool
        """
        try:
            if ('on_state_internally_handled' in self.dict_outputs[self.output_type[output_id]] and
                    self.dict_outputs[self.output_type[output_id]]['on_state_internally_handled']):
                if self.output_time_turned_on[output_id] or self.output_on_duration[output_id]:
                    return True
                else:
                    return False
            else:
                return self.output[output_id].is_on()
        except KeyError:
            self.logger.error("Output not found. This indicates the output controller either didn't properly "
                              "start or it experienced a fatal error.")
        except Exception:
            self.logger.exception("is_on() exception")

    def is_setup(self, output_id):
        """
        This function checks to see if the output is set up

        :param output_id: Unique ID for each output
        :type output_id: str

        :return: Is it safe to manipulate this output?
        :rtype: bool
        """
        try:
            return self.output[output_id].is_setup()
        except Exception:
            self.logger.exception("is_setup() exception")

    def set_off_until(self, dt_off_until, output_id):
        """ Save the datetime of when the output is supposed to stay off until """
        with session_scope(MYCODO_DB_PATH) as new_session:
            mod_cont = new_session.query(Output).filter(
                Output.unique_id == self.output_unique_id[output_id]).first()
            mod_cont.off_until = dt_off_until
            new_session.commit()

    def custom_button_exec_function(self, output_id, button_id, args_dict):
        """Execute function from custom action button press"""
        self.button_args_dict = args_dict
        self.button_output_id = output_id
        self.button_pressed = button_id
        return 0, "Command sent to Output Controller"
