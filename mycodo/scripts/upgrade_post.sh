#!/bin/bash
#
#  upgrade_post.sh - Commands to execute after a Mycodo upgrade
#

if [ "$EUID" -ne 0 ]; then
    printf "Please run as root\n";
    exit
fi

INSTALL_DIRECTORY=$( cd "$( dirname "${BASH_SOURCE[0]}" )/../../" && pwd -P )
INSTALL_CMD="/bin/bash ${INSTALL_DIRECTORY}/mycodo/scripts/upgrade_commands.sh"
INSTALL_DEP="/bin/bash ${INSTALL_DIRECTORY}/mycodo/scripts/dependencies.sh"
cd ${INSTALL_DIRECTORY}

printf "\n#### Removing statistics file\n"
rm /var/mycodo/database/statistics.csv

${INSTALL_CMD} update-apt-packages
${INSTALL_CMD} update-pip
${INSTALL_CMD} update-pip-packages

printf "\n#### Checking for updates to dependencies\n"
python ${INSTALL_DIRECTORY}/mycodo/utils/check_dependencies_installed.py

${INSTALL_CMD} update-alembic
${INSTALL_CMD} compile-translations
${INSTALL_CMD} restart-daemon
