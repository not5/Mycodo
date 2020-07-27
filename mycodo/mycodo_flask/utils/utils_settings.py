# -*- coding: utf-8 -*-
import logging
import subprocess
import time
import traceback

import bcrypt
import flask_login
import os
import re
import sqlalchemy
from flask import flash
from flask import redirect
from flask import url_for
from flask_babel import gettext
from sqlalchemy import and_
from sqlalchemy import or_

from mycodo.config import DAEMON_LOG_FILE
from mycodo.config import DEPENDENCY_INIT_FILE
from mycodo.config import INSTALL_DIRECTORY
from mycodo.config import PATH_CONTROLLERS_CUSTOM
from mycodo.config import PATH_INPUTS_CUSTOM
from mycodo.config import PATH_OUTPUTS_CUSTOM
from mycodo.config import UPGRADE_INIT_FILE
from mycodo.config_devices_units import MEASUREMENTS
from mycodo.config_devices_units import UNITS
from mycodo.config_translations import TRANSLATIONS
from mycodo.databases import set_api_key
from mycodo.databases.models import Conversion
from mycodo.databases.models import CustomController
from mycodo.databases.models import Dashboard
from mycodo.databases.models import DeviceMeasurements
from mycodo.databases.models import DisplayOrder
from mycodo.databases.models import Input
from mycodo.databases.models import Math
from mycodo.databases.models import Measurement
from mycodo.databases.models import Misc
from mycodo.databases.models import NoteTags
from mycodo.databases.models import Notes
from mycodo.databases.models import Output
from mycodo.databases.models import PID
from mycodo.databases.models import Role
from mycodo.databases.models import SMTP
from mycodo.databases.models import MQTT
from mycodo.databases.models import Unit
from mycodo.databases.models import User
from mycodo.databases.models import Widget
from mycodo.mycodo_client import DaemonControl
from mycodo.mycodo_flask.extensions import db
from mycodo.mycodo_flask.utils import utils_general
from mycodo.mycodo_flask.utils.utils_general import choices_measurements
from mycodo.mycodo_flask.utils.utils_general import choices_units
from mycodo.mycodo_flask.utils.utils_general import controller_activate_deactivate
from mycodo.mycodo_flask.utils.utils_general import delete_entry_with_id
from mycodo.mycodo_flask.utils.utils_general import flash_form_errors
from mycodo.mycodo_flask.utils.utils_general import flash_success_errors
from mycodo.mycodo_flask.utils.utils_input import input_deactivate_associated_controllers
from mycodo.utils.controllers import parse_controller_information
from mycodo.utils.database import db_retrieve_table
from mycodo.utils.inputs import parse_input_information
from mycodo.utils.modules import load_module_from_file
from mycodo.utils.outputs import parse_output_information
from mycodo.utils.send_data import send_email
from mycodo.utils.send_data import pub_mqtt
from mycodo.utils.system_pi import all_conversions
from mycodo.utils.system_pi import assure_path_exists
from mycodo.utils.system_pi import cmd_output
from mycodo.utils.utils import test_password
from mycodo.utils.utils import test_username

logger = logging.getLogger(__name__)


#
# User manipulation
#

def user_roles(form):
    action = None
    if form.add_role.data:
        action = TRANSLATIONS['add']['title']
    elif form.save_role.data:
        action = TRANSLATIONS['modify']['title']
    elif form.delete_role.data:
        action = TRANSLATIONS['delete']['title']

    action = '{action} {controller}'.format(
        action=action,
        controller=gettext("User Role"))
    error = []

    if not error:
        if form.add_role.data:
            new_role = Role()
            new_role.name = form.name.data
            new_role.view_logs = form.view_logs.data
            new_role.view_camera = form.view_camera.data
            new_role.view_stats = form.view_stats.data
            new_role.view_settings = form.view_settings.data
            new_role.edit_users = form.edit_users.data
            new_role.edit_settings = form.edit_settings.data
            new_role.edit_controllers = form.edit_controllers.data
            new_role.reset_password = form.reset_password.data
            try:
                new_role.save()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)
        elif form.save_role.data:
            mod_role = Role.query.filter(
                Role.unique_id == form.role_id.data).first()
            mod_role.view_logs = form.view_logs.data
            mod_role.view_camera = form.view_camera.data
            mod_role.view_stats = form.view_stats.data
            mod_role.view_settings = form.view_settings.data
            mod_role.edit_users = form.edit_users.data
            mod_role.edit_settings = form.edit_settings.data
            mod_role.edit_controllers = form.edit_controllers.data
            mod_role.reset_password = form.reset_password.data
            db.session.commit()
        elif form.delete_role.data:
            user = User().query.filter(User.role_id == form.role_id.data)
            if user.first().id == 1:
                error.append("Cannot delete user: this user is protected")
            if user.count():
                error.append(
                    "Cannot delete role if it is assigned to a user. "
                    "Change the user to another role and try again.")
            else:
                delete_entry_with_id(Role, form.role_id.data)
    flash_success_errors(
        error, action, url_for('routes_settings.settings_users'))


def user_add(form):
    action = '{action} {controller} {user}'.format(
        action=TRANSLATIONS['add']['title'],
        controller=TRANSLATIONS['user']['title'],
        user=form.user_name.data.lower())
    error = []

    if form.validate():
        new_user = User()
        new_user.name = form.user_name.data.lower()
        if not test_username(new_user.name):
            error.append(gettext(
                "Invalid user name. Must be between 2 and 64 characters "
                "and only contain letters and numbers."))

        new_user.email = form.email.data
        if User.query.filter_by(email=new_user.email).count():
            error.append(gettext(
                "Another user already has that email address."))

        if not test_password(form.password_new.data):
            error.append(gettext(
                "Invalid password. Must be between 6 and 64 characters "
                "and only contain letters, numbers, and symbols."))

        if form.password_new.data != form.password_repeat.data:
            error.append(gettext("Passwords do not match. Please try again."))

        if not error:
            new_user.set_password(form.password_new.data)
            role = Role.query.filter(
                Role.name == form.addRole.data).first()
            new_user.role_id = role.id
            new_user.theme = form.theme.data
            try:
                new_user.save()
            except sqlalchemy.exc.OperationalError as except_msg:
                error.append(except_msg)
            except sqlalchemy.exc.IntegrityError as except_msg:
                error.append(except_msg)

        flash_success_errors(
            error, action, url_for('routes_settings.settings_users'))
    else:
        flash_form_errors(form)


def generate_api_key(form):
    mod_user = User.query.filter(
        User.unique_id == form.user_id.data).first()
    action = '{action} {controller} {user}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=TRANSLATIONS['user']['title'],
        user=mod_user.name)
    error = []

    try:
        mod_user = User.query.filter(
            User.unique_id == form.user_id.data).first()
        mod_user.api_key = set_api_key(128)
        db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_users'))


