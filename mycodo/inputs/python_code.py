# coding=utf-8
import importlib.util
import textwrap

import copy
import os
from flask import Markup
from flask import flash

from mycodo.config import PATH_PYTHON_CODE_USER
from mycodo.databases.models import DeviceMeasurements
from mycodo.inputs.base_input import AbstractInput
from mycodo.utils.database import db_retrieve_table_daemon
from mycodo.utils.system_pi import assure_path_exists
from mycodo.utils.system_pi import cmd_output
from mycodo.utils.system_pi import set_user_grp


def format_pre_statement(unique_id, measure_info):
    """ Generate the code to place/execute before the user code """
    pre_statement = """import os
import sys
sys.path.append(os.path.abspath('/var/mycodo-root'))

from mycodo.mycodo_client import DaemonControl
from mycodo.utils.influx import add_measurements_influxdb

control = DaemonControl()

measurement_info = {measure_info}

def store_measurement(channel=None, measurement=None):
    if None in [channel, measurement]:
        return
    measure = {{channel: {{}}}}
    measure[channel]['measurement'] = measurement_info[channel]['measurement']
    measure[channel]['unit'] = measurement_info[channel]['unit']
    measure[channel]['value'] = measurement
    add_measurements_influxdb('{unique_id}', measure)

""".format(unique_id=unique_id, measure_info=measure_info)
    return pre_statement


def execute_at_creation(unique_id, cmd_command, dict_inputs):
    error = []
    pre_statement_run = """import os
import sys
sys.path.append(os.path.abspath('/var/mycodo-root'))
from mycodo.mycodo_client import DaemonControl
from mycodo.utils.influx import add_measurements_influxdb
control = DaemonControl()

class PythonInputRun:
    def __init__(self, logger, input_id, measurement_info):
        self.logger = logger
        self.input_id = input_id
        self.measurement_info = measurement_info

    def store_measurement(self, channel=None, measurement=None, timestamp=None):
        if None in [channel, measurement]:
            return
        measure = {channel: {}}
        measure[channel]['measurement'] = self.measurement_info[channel]['measurement']
        measure[channel]['unit'] = self.measurement_info[channel]['unit']
        measure[channel]['value'] = measurement
        if timestamp:
            measure[channel]['timestamp_utc'] = timestamp
        add_measurements_influxdb(self.input_id, measure)

    def python_code_run(self):
"""
    indented_code = textwrap.indent(cmd_command, ' ' * 8)
    input_python_code_run = pre_statement_run + indented_code

    assure_path_exists(PATH_PYTHON_CODE_USER)
    file_run = '{}/input_python_code_{}.py'.format(
        PATH_PYTHON_CODE_USER, unique_id)
    with open(file_run, 'w') as fw:
        fw.write('{}\n'.format(input_python_code_run))
        fw.close()
    set_user_grp(file_run, 'mycodo', 'mycodo')

    return error, (input_python_code_run, file_run)


