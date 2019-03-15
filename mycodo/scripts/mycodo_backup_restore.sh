#!/bin/bash

if [ "$EUID" -ne 0 ] ; then
    printf "Please run as root.\n"
    exit 1
fi

if [ ! -e $1 ]; then
    echo "Directory does not exist"
    exit 1
elif [ ! -d $1 ]; then
    echo "Input not a directory"
    exit 2
fi

INSTALL_DIRECTORY=$( cd -P /home/mycodo/.. && pwd -P )
echo '1' > /var/mycodo/.restore

function error_found {
    echo '2' > /var/mycodo/.restore
    printf "\n\n"
    date
    printf "#### ERROR ####\n"
    printf "There was an error detected during the restore. Please review the log at /var/log/mycodo/mycodorestore.log"
    exit 1
}

CURRENT_VERSION=$(python ${INSTALL_DIRECTORY}/mycodo/mycodo/utils/github_release_info.py -c 2>&1)
NOW=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_DIR="/var/mycodo/Mycodo-backups/Mycodo-backup-${NOW}-${CURRENT_VERSION}"

printf "\n#### Restore of backup $1 initiated $NOW ####\n"

printf "\nBacking up current Mycodo from ${INSTALL_DIRECTORY}/mycodo to ${BACKUP_DIR}..."
if ! mv ${INSTALL_DIRECTORY}/mycodo ${BACKUP_DIR} ; then
    printf "Failed: Error while trying to back up current Mycodo install from ${INSTALL_DIRECTORY}/mycodo to ${BACKUP_DIR}.\n"
    error_found
fi
printf "Done.\n"

printf "\nRestoring Mycodo from $1 to ${INSTALL_DIRECTORY}/mycodo..."
if ! mv $1 ${INSTALL_DIRECTORY}/mycodo ; then
    printf "Failed: Error while trying to restore Mycodo backup from ${INSTALL_DIRECTORY}/mycodo to ${BACKUP_DIR}.\n"
    error_found
fi
printf "Done.\n"

sleep 10

printf "\n\nRunning post-restore script...\n"
if ! ${INSTALL_DIRECTORY}/mycodo/mycodo/scripts/upgrade_post.sh ; then
  printf "Failed: Error while running post-restore script.\n"
  error_found
fi
printf "Done.\n\n"

date
printf "Restore completed successfully without errors.\n"

echo '0' > /var/mycodo/.restore