def user_mod(form):
    mod_user = User.query.filter(
        User.unique_id == form.user_id.data).first()
    action = '{action} {controller} {user}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=TRANSLATIONS['user']['title'],
        user=mod_user.name)
    error = []

    try:
        mod_user = User.query.filter(
            User.unique_id == form.user_id.data).first()
        mod_user.email = form.email.data
        # Only change the password if it's entered in the form
        logout_user = False
        if form.password_new.data != '':
            if not utils_general.user_has_permission('reset_password'):
                error.append("Cannot change user password")
            if not test_password(form.password_new.data):
                error.append(gettext("Invalid password"))
            if form.password_new.data != form.password_repeat.data:
                error.append(gettext(
                    "Passwords do not match. Please try again."))
            mod_user.password_hash = bcrypt.hashpw(
                form.password_new.data.encode('utf-8'),
                bcrypt.gensalt())
            if flask_login.current_user.id == form.user_id.data:
                logout_user = True

        current_user_name = User.query.filter(
            User.unique_id == form.user_id.data).first().name
        if (mod_user.role_id == 1 and
                mod_user.role_id != form.role_id.data and
                flask_login.current_user.name == current_user_name):
            error.append(
                "Cannot change currently-logged in user's role from Admin")

        if not error:
            mod_user.role_id = form.role_id.data
            mod_user.theme = form.theme.data
            db.session.commit()
            if logout_user:
                return 'logout'
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_users'))


def user_del(form):
    """ Delete user from SQL database """
    user_name = User.query.filter(
        User.unique_id == form.user_id.data).first().name
    action = '{action} {controller} {user}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=TRANSLATIONS['user']['title'],
        user=user_name)
    error = []

    if form.user_id.data == flask_login.current_user.id:
        error.append("Cannot delete the currently-logged in user")

    if not error:
        try:
            user = User.query.filter(
                User.unique_id == form.user_id.data).first()
            user.delete()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_users'))


#
# Settings modifications
#

def settings_general_mod(form):
    """ Modify General settings """
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=gettext("General Settings"))
    error = []

    if form.validate():
        if (form.output_usage_report_span.data == 'monthly' and
                not 0 < form.output_usage_report_day.data < 29):
            error.append("Day Options: Daily: 1-7 (1=Monday), Monthly: 1-28")
        elif (form.output_usage_report_span.data == 'weekly' and
                not 0 < form.output_usage_report_day.data < 8):
            error.append("Day Options: Daily: 1-7 (1=Monday), Monthly: 1-28")

        if not error:
            try:
                mod_misc = Misc.query.first()

                force_https = mod_misc.force_https
                mod_misc.force_https = form.force_https.data
                mod_misc.rpyc_timeout = form.rpyc_timeout.data
                mod_misc.daemon_debug_mode = form.daemon_debug_mode.data
                mod_misc.hide_alert_success = form.hide_success.data
                mod_misc.hide_alert_info = form.hide_info.data
                mod_misc.hide_alert_warning = form.hide_warning.data
                mod_misc.hide_tooltips = form.hide_tooltips.data
                mod_misc.grid_cell_height = form.grid_cell_height.data
                mod_misc.max_amps = form.max_amps.data
                mod_misc.output_usage_volts = form.output_stats_volts.data
                mod_misc.output_usage_cost = form.output_stats_cost.data
                mod_misc.output_usage_currency = form.output_stats_currency.data
                mod_misc.output_usage_dayofmonth = form.output_stats_day_month.data
                mod_misc.output_usage_report_gen = form.output_usage_report_gen.data
                mod_misc.output_usage_report_span = form.output_usage_report_span.data
                mod_misc.output_usage_report_day = form.output_usage_report_day.data
                mod_misc.output_usage_report_hour = form.output_usage_report_hour.data
                mod_misc.stats_opt_out = form.stats_opt_out.data
                mod_misc.enable_upgrade_check = form.enable_upgrade_check.data
                mod_misc.net_test_ip = form.net_test_ip.data
                mod_misc.net_test_port = form.net_test_port.data
                mod_misc.net_test_timeout = form.net_test_timeout.data

                mod_user = User.query.filter(
                    User.id == flask_login.current_user.id).first()
                mod_user.landing_page = form.landing_page.data
                mod_user.language = form.language.data

                db.session.commit()
                control = DaemonControl()
                control.refresh_daemon_misc_settings()

                if force_https != form.force_https.data:
                    # Force HTTPS option changed.
                    # Reload web server with new settings.
                    wsgi_file = '{inst_dir}/mycodo_flask.wsgi'.format(
                        inst_dir=INSTALL_DIRECTORY)
                    with open(wsgi_file, 'a'):
                        os.utime(wsgi_file, None)

            except Exception as except_msg:
                error.append(except_msg)

        flash_success_errors(
            error, action, url_for('routes_settings.settings_general'))
    else:
        flash_form_errors(form)


def settings_controller_import(form):
    """
    Receive an controller module file, check it for errors, add it to Mycodo controller list
    """
    action = '{action} {controller}'.format(
        action=gettext("Import"),
        controller=TRANSLATIONS['controller']['title'])
    error = []

    controller_info = None

    try:
        # correct_format = 'Mycodo_MYCODOVERSION_Settings_DBVERSION_HOST_DATETIME.zip'
        install_dir = os.path.abspath(INSTALL_DIRECTORY)
        tmp_directory = os.path.join(install_dir, 'mycodo/controllers/tmp_controllers')
        assure_path_exists(tmp_directory)
        assure_path_exists(PATH_CONTROLLERS_CUSTOM)
        tmp_name = 'tmp_controller_testing.py'
        full_path_tmp = os.path.join(tmp_directory, tmp_name)

        if not form.import_controller_file.data:
            error.append('No file present')
        elif form.import_controller_file.data.filename == '':
            error.append('No file name')
        else:
            form.import_controller_file.data.save(full_path_tmp)

        try:
            controller_info = load_module_from_file(full_path_tmp, 'controllers')
            if not hasattr(controller_info, 'CONTROLLER_INFORMATION'):
                error.append("Could not load CONTROLLER_INFORMATION dictionary from "
                             "the uploaded controller module")
        except Exception:
            error.append("Could not load uploaded file as a python module:\n"
                         "{}".format(traceback.format_exc()))

        dict_controllers = parse_controller_information()
        list_controllers = []
        for each_key in dict_controllers.keys():
            list_controllers.append(each_key.lower())

        if not error:
            if 'controller_name_unique' not in controller_info.CONTROLLER_INFORMATION:
                error.append(
                    "'controller_name_unique' not found in "
                    "CONTROLLER_INFORMATION dictionary")
            elif controller_info.CONTROLLER_INFORMATION['controller_name_unique'] == '':
                error.append("'controller_name_unique' is empty")
            elif controller_info.CONTROLLER_INFORMATION['controller_name_unique'].lower() in list_controllers:
                error.append(
                    "'controller_name_unique' is not unique, there "
                    "is already an controller with that name ({})".format(
                        controller_info.CONTROLLER_INFORMATION['controller_name_unique']))

            if 'controller_name' not in controller_info.CONTROLLER_INFORMATION:
                error.append(
                    "'controller_name' not found in CONTROLLER_INFORMATION dictionary")
            elif controller_info.CONTROLLER_INFORMATION['controller_name'] == '':
                error.append("'controller_name' is empty")

            if 'dependencies_module' in controller_info.CONTROLLER_INFORMATION:
                if not isinstance(controller_info.CONTROLLER_INFORMATION['dependencies_module'], list):
                    error.append("'dependencies_module' must be a list of tuples")
                else:
                    for each_dep in controller_info.CONTROLLER_INFORMATION['dependencies_module']:
                        if not isinstance(each_dep, tuple):
                            error.append(
                                "'dependencies_module' must be a list of "
                                "tuples")
                        elif len(each_dep) != 3:
                            error.append(
                                "'dependencies_module': tuples in list must "
                                "have 3 items")
                        elif not each_dep[0] or not each_dep[1] or not each_dep[2]:
                            error.append(
                                "'dependencies_module': tuples in list must "
                                "not be empty")
                        elif each_dep[0] not in ['internal', 'pip-pypi', 'pip-git', 'apt']:
                            error.append(
                                "'dependencies_module': first in tuple "
                                "must be 'internal', 'pip-pypi', 'pip-git', "
                                "or 'apt'")

        if not error:
            # Determine filename
            unique_name = '{}.py'.format(controller_info.CONTROLLER_INFORMATION['controller_name_unique'].lower())

            # Move module from temp directory to custom_controller directory
            full_path_final = os.path.join(PATH_CONTROLLERS_CUSTOM, unique_name)
            os.rename(full_path_tmp, full_path_final)

            # Reload frontend to refresh the controllers
            cmd = '{path}/mycodo/scripts/mycodo_wrapper frontend_reload 2>&1'.format(
                path=install_dir)
            subprocess.Popen(cmd, shell=True)
            flash('Frontend reloaded to scan for new Controller Modules', 'success')

    except Exception as err:
        error.append("Exception: {}".format(err))

    flash_success_errors(error, action, url_for('routes_settings.settings_controller'))


