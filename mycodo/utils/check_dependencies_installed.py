# -*- coding: utf-8 -*-
import importlib
import logging
import os
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir) + '/..'))

from mycodo.config import INSTALL_DIRECTORY
from mycodo.config import LIST_DEPENDENCIES

from mycodo.mycodo_flask.utils.utils_general import return_dependencies
from mycodo.utils.inputs import parse_input_information
from mycodo.utils.system_pi import cmd_output
from mycodo.databases.models import Input
from mycodo.databases.models import Output
from mycodo.utils.database import db_retrieve_table_daemon

logger = logging.getLogger("mycodo.check_dependencies_installed")


def get_installed_dependencies():
    met_deps = []
    list_dependencies = [parse_input_information()] + LIST_DEPENDENCIES

    for each_section in list_dependencies:
        for device_type in each_section:
            for each_device, each_dict in each_section[device_type].items():
                if each_device == 'dependencies_module':
                    for (install_type, package, install_id) in each_dict:
                        entry = '{0} {1}'.format(install_type, install_id)
                        if install_type in ['pip-pypi', 'pip-git']:
                            try:
                                module = importlib.util.find_spec(package)
                                if module is not None and entry not in met_deps:
                                    met_deps.append(entry)
                            except Exception:
                                logger.debug(
                                    'Exception while checking python dependency: '
                                    '{dep}'.format(dep=package))
                        elif install_type == 'apt':
                            cmd = 'dpkg -l {}'.format(package)
                            _, _, stat = cmd_output(cmd)
                            if not stat and entry not in met_deps:
                                met_deps.append(entry)
    return met_deps


def install_device_dependencies():
    # Check all currently-installed devices for uninstalled dependencies
    # and install if found
    list_devices = []
    for each_input in db_retrieve_table_daemon(Input, entry='all'):
        if each_input.device not in list_devices:
            list_devices.append(each_input.device)
    for each_output in db_retrieve_table_daemon(Output, entry='all'):
        if each_output.output_type not in list_devices:
            list_devices.append(each_output.output_type)

    dependencies_to_install = []
    for each_device in list_devices:
        device_unmet_dependencies, _ = return_dependencies(each_device)
        for each_unmet_dep in device_unmet_dependencies:
            if each_unmet_dep not in dependencies_to_install:
                dependencies_to_install.append(each_unmet_dep)

    for each_dep in dependencies_to_install:
        if each_dep[2] in ['apt', 'pip-git', 'pip-pypi']:
            logger.info("Installing dependency: {}".format(each_dep[3]))
            update_cmd = '{home}/scripts/dependencies.sh {dep}'.format(
                home=INSTALL_DIRECTORY,
                dep='{} {}'.format(each_dep[2],
                                   each_dep[3]))
            output, err, stat = cmd_output(update_cmd)
            if err:
                logger.error("Error detected while installing dependency: {}: {}".format(each_dep, err))


if __name__ == "__main__":
    install_device_dependencies()

    # Update installed dependencies
    installed_deps = get_installed_dependencies()
    for each_dep in installed_deps:
        if each_dep.split(' ')[0] in ['apt', 'pip-git', 'pip-pypi']:
            update_cmd = '{home}/scripts/dependencies.sh {dep}'.format(
                home=INSTALL_DIRECTORY, dep=each_dep)
            output, err, stat = cmd_output(update_cmd)
            print("{}".format(output.decode("utf-8")))