def test_before_saving(mod_input, request_form):
    """
    Function to run when the Input is saved to evaluate the Python 3 code using pylint3
    :param mod_input: The WTForms object containing the form data submitted by the web GUI
    :param request_form: The custom_options form input data (if it exists)
    :return: tuple of (all_passed, error, mod_input) variables
    """
    all_passed = True

    error, (input_python_code_run, file_run) = execute_at_creation(
        mod_input.unique_id, mod_input.cmd_command, None)

    # Only add strings to this list to prevent options from being saved.
    # Use flash('my error message', 'error') to show errors but allow options
    # to save.
    error = []

    if len(input_python_code_run.splitlines()) > 999:
        error.append("Too many lines in code. Reduce code to less than 1000 lines.")

    lines_code = ''
    for line_num, each_line in enumerate(input_python_code_run.splitlines(), 1):
        if len(str(line_num)) == 3:
            line_spacing = ''
        elif len(str(line_num)) == 2:
            line_spacing = ' '
        else:
            line_spacing = '  '
        lines_code += '{sp}{ln}: {line}\n'.format(
            sp=line_spacing,
            ln=line_num,
            line=each_line)

    cmd_test = 'export PYTHONPATH=$PYTHONPATH:/var/mycodo-root && ' \
               'pylint3 -d I,W0621,C0103,C0111,C0301,C0327,C0410,C0413 {path}'.format(
        path=file_run)
    cmd_out, _, cmd_status = cmd_output(cmd_test)

    message = Markup(
        '<pre>\n\n'
        'Full Python Code Input code:\n\n{code}\n\n'
        'Python Code Input code analysis:\n\n{report}'
        '</pre>'.format(
            code=lines_code, report=cmd_out.decode("utf-8")))
    if cmd_status:
        flash('Error(s) were found while evaluating your code. Review '
              'the error(s), below, and fix them before activating your '
              'Input.', 'error')
        flash(message, 'error')
    else:
        flash(
            "No errors were found while evaluating your code. However, "
            "this doesn't mean your code will perform as expected. "
            "Review your code for issues and test your Input "
            "before putting it into a production environment.", 'success')
        flash(message, 'success')

    return all_passed, error, mod_input


# Measurements
measurements_dict = {}

# Input information
INPUT_INFORMATION = {
    'input_name_unique': 'PythonCode',
    'input_manufacturer': 'Linux',
    'input_name': 'Python 3 Code',
    'measurements_name': 'Store Value(s)',
    'measurements_dict': measurements_dict,
    'measurements_variable_amount': True,

    'options_enabled': [
        'measurements_select',
        'period',
        'cmd_command',
        'pre_output'
    ],
    'options_disabled': ['interface'],

    'execute_at_creation': execute_at_creation,
    'test_before_saving': test_before_saving,

    'interfaces': ['Mycodo'],
    'cmd_command': """import random  # Import any external libraries

# Get measurements/values (for example, these are randomly-generated numbers)
random_value_channel_0 = random.uniform(10.0, 100.0)

# Store measurements in database (must specify the channel and measurement)
self.store_measurement(channel=0, measurement=random_value_channel_0)"""
}


class InputModule(AbstractInput):
    """ A sensor support class that returns a value from a command """

    def __init__(self, input_dev, testing=False):
        super(InputModule, self).__init__(input_dev, testing=testing, name=__name__)

        self.python_code = None

        if not testing:
            self.initialize_input()

    def initialize_input(self):
        self.unique_id = self.input_dev.unique_id

        self.measure_info = {}
        self.device_measurements = db_retrieve_table_daemon(
            DeviceMeasurements).filter(
            DeviceMeasurements.device_id == self.input_dev.unique_id)
        for each_measure in self.device_measurements.all():
            self.measure_info[each_measure.channel] = {}
            self.measure_info[each_measure.channel]['unit'] = each_measure.unit
            self.measure_info[each_measure.channel]['measurement'] = each_measure.measurement

        self.python_code = self.input_dev.cmd_command

    def get_measurement(self):
        """ Determine if the return value of the command is a number """
        if not self.python_code:
            self.logger.error("Input not set up")
            return

        self.return_dict = copy.deepcopy(measurements_dict)

        file_run = '{}/input_python_code_{}.py'.format(PATH_PYTHON_CODE_USER, self.unique_id)

        # If the file to execute doesn't exist, generate it
        if not os.path.exists(file_run):
            execute_at_creation(self.unique_id, self.python_code, None)

        with open(file_run, 'r') as file:
            self.logger.debug("Python Code:\n{}".format(file.read()))

        module_name = "mycodo.input.python_code_exec_{}".format(os.path.basename(file_run).split('.')[0])
        spec = importlib.util.spec_from_file_location(module_name, file_run)
        conditional_run = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(conditional_run)
        run = conditional_run.PythonInputRun(self.logger, self.unique_id, self.measure_info)
        try:
            run.python_code_run()
        except Exception:
            self.logger.exception(1)