def settings_controller_delete(form):
    action = '{action} {controller}'.format(
        action=gettext("Import"),
        controller=TRANSLATIONS['controller']['title'])
    error = []

    controller_device_name = form.controller_id.data
    file_name = '{}.py'.format(form.controller_id.data.lower())
    full_path_file = os.path.join(PATH_CONTROLLERS_CUSTOM, file_name)

    if not error:
        # Check if any Controller entries exist
        controller_dev = CustomController.query.filter(
            CustomController.device == controller_device_name).count()
        if controller_dev:
            error.append("Cannot delete Controller Module if there are still "
                         "Controller entries using it. Deactivate and delete all "
                         "Controller entries that use this module before deleting "
                         "the module.")

    if not error:
        os.remove(full_path_file)

        # Reload frontend to refresh the controllers
        cmd = '{path}/mycodo/scripts/mycodo_wrapper frontend_reload 2>&1'.format(
            path=os.path.abspath(INSTALL_DIRECTORY))
        subprocess.Popen(cmd, shell=True)
        flash('Frontend reloaded to scan for new Controller Modules', 'success')

    flash_success_errors(error, action, url_for('routes_settings.settings_controller'))


def settings_input_import(form):
    """
    Receive an input module file, check it for errors, add it to Mycodo input list
    """
    action = '{action} {controller}'.format(
        action=gettext("Import"),
        controller=TRANSLATIONS['input']['title'])
    error = []

    input_info = None

    try:
        # correct_format = 'Mycodo_MYCODOVERSION_Settings_DBVERSION_HOST_DATETIME.zip'
        install_dir = os.path.abspath(INSTALL_DIRECTORY)
        tmp_directory = os.path.join(install_dir, 'mycodo/inputs/tmp_inputs')
        assure_path_exists(tmp_directory)
        assure_path_exists(PATH_INPUTS_CUSTOM)
        tmp_name = 'tmp_input_testing.py'
        full_path_tmp = os.path.join(tmp_directory, tmp_name)

        if not form.import_input_file.data:
            error.append('No file present')
        elif form.import_input_file.data.filename == '':
            error.append('No file name')
        else:
            form.import_input_file.data.save(full_path_tmp)

        try:
            input_info = load_module_from_file(full_path_tmp, 'inputs')
            if not hasattr(input_info, 'INPUT_INFORMATION'):
                error.append("Could not load INPUT_INFORMATION dictionary from "
                             "the uploaded input module")
        except Exception:
            error.append("Could not load uploaded file as a python module:\n"
                         "{}".format(traceback.format_exc()))

        dict_inputs = parse_input_information()
        list_inputs = []
        for each_key in dict_inputs.keys():
            list_inputs.append(each_key.lower())

        if not error:
            if 'input_name_unique' not in input_info.INPUT_INFORMATION:
                error.append(
                    "'input_name_unique' not found in "
                    "INPUT_INFORMATION dictionary")
            elif input_info.INPUT_INFORMATION['input_name_unique'] == '':
                error.append("'input_name_unique' is empty")
            elif input_info.INPUT_INFORMATION['input_name_unique'].lower() in list_inputs:
                error.append(
                    "'input_name_unique' is not unique, there "
                    "is already an input with that name ({})".format(
                        input_info.INPUT_INFORMATION['input_name_unique']))

            if 'input_manufacturer' not in input_info.INPUT_INFORMATION:
                error.append(
                    "'input_manufacturer' not found in "
                    "INPUT_INFORMATION dictionary")
            elif input_info.INPUT_INFORMATION['input_manufacturer'] == '':
                error.append("'input_manufacturer' is empty")

            if 'input_name' not in input_info.INPUT_INFORMATION:
                error.append(
                    "'input_name' not found in INPUT_INFORMATION dictionary")
            elif input_info.INPUT_INFORMATION['input_name'] == '':
                error.append("'input_name' is empty")

            if 'measurements_name' not in input_info.INPUT_INFORMATION:
                error.append(
                    "'measurements_name' not found in "
                    "INPUT_INFORMATION dictionary")
            elif input_info.INPUT_INFORMATION['measurements_name'] == '':
                error.append("'measurements_name' list is empty")

            if 'measurements_dict' not in input_info.INPUT_INFORMATION:
                error.append(
                    "'measurements_dict' not found in "
                    "INPUT_INFORMATION dictionary")
            elif not input_info.INPUT_INFORMATION['measurements_dict']:
                if ('measurements_variable_amount' in input_info.INPUT_INFORMATION and
                   input_info.INPUT_INFORMATION['measurements_variable_amount']):
                    pass
                else:
                    error.append("'measurements_dict' list is empty")
            else:
                # Check that units and measurements exist in database
                for _, each_unit_measure in input_info.INPUT_INFORMATION['measurements_dict'].items():
                    if (each_unit_measure['unit'] not in UNITS and
                            not Unit.query.filter(Unit.name_safe == each_unit_measure['unit']).count()):
                        error.append(
                            "Unit not found in database. "
                            "Add the unit '{}' to the database before importing.".format(
                                each_unit_measure['unit']))
                    if (each_unit_measure['measurement'] not in MEASUREMENTS and
                            not Measurement.query.filter(Measurement.name_safe == each_unit_measure['measurement']).count()):
                        error.append(
                            "Measurement not found in database. "
                            "Add the measurement '{}' to the database before importing.".format(
                                each_unit_measure['measurement']))

            if 'dependencies_module' in input_info.INPUT_INFORMATION:
                if not isinstance(input_info.INPUT_INFORMATION['dependencies_module'], list):
                    error.append("'dependencies_module' must be a list of tuples")
                else:
                    for each_dep in input_info.INPUT_INFORMATION['dependencies_module']:
                        if not isinstance(each_dep, tuple):
                            error.append(
                                "'dependencies_module' must be a list of "
                                "tuples")
                        elif len(each_dep) != 3:
                            error.append(
                                "'dependencies_module': tuples in list must "
                                "have 3 items")
                        elif not each_dep[0] or not each_dep[1] or not each_dep[2]:
                            error.append(
                                "'dependencies_module': tuples in list must "
                                "not be empty")
                        elif each_dep[0] not in ['internal', 'pip-pypi', 'pip-git', 'apt']:
                            error.append(
                                "'dependencies_module': first in tuple "
                                "must be 'internal', 'pip-pypi', 'pip-git', "
                                "or 'apt'")

        if not error:
            # Determine filename
            unique_name = '{}.py'.format(input_info.INPUT_INFORMATION['input_name_unique'].lower())

            # Move module from temp directory to custom_input directory
            full_path_final = os.path.join(PATH_INPUTS_CUSTOM, unique_name)
            os.rename(full_path_tmp, full_path_final)

            # Reload frontend to refresh the inputs
            cmd = '{path}/mycodo/scripts/mycodo_wrapper frontend_reload 2>&1'.format(
                path=install_dir)
            subprocess.Popen(cmd, shell=True)
            flash('Frontend reloaded to scan for new Input Modules', 'success')

    except Exception as err:
        error.append("Exception: {}".format(err))

    flash_success_errors(error, action, url_for('routes_settings.settings_input'))


