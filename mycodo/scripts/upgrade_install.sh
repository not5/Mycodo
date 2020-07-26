#!/bin/bash
# Upgrade from a previous release to this current release.
# Check currently-installed version for the ability to upgrade to this release version.

exec 2>&1

RELEASE_WIPE=$1

if [ "$EUID" -ne 0 ] ; then
  printf "Must be run as root.\n"
  exit 1
fi

runSelfUpgrade() {
  function error_found {
    echo '2' > "${INSTALL_DIRECTORY}"/Mycodo/.upgrade
    printf "\n\n"
    printf "#### ERROR ####\n"
    printf "There was an error detected during the upgrade. Please review the log at /var/log/mycodo/mycodoupgrade.log"
    exit 1
  }

  printf "\n#### Beginning Upgrade Stage 2 of 3 ####\n\n"
  TIMER_START_stage_two=$SECONDS

  printf "RELEASE_WIPE = %s\n" "$RELEASE_WIPE"

  CURRENT_MYCODO_DIRECTORY=$( cd -P /var/mycodo-root && pwd -P )
  CURRENT_MYCODO_INSTALL_DIRECTORY=$( cd -P /var/mycodo-root/.. && pwd -P )
  THIS_MYCODO_DIRECTORY=$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd -P )
  NOW=$(date +"%Y-%m-%d_%H-%M-%S")

  if [ "$CURRENT_MYCODO_DIRECTORY" == "$THIS_MYCODO_DIRECTORY" ] ; then
    printf "Cannot perform upgrade to the Mycodo instance already intalled. Halting upgrade.\n"
    exit 1
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}" ] ; then
    printf "Found currently-installed version of Mycodo. Checking version...\n"
    CURRENT_VERSION=$("${CURRENT_MYCODO_INSTALL_DIRECTORY}"/Mycodo/env/bin/python3 "${CURRENT_MYCODO_INSTALL_DIRECTORY}"/Mycodo/mycodo/utils/github_release_info.py -c 2>&1)
    MAJOR=$(echo "$CURRENT_VERSION" | cut -d. -f1)
    MINOR=$(echo "$CURRENT_VERSION" | cut -d. -f2)
    REVISION=$(echo "$CURRENT_VERSION" | cut -d. -f3)
    if [ -z "$MAJOR" ] || [ -z "$MINOR" ] || [ -z "$REVISION" ] ; then
      printf "Could not determine Mycodo version\n"
      exit 1
    else
      printf "Mycodo version found installed: %s.%s.%s\n" "${MAJOR}" "${MINOR}" "${REVISION}"
    fi
  else
    printf "Could not find a current version of Mycodo installed. Check the symlink /var/mycdo-root that is supposed to point to the install directory"
    exit 1
  fi

  ################################
  # Begin tests prior to upgrade #
  ################################

  printf "\n#### Beginning pre-upgrade checks ####\n\n"

  # Maintenance mode
  # This is a temporary state so the developer can test a version release before users can upgrade.
  # Creating the file ~/Mycodo/.maintenance will override maintenece mode.
  if python "${CURRENT_MYCODO_DIRECTORY}"/mycodo/scripts/upgrade_check.py --maintenance_mode; then
    if [[ ! -e $CURRENT_MYCODO_DIRECTORY/.maintenance ]]; then
      printf "The Mycodo upgrade system is currently in maintenance mode so the developer can test the latest upgrade.\n"
      printf "Please wait and attempt the upgrade later.\n"
      echo '0' > "${CURRENT_MYCODO_DIRECTORY}"/.upgrade
      exit 1
    fi
  fi

  # Upgrade requires Python >= 3.6
  printf "Checking Python version...\n"
  if hash python3 2>/dev/null; then
    if ! python3 "${CURRENT_MYCODO_DIRECTORY}"/mycodo/scripts/upgrade_check.py --min_python_version "3.6"; then
      printf "\nIncorrect Python version found. Mycodo requires Python >= 3.6.\n"
      printf "If you're running Raspbian 9 (Stretch) with Python 3.5, you will need to install at least Raspbian 10 (Buster) with Python 3.7 to upgrade to the latest version of Mycodo.\n"
      echo '0' > "${CURRENT_MYCODO_DIRECTORY}"/.upgrade
      exit 1
    else
      printf "Python >= 3.6 found. Continuing with the upgrade.\n"
    fi
  else
    printf "\npython3 was not found. Cannot proceed with the upgrade without python3 (Python >= 3.6).\n"
    echo '0' > "${CURRENT_MYCODO_DIRECTORY}"/.upgrade
    exit 1
  fi

  # If upgrading from version 7 and Python >= 3.6 found (from previous check), upgrade without wiping database
  if [[ "$MAJOR" == 7 ]] && [[ "$RELEASE_WIPE" = true ]]; then
    printf "Your system was found to have Python >= 3.6 installed. Proceeding with upgrade without wiping database.\n"
    RELEASE_WIPE=false
  fi

  printf "All pre-upgrade checks passed. Proceeding with upgrade.\n\n"

  ##############################
  # End tests prior to upgrade #
  ##############################

  THIS_VERSION=$("${CURRENT_MYCODO_DIRECTORY}"/env/bin/python3 "${THIS_MYCODO_DIRECTORY}"/mycodo/utils/github_release_info.py -c 2>&1)
  printf "Upgrading Mycodo to version %s\n\n" "$THIS_VERSION"

  printf "Stopping the Mycodo daemon..."
  if ! service mycodo stop ; then
    printf "Error: Unable to stop the daemon. Continuing anyway...\n"
  fi
  printf "Done.\n"

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/env ] ; then
    printf "Moving env directory..."
    if ! mv "${CURRENT_MYCODO_DIRECTORY}"/env "${THIS_MYCODO_DIRECTORY}" ; then
      printf "Failed: Error while trying to move env directory.\n"
      error_found
    fi
    printf "Done.\n"
  fi

  printf "Copying databases..."
  if ! cp "${CURRENT_MYCODO_DIRECTORY}"/databases/*.db "${THIS_MYCODO_DIRECTORY}"/databases ; then
    printf "Failed: Error while trying to copy databases."
    error_found
  fi
  printf "Done.\n"

  printf "Copying flask_secret_key..."
  if ! cp "${CURRENT_MYCODO_DIRECTORY}"/databases/flask_secret_key "${THIS_MYCODO_DIRECTORY}"/databases ; then
    printf "Failed: Error while trying to copy flask_secret_key."
  fi
  printf "Done.\n"

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/mycodo/mycodo_flask/ssl_certs ] ; then
    printf "Copying SSL certificates..."
    if ! cp -R "${CURRENT_MYCODO_DIRECTORY}"/mycodo/mycodo_flask/ssl_certs "${THIS_MYCODO_DIRECTORY}"/mycodo/mycodo_flask/ssl_certs ; then
      printf "Failed: Error while trying to copy SSL certificates."
      error_found
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/mycodo/controllers/custom_controllers ] ; then
    printf "Copying mycodo/controllers/custom_controllers..."
    if ! cp "${CURRENT_MYCODO_DIRECTORY}"/mycodo/controllers/custom_controllers/*.py "${THIS_MYCODO_DIRECTORY}"/mycodo/controllers/custom_controllers/ ; then
      printf "Failed: Error while trying to copy mycodo/controllers/custom_controllers"
      error_found
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/mycodo/inputs/custom_inputs ] ; then
    printf "Copying mycodo/inputs/custom_inputs..."
    if ! cp "${CURRENT_MYCODO_DIRECTORY}"/mycodo/inputs/custom_inputs/*.py "${THIS_MYCODO_DIRECTORY}"/mycodo/inputs/custom_inputs/ ; then
      printf "Failed: Error while trying to copy mycodo/inputs/custom_inputs"
      error_found
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/mycodo/outputs/custom_outputs ] ; then
    printf "Copying mycodo/outputs/custom_outputs..."
    if ! cp "${CURRENT_MYCODO_DIRECTORY}"/mycodo/outputs/custom_outputs/*.py "${THIS_MYCODO_DIRECTORY}"/mycodo/outputs/custom_outputs/ ; then
      printf "Failed: Error while trying to copy mycodo/outputs/custom_outputs"
      error_found
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/mycodo/user_python_code ] ; then
    printf "Copying mycodo/user_python_code..."
    if ! cp "${CURRENT_MYCODO_DIRECTORY}"/mycodo/user_python_code/*.py "${THIS_MYCODO_DIRECTORY}"/mycodo/user_python_code/ ; then
      printf "Failed: Error while trying to copy mycodo/user_python_code"
      error_found
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/output_usage_reports ] ; then
    printf "Moving output_usage_reports directory..."
    if ! mv "${CURRENT_MYCODO_DIRECTORY}"/output_usage_reports "${THIS_MYCODO_DIRECTORY}" ; then
      printf "Failed: Error while trying to move output_usage_reports directory.\n"
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/cameras ] ; then
    printf "Moving cameras directory..."
    if ! mv "${CURRENT_MYCODO_DIRECTORY}"/cameras "${THIS_MYCODO_DIRECTORY}" ; then
      printf "Failed: Error while trying to move cameras directory.\n"
    fi
    printf "Done.\n"
  fi

  if [ -d "${CURRENT_MYCODO_DIRECTORY}"/.upgrade ] ; then
    printf "Moving .upgrade file..."
    if ! mv "${CURRENT_MYCODO_DIRECTORY}"/.upgrade "${THIS_MYCODO_DIRECTORY}" ; then
      printf "Failed: Error while trying to move .upgrade file.\n"
    fi
    printf "Done.\n"
  fi

  if [ ! -d "/var/Mycodo-backups" ] ; then
    mkdir /var/Mycodo-backups
  fi

  BACKUP_DIR="/var/Mycodo-backups/Mycodo-backup-${NOW}-${CURRENT_VERSION}"

  printf "Moving current Mycodo intstall from %s to %s..." "${CURRENT_MYCODO_DIRECTORY}" "${BACKUP_DIR}"
  if ! mv "${CURRENT_MYCODO_DIRECTORY}" "${BACKUP_DIR}" ; then
    printf "Failed: Error while trying to move old Mycodo install from %s to %s.\n" "${CURRENT_MYCODO_DIRECTORY}" "${BACKUP_DIR}"
    error_found
  fi
  printf "Done.\n"

  printf "Moving downloaded Mycodo version from %s to %s/Mycodo..." "${THIS_MYCODO_DIRECTORY}" "${CURRENT_MYCODO_INSTALL_DIRECTORY}"
  if ! mv "${THIS_MYCODO_DIRECTORY}" "${CURRENT_MYCODO_INSTALL_DIRECTORY}"/Mycodo ; then
    printf "Failed: Error while trying to move new Mycodo install from %s to %s/Mycodo.\n" "${THIS_MYCODO_DIRECTORY}" "${CURRENT_MYCODO_INSTALL_DIRECTORY}"
    error_found
  fi
  printf "Done.\n"

  sleep 30

  CURRENT_MYCODO_DIRECTORY=$( cd -P /var/mycodo-root && pwd -P )
  cd "${CURRENT_MYCODO_DIRECTORY}" || return

  ############################################
  # Begin tests prior to post-upgrade script #
  ############################################

  if [ "$RELEASE_WIPE" = true ] ; then
    # Instructed to wipe configuration files (database, virtualenv)

    if [ -d "${CURRENT_MYCODO_DIRECTORY}"/env ] ; then
      printf "Removing virtaulenv at %s/env..." "${CURRENT_MYCODO_DIRECTORY}"
      if ! rm -rf "${CURRENT_MYCODO_DIRECTORY}"/env ; then
        printf "Failed: Error while trying to delete virtaulenv.\n"
      fi
      printf "Done.\n"
    fi

    if [ -d "${CURRENT_MYCODO_DIRECTORY}"/databases/mycodo.db ] ; then
      printf "Removing database at %s/databases/mycodo.db..." "${CURRENT_MYCODO_DIRECTORY}"
      if ! rm -f "${CURRENT_MYCODO_DIRECTORY}"/databases/mycodo.db ; then
        printf "Failed: Error while trying to delete database.\n"
      fi
      printf "Done.\n"
    fi

  fi

  printf "\n#### Completed Upgrade Stage 2 of 3 in %s seconds ####\n" "$((SECONDS - TIMER_START_stage_two))"

  ##########################################
  # End tests prior to post-upgrade script #
  ##########################################

  printf "\n#### Beginning Upgrade Stage 3 of 3 ####\n\n"
  TIMER_START_stage_three=$SECONDS

  printf "Running post-upgrade script...\n"
  if ! "${CURRENT_MYCODO_DIRECTORY}"/mycodo/scripts/upgrade_post.sh ; then
    printf "Failed: Error while running post-upgrade script.\n"
    error_found
  fi

  printf "\n#### Completed Upgrade Stage 3 of 3 in %s seconds ####\n\n" "$((SECONDS - TIMER_START_stage_three))"

  printf "Upgrade completed successfully without errors.\n"

  #############################
  # Begin tests after upgrade #
  #############################



  ###########################
  # End tests after upgrade #
  ###########################

  echo '0' > "${CURRENT_MYCODO_DIRECTORY}"/.upgrade

  exit 0
}

runSelfUpgrade
