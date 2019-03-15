#!/bin/bash
# Upgrade to the latest major version release
# Usage:
# sudo /bin/bash ./upgrade_mycodo_release_maj.sh [major version number]

if [ "$EUID" -ne 0 ] ; then
  printf "Please run as root.\n"
  exit 1
fi

INSTALL_DIRECTORY=$( cd "$( dirname "${BASH_SOURCE[0]}" )/../../.." && pwd -P )
cd ${INSTALL_DIRECTORY}

runSelfUpgrade() {
  INSTALL_DIRECTORY=$( cd -P /home/mycodo/.. && pwd -P )
  echo '1' > /var/mycodo/.upgrade

  function error_found {
    echo '2' > /var/mycodo/.upgrade
    printf "\n\n"
    printf "#### ERROR ####\n"
    printf "There was an error detected during the upgrade. Please review the log at /var/mycodo/log/upgrade.log"
    exit 1
  }

  NOW=$(date +"%Y-%m-%d_%H-%M-%S")
  CURRENT_VERSION=$(python ${INSTALL_DIRECTORY}/mycodo/mycodo/utils/github_release_info.py -c 2>&1)
  BACKUP_DIR="/var/mycodo/Mycodo-backups/Mycodo-backup-${NOW}-${CURRENT_VERSION}"
  UPDATE_VERSION=$(python ${INSTALL_DIRECTORY}/mycodo/mycodo/utils/github_release_info.py -m ${1} -v 2>&1)
  MYCODO_NEW_TMP_DIR="/tmp/Mycodo-${UPDATE_VERSION}"
  UPDATE_URL=$(python ${INSTALL_DIRECTORY}/mycodo/mycodo/utils/github_release_info.py -m ${1} 2>&1)
  TARBALL_FILE="mycodo-${UPDATE_VERSION}"

  printf "\n"

  # If this script is executed with the 'force-upgrade-master' argument,
  # an upgrade will be performed with the latest git commit from the repo
  # master instead of the release version

  if [ "${CURRENT_VERSION}" == "${UPDATE_VERSION}" ] ; then
    printf "Unable to upgrade. You currently have the latest release installed.\n"
    error_found
  else
    printf "\nInstalled version: ${CURRENT_VERSION}\n"
    printf "Latest version: ${UPDATE_VERSION}\n"
  fi

  if [ "${UPDATE_URL}" == "None" ] ; then
    printf "\nUnable to upgrade. A URL of the latest release was not able to be obtained.\n"
    error_found
  fi

  printf "\n#### Upgrade to v${UPDATE_VERSION} initiated ${NOW} ####\n"
  printf "\n#### Beginning Upgrade: Stage 1 of 2 ####\n"

  printf "Stopping the Mycodo daemon..."
  if ! service mycodo stop ; then
    printf "Error: Unable to stop the daemon. Continuing anyway...\n"
  fi
  printf "Done.\n"

  printf "Downloading latest Mycodo version to ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz..."
  if ! wget --quiet -O ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz ${UPDATE_URL} ; then
    printf "Failed: Error while trying to wget new version.\n"
    printf "File requested: ${UPDATE_URL} -> ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz\n"
    error_found
  fi
  printf "Done.\n"

  if [ -d "${MYCODO_NEW_TMP_DIR}" ] ; then
    printf "The tmp directory ${MYCODO_NEW_TMP_DIR} already exists. Removing..."
    if ! rm -Rf ${MYCODO_NEW_TMP_DIR} ; then
      printf "Failed: Error while trying to delete tmp directory ${MYCODO_NEW_TMP_DIR}.\n"
      error_found
    fi
    printf "Done.\n"
  fi

  printf "Creating ${MYCODO_NEW_TMP_DIR}..."
  if ! mkdir ${MYCODO_NEW_TMP_DIR} ; then
    printf "Failed: Error while trying to create ${MYCODO_NEW_TMP_DIR}.\n"
    error_found
  fi
  printf "Done.\n"

  printf "Extracting ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz to ${MYCODO_NEW_TMP_DIR}..."
  if ! tar xzf ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz -C ${MYCODO_NEW_TMP_DIR} --strip-components=1 ; then
    printf "Failed: Error while trying to extract files from ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz to ${MYCODO_NEW_TMP_DIR}.\n"
    error_found
  fi
  printf "Done.\n"

  printf "Removing ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz..."
  if ! rm -rf ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz ; then
    printf "Failed: Error while removing ${INSTALL_DIRECTORY}/${TARBALL_FILE}.tar.gz.\n"
  fi
  printf "Done.\n"

  printf "#### Stage 1 of 2 Complete ####\n"

  # Spawn upgrade script
  cat > /tmp/upgrade_mycodo_stagetwo.sh << EOF
#!/bin/bash

function error_found {
  printf "\n\n"
  printf "There was an error during the upgrade.\n"
  printf "Initial steps to try to fix:\n"
  printf "1. Reboot\n"
  printf "2. If that doesn't fix the issue, run the following command:\n"
  printf "sudo /bin/bash ~/Mycodo/mycodo/scripts/upgrade_commands.sh upgrade\n"
  printf "3. If that command returns that you are running the latest version, run the following command:\n"
  printf "sudo /bin/bash ~/Mycodo/mycodo/scripts/upgrade_post.sh\n\n"
  echo '2' > /var/mycodo/.upgrade
  exit 1
}

printf "\n#### Continuing Upgrade: Stage 2 of 2 ####\n"

if [ ! -d "/var/mycodo/Mycodo-backups" ] ; then
  mkdir /var/mycodo/Mycodo-backups
fi

printf "\nMoving old Mycodo from ${INSTALL_DIRECTORY}/mycodo to ${BACKUP_DIR}..."
if ! mv ${INSTALL_DIRECTORY}/mycodo ${BACKUP_DIR} ; then
  printf "Failed: Error while trying to move old Mycodo install from ${INSTALL_DIRECTORY}/mycodo to ${BACKUP_DIR}.\n"
  error_found
fi
printf "Done.\n"

printf "Moving new Mycodo from ${MYCODO_NEW_TMP_DIR} to ${INSTALL_DIRECTORY}/mycodo..."
if ! mv ${MYCODO_NEW_TMP_DIR} ${INSTALL_DIRECTORY}/mycodo ; then
  printf "Failed: Error while trying to move new Mycodo install from ${MYCODO_NEW_TMP_DIR} to ${INSTALL_DIRECTORY}/mycodo.\n"
  error_found
fi
printf "Done.\n"

sleep 30

cd ${INSTALL_DIRECTORY}/mycodo

printf "\nRunning post-upgrade script...\n"
if ! ${INSTALL_DIRECTORY}/mycodo/mycodo/scripts/upgrade_post.sh ; then
  printf "Failed: Error while running post-upgrade script.\n"
  error_found
fi
printf "Done.\n\n"

printf "Upgrade completed successfully without errors.\n"

echo '0' > /var/mycodo/.upgrade
rm \$0
EOF
  exec /bin/bash /tmp/upgrade_mycodo_stagetwo.sh
}

runSelfUpgrade "${1}"