def settings_input_delete(form):
    action = '{action} {controller}'.format(
        action=gettext("Import"),
        controller=TRANSLATIONS['input']['title'])
    error = []

    input_device_name = form.input_id.data
    file_name = '{}.py'.format(form.input_id.data.lower())
    full_path_file = os.path.join(PATH_INPUTS_CUSTOM, file_name)

    if not error:
        # Check if any Input entries exist
        input_dev = Input.query.filter(
            Input.device == input_device_name).count()
        if input_dev:
            error.append("Cannot delete Input Module if there are still "
                         "Input entries using it. Deactivate and delete all "
                         "Input entries that use this module before deleting "
                         "the module.")

    if not error:
        os.remove(full_path_file)

        # Reload frontend to refresh the inputs
        cmd = '{path}/mycodo/scripts/mycodo_wrapper frontend_reload 2>&1'.format(
            path=os.path.abspath(INSTALL_DIRECTORY))
        subprocess.Popen(cmd, shell=True)
        flash('Frontend reloaded to scan for new Input Modules', 'success')

    flash_success_errors(error, action, url_for('routes_settings.settings_input'))


def settings_output_import(form):
    """
    Receive an output module file, check it for errors, add it to Mycodo output list
    """
    action = '{action} {controller}'.format(
        action=gettext("Import"),
        controller=TRANSLATIONS['output']['title'])
    error = []

    output_info = None

    try:
        # correct_format = 'Mycodo_MYCODOVERSION_Settings_DBVERSION_HOST_DATETIME.zip'
        install_dir = os.path.abspath(INSTALL_DIRECTORY)
        tmp_directory = os.path.join(install_dir, 'mycodo/outputs/tmp_outputs')
        assure_path_exists(tmp_directory)
        assure_path_exists(PATH_OUTPUTS_CUSTOM)
        tmp_name = 'tmp_output_testing.py'
        full_path_tmp = os.path.join(tmp_directory, tmp_name)

        if not form.import_output_file.data:
            error.append('No file present')
        elif form.import_output_file.data.filename == '':
            error.append('No file name')
        else:
            form.import_output_file.data.save(full_path_tmp)

        try:
            output_info = load_module_from_file(full_path_tmp, 'outputs')
            if not hasattr(output_info, 'OUTPUT_INFORMATION'):
                error.append("Could not load OUTPUT_INFORMATION dictionary from "
                             "the uploaded output module")
        except Exception:
            error.append("Could not load uploaded file as a python module:\n"
                         "{}".format(traceback.format_exc()))

        dict_outputs = parse_output_information()
        list_outputs = []
        for each_key in dict_outputs.keys():
            list_outputs.append(each_key.lower())

        if not error:
            if 'output_name_unique' not in output_info.OUTPUT_INFORMATION:
                error.append(
                    "'output_name_unique' not found in "
                    "OUTPUT_INFORMATION dictionary")
            elif output_info.OUTPUT_INFORMATION['output_name_unique'] == '':
                error.append("'output_name_unique' is empty")
            elif output_info.OUTPUT_INFORMATION['output_name_unique'].lower() in list_outputs:
                error.append(
                    "'output_name_unique' is not unique, there "
                    "is already an output with that name ({})".format(
                        output_info.OUTPUT_INFORMATION['output_name_unique']))

            if 'output_name' not in output_info.OUTPUT_INFORMATION:
                error.append(
                    "'output_name' not found in OUTPUT_INFORMATION dictionary")
            elif output_info.OUTPUT_INFORMATION['output_name'] == '':
                error.append("'output_name' is empty")

            if 'measurements_dict' not in output_info.OUTPUT_INFORMATION:
                error.append(
                    "'measurements_dict' not found in "
                    "OUTPUT_INFORMATION dictionary")
            elif not output_info.OUTPUT_INFORMATION['measurements_dict']:
                if ('measurements_variable_amount' in output_info.OUTPUT_INFORMATION and
                   output_info.OUTPUT_INFORMATION['measurements_variable_amount']):
                    pass
                else:
                    error.append("'measurements_dict' list is empty")
            else:
                # Check that units and measurements exist in database
                for _, each_unit_measure in output_info.OUTPUT_INFORMATION['measurements_dict'].items():
                    if (each_unit_measure['unit'] not in UNITS and
                            not Unit.query.filter(Unit.name_safe == each_unit_measure['unit']).count()):
                        error.append(
                            "Unit not found in database. "
                            "Add the unit '{}' to the database before importing.".format(
                                each_unit_measure['unit']))
                    if (each_unit_measure['measurement'] not in MEASUREMENTS and
                            not Measurement.query.filter(Measurement.name_safe == each_unit_measure['measurement']).count()):
                        error.append(
                            "Measurement not found in database. "
                            "Add the measurement '{}' to the database before importing.".format(
                                each_unit_measure['measurement']))

            if 'dependencies_module' in output_info.OUTPUT_INFORMATION:
                if not isinstance(output_info.OUTPUT_INFORMATION['dependencies_module'], list):
                    error.append("'dependencies_module' must be a list of tuples")
                else:
                    for each_dep in output_info.OUTPUT_INFORMATION['dependencies_module']:
                        if not isinstance(each_dep, tuple):
                            error.append(
                                "'dependencies_module' must be a list of "
                                "tuples")
                        elif len(each_dep) != 3:
                            error.append(
                                "'dependencies_module': tuples in list must "
                                "have 3 items")
                        elif not each_dep[0] or not each_dep[1] or not each_dep[2]:
                            error.append(
                                "'dependencies_module': tuples in list must "
                                "not be empty")
                        elif each_dep[0] not in ['internal', 'pip-pypi', 'pip-git', 'apt']:
                            error.append(
                                "'dependencies_module': first in tuple "
                                "must be 'internal', 'pip-pypi', 'pip-git', "
                                "or 'apt'")

        if not error:
            # Determine filename
            unique_name = '{}.py'.format(output_info.OUTPUT_INFORMATION['output_name_unique'].lower())

            # Move module from temp directory to custom_output directory
            full_path_final = os.path.join(PATH_OUTPUTS_CUSTOM, unique_name)
            os.rename(full_path_tmp, full_path_final)

            # Reload frontend to refresh the outputs
            cmd = '{path}/mycodo/scripts/mycodo_wrapper frontend_reload 2>&1'.format(
                path=install_dir)
            subprocess.Popen(cmd, shell=True)
            flash('Frontend reloaded to scan for new Output Modules', 'success')

    except Exception as err:
        error.append("Exception: {}".format(err))

    flash_success_errors(error, action, url_for('routes_settings.settings_output'))


def settings_output_delete(form):
    action = '{action} {controller}'.format(
        action=gettext("Import"),
        controller=TRANSLATIONS['output']['title'])
    error = []

    output_device_name = form.output_id.data
    file_name = '{}.py'.format(form.output_id.data.lower())
    full_path_file = os.path.join(PATH_OUTPUTS_CUSTOM, file_name)

    if not error:
        # Check if any Output entries exist
        output_dev = Output.query.filter(
            Output.output_type == output_device_name).count()
        if output_dev:
            error.append("Cannot delete Output Module if there are still "
                         "Output entries using it. Delete all Output entries "
                         "that use this module before deleting the module.")

    if not error:
        os.remove(full_path_file)

        # Reload frontend to refresh the outputs
        cmd = '{path}/mycodo/scripts/mycodo_wrapper frontend_reload 2>&1'.format(
            path=os.path.abspath(INSTALL_DIRECTORY))
        subprocess.Popen(cmd, shell=True)
        flash('Frontend reloaded to scan for new Output Modules', 'success')

    flash_success_errors(error, action, url_for('routes_settings.settings_output'))


def settings_measurement_add(form):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['add']['title'],
        controller=TRANSLATIONS['measurement']['title'])
    error = []
    choices_meas = choices_measurements(Measurement.query.all())

    new_measurement = Measurement()
    new_measurement.name = form.name.data
    new_measurement.units = ",".join(form.units.data)

    name_safe = re.sub('[^0-9a-zA-Z]+', '_', form.id.data)
    if name_safe.endswith('_'):
        name_safe = name_safe[:-1]
    if name_safe in choices_meas:
        error.append("Measurement name already exists: {name}".format(
            name=name_safe))

    new_measurement.name_safe = name_safe

    try:
        if not error:
            new_measurement.save()
            flash(gettext(
                "Measurement with ID %(id)s (%(uuid)s) successfully added",
                id=new_measurement.id,
                uuid=new_measurement.unique_id),
                  "success")
    except sqlalchemy.exc.OperationalError as except_msg:
        error.append(except_msg)
    except sqlalchemy.exc.IntegrityError as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def settings_measurement_mod(form):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=TRANSLATIONS['measurement']['title'])
    error = []
    try:
        mod_measurement = Measurement.query.filter(
            Measurement.unique_id == form.measurement_id.data).first()
        mod_measurement.name = form.name.data
        mod_measurement.units = ",".join(form.units.data)

        name_safe = re.sub('[^0-9a-zA-Z]+', '_', form.id.data)
        if name_safe.endswith('_'):
            name_safe = name_safe[:-1]

        if name_safe != mod_measurement.name_safe:  # Change measurement name
            # Ensure no Inputs depend on this measurement
            for _, each_data in parse_input_information().items():
                if 'measurements_dict' in each_data:
                    for _, each_channel_data in each_data['measurements_dict'].items():
                        if ('measurement' in each_channel_data and
                                each_channel_data['measurement'] == mod_measurement.name_safe):
                            error.append(
                                "Cannot change the name of this measurement "
                                "because an Input depends on it.")
            # Ensure a measurement doesn't already exist with the new name
            if (Measurement.query.filter(
                    and_(Measurement.name_safe == name_safe,
                         Measurement.unique_id != mod_measurement.unique_id)).count() or
                    name_safe in MEASUREMENTS):
                error.append("Measurement name already exists: {name}".format(
                    name=name_safe))
            else:
                mod_measurement.name_safe = name_safe

        if not error:
            db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def settings_measurement_del(unique_id):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=TRANSLATIONS['measurement']['title'])
    error = []

    measurement = Measurement.query.filter(
        Measurement.unique_id == unique_id).first()

    # Ensure no Inputs depend on this measurement
    for _, each_data in parse_input_information().items():
        if 'measurements_dict' in each_data:
            for _, each_channel_data in each_data['measurements_dict'].items():
                if ('measurement' in each_channel_data and
                        each_channel_data['measurement'] == measurement.name_safe):
                    error.append("Cannot delete this measurement because "
                                 "an Input depends on it.")

    try:
        if not error:
            delete_entry_with_id(Measurement, unique_id)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def settings_unit_add(form):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['add']['title'],
        controller=gettext("Unit"))
    error = []
    choices_unit = choices_units(Unit.query.all())

    if form.validate():
        name_safe = re.sub('[^0-9a-zA-Z]+', '_', form.id.data)
        if name_safe.endswith('_'):
            name_safe = name_safe[:-1]

        if name_safe in choices_unit:
            error.append("Unit name already exists: {name}".format(
                name=name_safe))

        new_unit = Unit()
        new_unit.name_safe = name_safe
        new_unit.name = form.name.data
        new_unit.unit = form.unit.data

        try:
            if not error:
                new_unit.save()
                flash(gettext(
                    "Unit with ID %(id)s (%(uuid)s) successfully added",
                    id=new_unit.id,
                    uuid=new_unit.unique_id),
                    "success")
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)

        flash_success_errors(
            error, action, url_for('routes_settings.settings_measurement'))
    else:
        flash_form_errors(form)


def settings_unit_mod(form):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=gettext("Unit"))
    error = []
    try:
        mod_unit = Unit.query.filter(
            Unit.unique_id == form.unit_id.data).first()

        name_safe = re.sub('[^0-9a-zA-Z]+', '_', form.id.data)
        if name_safe.endswith('_'):
            name_safe = name_safe[:-1]

        conversions = Conversion.query.filter(or_(
            Conversion.convert_unit_from == mod_unit.name_safe,
            Conversion.convert_unit_to == mod_unit.name_safe
        )).count()

        if (Unit.query.filter(
                and_(Unit.name_safe == name_safe,
                     Unit.unique_id != form.unit_id.data)).count() or
                name_safe in UNITS):
            error.append("Unit name already exists: {name}".format(
                name=name_safe))
        elif mod_unit.name_safe != name_safe:
            if conversions:
                error.append(
                    "Unit belongs to a conversion."
                    "Delete conversion(s) before changing unit.")
            else:
                # Ensure no Inputs depend on this measurement
                for _, each_data in parse_input_information().items():
                    if 'measurements_dict' in each_data:
                        for _, each_channel_data in each_data['measurements_dict'].items():
                            if ('unit' in each_channel_data and
                                    each_channel_data['unit'] == mod_unit.name_safe):
                                error.append(
                                    "Cannot change the name of this unit "
                                    "because an Input depends on it.")

        mod_unit.name = form.name.data
        mod_unit.unit = form.unit.data
        mod_unit.name_safe = name_safe

        if not error:
            db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def settings_unit_del(unique_id):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=gettext("Unit"))
    error = []

    del_unit = Unit.query.filter(
        Unit.unique_id == unique_id).first()

    conversions = Conversion.query.filter(or_(
        Conversion.convert_unit_from == del_unit.name_safe,
        Conversion.convert_unit_to == del_unit.name_safe
    )).count()

    if conversions:
        error.append(
            "Unit belongs to a conversion."
            "Delete conversion(s) before deleting unit.")

    # Ensure no Inputs depend on this unit
    for _, each_data in parse_input_information().items():
        if 'measurements_dict' in each_data:
            for _, each_channel_data in each_data['measurements_dict'].items():
                if ('unit' in each_channel_data and
                        each_channel_data['unit'] == del_unit.name_safe):
                    error.append("Cannot delete this unit because an "
                                 "Input depends on it.")

    try:
        if not error:
            delete_entry_with_id(Unit, unique_id)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def settings_convert_add(form):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['add']['title'],
        controller=gettext("Conversion"))
    error = []

    conversion = Conversion.query.all()

    conversion_str = '{fr}_to_{to}'.format(
        fr=form.convert_unit_from.data, to=form.convert_unit_to.data)
    if conversion_str in all_conversions(conversion):
        error.append("Conversion '{cs}' already exists.".format(
            cs=conversion_str))

    if 'x' not in form.equation.data:
        error.append("'x' must appear in the equation.")

    if form.validate():
        new_conversion = Conversion()
        new_conversion.convert_unit_from = form.convert_unit_from.data
        new_conversion.convert_unit_to = form.convert_unit_to.data
        new_conversion.equation = form.equation.data

        try:
            if not error:
                new_conversion.save()
                flash(gettext(
                    "Conversion with ID %(id)s (%(uuid)s) successfully added",
                    id=new_conversion.id,
                    uuid=new_conversion.unique_id),
                    "success")
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)

        flash_success_errors(
            error, action, url_for('routes_settings.settings_measurement'))
    else:
        flash_form_errors(form)


def settings_convert_mod(form):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=gettext("Conversion"))
    error = []

    if 'x' not in form.equation.data:
        error.append("'x' must appear in the equation")

    try:
        mod_conversion = Conversion.query.filter(
            Conversion.unique_id == form.conversion_id.data).first()

        # Don't allow conversion to be changed for an active controller
        error = check_conversion_being_used(mod_conversion, error, state='active')

        if not error:
            # Don't allow from conversion to be changed for an inactive controller
            if mod_conversion.convert_unit_from != form.convert_unit_from.data:
                error = check_conversion_being_used(mod_conversion, error, state='inactive')

            if not mod_conversion.protected:
                mod_conversion.convert_unit_from = form.convert_unit_from.data
                mod_conversion.convert_unit_to = form.convert_unit_to.data
            mod_conversion.equation = form.equation.data
            db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def settings_convert_del(unique_id):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=gettext("Conversion"))
    error = []

    try:
        conv = Conversion.query.filter(
            Conversion.unique_id == unique_id).first()

        # Don't allow conversion to be changed for an active controller
        error = check_conversion_being_used(conv, error, state='active')

        if not error:
            # Delete conversion from any controllers
            remove_conversion_from_controllers(unique_id)
            delete_entry_with_id(Conversion, unique_id)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(
        error, action, url_for('routes_settings.settings_measurement'))


def check_conversion_being_used(conv, error, state=None):
    """
    Check if a controller is currently active/inactive and using the conversion
    If so, cannot edit the database/modify the conversion
    """
    try:
        device_measurements = DeviceMeasurements.query.all()

        list_measurements = [
            Input,
            Math,
            PID,
        ]

        for each_device_type in list_measurements:
            for each_device in each_device_type.query.all():
                for each_meas in device_measurements:
                    if (each_device.unique_id == each_meas.device_id and
                            conv.unique_id == each_meas.conversion_id):

                        detected_device = each_device_type.query.filter(
                            each_device_type.unique_id == each_meas.device_id).first()

                        if ((state == 'active' and detected_device.is_activated) or
                                (state == 'inactive' and not detected_device.is_activated)):
                            error.append(
                                "Conversion [{cid}] ({conv}): "
                                "Currently in use for measurement {meas}, "
                                "for device {dev}".format(
                                    cid=conv.id,
                                    conv=conv.unique_id,
                                    meas=each_meas.unique_id,
                                    dev=each_meas.device_id))
    except Exception as except_msg:
        error.append(except_msg)
    return error


def remove_conversion_from_controllers(conv_id):
    """
    Find measurements using the conversion and delete the reference to the conversion_id
    """
    device_measurements = DeviceMeasurements.query.all()

    for each_meas in device_measurements:
        if each_meas.conversion_id == conv_id:
            each_meas.conversion_id = ''

    db.session.commit()


def settings_pi_mod(form):
    """
    Change Pi Settings
    Commands found at
    https://github.com/raspberrypi-ui/rc_gui/blob/master/src/rc_gui.c
    """
    error = []
    status = None
    action_str = None

    if form.save_sample_rates.data:
        mod_misc = Misc.query.first()
        mod_misc.sample_rate_controller_conditional = form.sample_rate_controller_conditional.data
        mod_misc.sample_rate_controller_input = form.sample_rate_controller_input.data
        mod_misc.sample_rate_controller_math = form.sample_rate_controller_math.data
        mod_misc.sample_rate_controller_output = form.sample_rate_controller_output.data
        mod_misc.sample_rate_controller_pid = form.sample_rate_controller_pid.data
        db.session.commit()
    elif form.enable_i2c.data:
        _, _, status = cmd_output("raspi-config nonint do_i2c 0", user='root')
        action_str = "Enable I2C"
    elif form.disable_i2c.data:
        _, _, status = cmd_output("raspi-config nonint do_i2c 1", user='root')
        action_str = "Disable I2C"
    elif form.enable_one_wire.data:
        _, _, status = cmd_output("raspi-config nonint do_onewire 0", user='root')
        action_str = "Enable 1-Wire"
    elif form.disable_one_wire.data:
        _, _, status = cmd_output("raspi-config nonint do_onewire 1", user='root')
        action_str = "Disable 1-Wire"
    elif form.enable_serial.data:
        _, _, status = cmd_output("raspi-config nonint do_serial 0", user='root')
        action_str = "Enable Serial"
    elif form.disable_serial.data:
        _, _, status = cmd_output("raspi-config nonint do_serial 1", user='root')
        action_str = "Disable Serial"
    elif form.enable_spi.data:
        _, _, status = cmd_output("raspi-config nonint do_spi 0", user='root')
        action_str = "Enable SPI"
    elif form.disable_spi.data:
        _, _, status = cmd_output("raspi-config nonint do_spi 1", user='root')
        action_str = "Disable SPI"
    elif form.enable_ssh.data:
        _, _, status = cmd_output("raspi-config nonint do_ssh 0", user='root')
        action_str = "Enable SSH"
    elif form.disable_ssh.data:
        _, _, status = cmd_output("raspi-config nonint do_ssh 1", user='root')
        action_str = "Disable SSH"
    elif form.enable_pi_camera.data:
        _, _, status = cmd_output("raspi-config nonint do_camera 0", user='root')
        action_str = "Enable Pi Camera"
    elif form.disable_pi_camera.data:
        _, _, status = cmd_output("raspi-config nonint do_camera 1", user='root')
        action_str = "Disable Pi Camera"
    elif form.change_hostname.data:
        if is_valid_hostname(form.hostname.data):
            _, _, status = cmd_output(
                "raspi-config nonint do_hostname {host}".format(
                    host=form.hostname.data))
        else:
            error.append(
                "Invalid hostname. Hostnames are composed of series of "
                "labels concatenated with dots, as are all domain names. "
                "Hostnames must be 1 to 63 characters and may contain only "
                "the ASCII letters 'a' through 'z' (in a case-insensitive "
                "manner), the digits '0' through '9', and the hyphen ('-').")
        action_str = "Change Hostname to '{host}'".format(
            host=form.hostname.data)
    elif form.change_pigpiod_sample_rate.data:
        if form.pigpiod_sample_rate.data not in ['low', 'high',
                                                 'disabled', 'uninstalled']:
            error.append(
                "Valid pigpiod options: Uninstall, Disable, 1 ms, or 5 ms. "
                "Invalid option: {op}".format(
                    op=form.pigpiod_sample_rate.data))
        else:
            # Stop the Mycodo daemon
            cmd = "{pth}/mycodo/scripts/mycodo_wrapper daemon_stop" \
                  " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                pth=INSTALL_DIRECTORY)
            stop_daemon = subprocess.Popen(cmd, shell=True)
            stop_daemon.wait()

            if (form.pigpiod_sample_rate.data != 'uninstalled' and
                    form.pigpiod_state.data == 'uninstalled'):
                # Install pigpiod (sample rate of 1 ms)
                cmd = "{pth}/mycodo/scripts/mycodo_wrapper install_pigpiod" \
                      " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                    pth=INSTALL_DIRECTORY)
                install_pigpiod = subprocess.Popen(cmd, shell=True)
                install_pigpiod.wait()

            # Disable pigpiod
            cmd = "{pth}/mycodo/scripts/mycodo_wrapper disable_pigpiod" \
                  " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                pth=INSTALL_DIRECTORY)
            disable_pigpiod = subprocess.Popen(cmd, shell=True)
            disable_pigpiod.wait()

            if form.pigpiod_sample_rate.data == 'low':
                # Install pigpiod (sample rate of 1 ms)
                cmd = "{pth}/mycodo/scripts/mycodo_wrapper enable_pigpiod_low" \
                      " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                    pth=INSTALL_DIRECTORY)
                enable_pigpiod_1ms = subprocess.Popen(cmd, shell=True)
                enable_pigpiod_1ms.wait()
            elif form.pigpiod_sample_rate.data == 'high':
                # Install pigpiod (sample rate of 5 ms)
                cmd = "{pth}/mycodo/scripts/mycodo_wrapper enable_pigpiod_high" \
                      " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                    pth=INSTALL_DIRECTORY)
                enable_pigpiod_5ms = subprocess.Popen(cmd, shell=True)
                enable_pigpiod_5ms.wait()
            elif form.pigpiod_sample_rate.data == 'disabled':
                # Disable pigpiod (user selected disable)
                cmd = "{pth}/mycodo/scripts/mycodo_wrapper enable_pigpiod_disabled" \
                      " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                    pth=INSTALL_DIRECTORY)
                disable_pigpiod = subprocess.Popen(cmd, shell=True)
                disable_pigpiod.wait()
            elif form.pigpiod_sample_rate.data == 'uninstalled':
                # Uninstall pigpiod (user selected disable)
                cmd = "{pth}/mycodo/scripts/mycodo_wrapper uninstall_pigpiod" \
                      " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                    pth=INSTALL_DIRECTORY)
                uninstall_pigpiod = subprocess.Popen(cmd, shell=True)
                uninstall_pigpiod.wait()

            # Start the Mycodo daemon
            cmd = "{pth}/mycodo/scripts/mycodo_wrapper daemon_start" \
                  " | ts '[%Y-%m-%d %H:%M:%S]' 2>&1".format(
                pth=INSTALL_DIRECTORY)
            start_daemon = subprocess.Popen(cmd, shell=True)
            start_daemon.wait()

    if status:
        error.append("Unknown error executing command to {action}".format(
            action=action_str))

    action = '{controller}: {action}'.format(
        controller=gettext("Pi Settings"),
        action=action_str)

    flash_success_errors(error, action, url_for('routes_settings.settings_pi'))


def settings_alert_mod(form_mod_alert):
    """ Modify Alert settings """
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=gettext("Alert Settings"))
    error = []

    try:
        if form_mod_alert.validate():
            mod_smtp = SMTP.query.one()
            if form_mod_alert.send_test.data:
                send_email(
                    mod_smtp.host, mod_smtp.protocol, mod_smtp.port,
                    mod_smtp.user, mod_smtp.passw, mod_smtp.email_from,
                    form_mod_alert.send_test_to_email.data,
                    "This is a test email from Mycodo")
                flash(gettext("Test email sent to %(recip)s. Check your "
                              "inbox to see if it was successful.",
                              recip=form_mod_alert.send_test_to_email.data),
                      "success")
                return redirect(url_for('routes_settings.settings_alerts'))
            else:
                mod_smtp.host = form_mod_alert.smtp_host.data
                if form_mod_alert.smtp_port.data:
                    mod_smtp.port = form_mod_alert.smtp_port.data
                else:
                    mod_smtp.port = None
                mod_smtp.protocol = form_mod_alert.smtp_protocol.data
                mod_smtp.user = form_mod_alert.smtp_user.data
                if form_mod_alert.smtp_password.data:
                    mod_smtp.passw = form_mod_alert.smtp_password.data
                mod_smtp.email_from = form_mod_alert.smtp_from_email.data
                mod_smtp.hourly_max = form_mod_alert.smtp_hourly_max.data
                db.session.commit()
        else:
            flash_form_errors(form_mod_alert)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_alerts'))

def settings_mqtt_mod(form_mod_mqtt):
    """ Modify MQTT settings """
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['modify']['title'],
        controller=gettext("MQTT Settings"))
    error = []

    try:
        if form_mod_mqtt.validate():
            mod_mqtt = MQTT.query.one()
            if form_mod_mqtt.send_test_mqtt.data:
                pub_mqtt(
                    mod_mqtt.hostname, mod_mqtt.port,
                    mod_mqtt.user, mod_mqtt.passw, mod_mqtt.keep_alive, mod_mqtt.clientid,
                    form_mod_mqtt.send_test_mqtt_topic.data, "Test")
                flash(gettext("Test message published to %(topic)s. Check the broker "
                              "for confirmation of receipt.",
                              topic=form_mod_mqtt.send_test_mqtt_topic.data),
                      "success")
                return redirect(url_for('routes_settings.settings_mqtt'))
            elif form_mod_mqtt.enable_mqtt.data:
                mod_mqtt.enabled = 1
                db.session.commit()
            elif form_mod_mqtt.disable_mqtt.data:
                mod_mqtt.enabled = 0
                db.session.commit()
            else:
                mod_mqtt.hostname = form_mod_mqtt.mqtt_hostname.data
                if form_mod_mqtt.mqtt_port.data:
                    mod_mqtt.port = form_mod_mqtt.mqtt_port.data
                else:
                    mod_mqtt.port = None
                mod_mqtt.user = form_mod_mqtt.mqtt_user.data
                if form_mod_mqtt.mqtt_password.data:
                    mod_mqtt.passw = form_mod_mqtt.mqtt_password.data
                mod_mqtt.clientid = form_mod_mqtt.mqtt_clientid.data
                mod_mqtt.topic_prefix = form_mod_mqtt.mqtt_topic_prefix.data
                mod_mqtt.keep_alive = form_mod_mqtt.mqtt_keep_alive.data
                db.session.commit()
        else:
            flash_form_errors(form_mod_mqtt)
    except Exception as except_msg:
        error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_mqtt'))

def settings_diagnostic_delete_inputs():
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=TRANSLATIONS['input']['title'])
    error = []

    inputs = db_retrieve_table(Input)
    device_measurements = db_retrieve_table(DeviceMeasurements)
    display_order = db_retrieve_table(DisplayOrder, entry='first')

    if not error:
        try:
            for each_input in inputs:
                # Deactivate any active controllers using the input
                if each_input.is_activated:
                    input_deactivate_associated_controllers(each_input.unique_id)
                    controller_activate_deactivate('deactivate', 'Input', each_input.unique_id)

                # Delete all measurements associated with the input
                for each_measurement in device_measurements:
                    if each_measurement.device_id == each_input.unique_id:
                        db.session.delete(each_measurement)

                # Delete the input
                db.session.delete(each_input)
            display_order.input = ''  # Clear the order
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_delete_maths():
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=TRANSLATIONS['math']['title'])
    error = []

    maths = db_retrieve_table(Math)
    device_measurements = db_retrieve_table(DeviceMeasurements)
    display_order = db_retrieve_table(DisplayOrder, entry='first')

    if not error:
        try:
            for each_math in maths:
                # Deactivate any active controllers using the input
                if each_math.is_activated:
                    controller_activate_deactivate('deactivate', 'Math', each_math.unique_id)

                # Delete all measurements associated
                for each_measurement in device_measurements:
                    if each_measurement.device_id == each_math.unique_id:
                        db.session.delete(each_measurement)
                db.session.delete(each_math)
            display_order.math = ''
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_delete_dashboard_elements():
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=TRANSLATIONS['dashboard']['title'])
    error = []

    dashboard = db_retrieve_table(Dashboard)
    widget = db_retrieve_table(Widget)

    if not error:
        try:
            for each_dash in dashboard:
                db.session.delete(each_dash)
                db.session.commit()

            for each_widget in widget:
                db.session.delete(each_widget)
                db.session.commit()

            Dashboard(id=1, name='Default').save()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_delete_notes_tags():
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller='{}/{}'.format(TRANSLATIONS['tag']['title'],
                                  TRANSLATIONS['note']['title']))
    error = []

    if not error:
        try:
            for each_tag in db_retrieve_table(NoteTags):
                db.session.delete(each_tag)
                db.session.commit()
            for each_note in db_retrieve_table(Notes):
                db.session.delete(each_note)
                db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_delete_outputs():
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=TRANSLATIONS['output']['title'])
    error = []

    output = db_retrieve_table(Output)
    display_order = db_retrieve_table(DisplayOrder, entry='first')

    if not error:
        try:
            for each_output in output:
                db.session.delete(each_output)
                db.session.commit()
            display_order.output = ''
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_delete_settings_database():
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller='Settings Database')
    error = []

    if not error:
        try:
            os.remove('/var/mycodo-root/databases/mycodo.db')
            cmd = "{pth}/mycodo/scripts/mycodo_wrapper frontend_reload" \
                  " | ts '[%Y-%m-%d %H:%M:%S]'" \
                  " >> {log} 2>&1".format(pth=INSTALL_DIRECTORY,
                                          log=DAEMON_LOG_FILE)
            subprocess.Popen(cmd, shell=True)
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_delete_file(delete_type):
    action = '{action} {controller}'.format(
        action=TRANSLATIONS['delete']['title'],
        controller=gettext("File"))
    error = []

    if not error:
        try:
            file_remove = None
            if delete_type == 'dependency':
                file_remove = os.path.abspath(DEPENDENCY_INIT_FILE)
            elif delete_type == 'upgrade':
                file_remove = os.path.abspath(UPGRADE_INIT_FILE)
            if file_remove:
                if os.path.isfile(file_remove):
                    os.remove(file_remove)
                else:
                    error.append("File not found: {}".format(file_remove))
            else:
                error.append("Unknown file: {}".format(delete_type))
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def settings_diagnostic_reset_email_counter():
    action = gettext("Reset email counter")
    error = []

    if not error:
        try:
            smtp_settings = SMTP.query.first()
            smtp_settings.email_count = 0
            smtp_settings.smtp_wait_timer = time.time() + 3600
            db.session.commit()
        except Exception as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_settings.settings_diagnostic'))


def is_valid_hostname(hostname):
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1] # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))
