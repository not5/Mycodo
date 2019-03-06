#!/bin/bash
#
#  upgrade_commands.sh - Mycodo commands
#
if [ "$EUID" -ne 0 ] ; then
  printf "Please run as root.\n"
  exit 1
fi

# Required apt packages. This has only been tested with Raspbian for the
# Raspberry Pi but should work with most debian-based systems.
APT_PKGS="fswebcam gawk gcc git libffi-dev libi2c-dev logrotate \
          moreutils nginx python-setuptools sqlite3 wget \
          python3 python3-dev python3-smbus python3-pylint-common"

PYTHON_BINARY_SYS_LOC="$(python3.5 -c "import os; print(os.environ['_'])")"

# Get the Mycodo root directory
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE" # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
MYCODO_PATH="$( cd -P "$( dirname "${SOURCE}" )/../.." && pwd )"

cd ${MYCODO_PATH}

HELP_OPTIONS="upgrade_commands.sh [option] - Program to execute various mycodo commands

Options:
  backup-create                 Create a backup of the ~/Mycodo directory
  backup-restore [backup]       Restore [backup] location, which must be the full path to the backup.
                                Ex.: '/var/Mycodo-backups/Mycodo-backup-2018-03-11_21-19-15-5.6.4/'
  compile-translations          Compile language translations for web interface
  create-files-directories      Create required directories
  restart-daemon                Restart the Mycodo daemon
  ssl-certs-generate            Generate SSL certificates for the web user interface
  update-alembic                Use alembic to upgrade the mycodo.db settings database
  update-apt                    Update apt sources
  install-bcm2835               Install bcm2835
  install-pigpiod               Install pigpiod
  install-wiringpi              Install wiringpi
  uninstall-pigpiod             Uninstall pigpiod
  disable-pigpiod               Disable pigpiod
  enable-pigpiod-low            Enable pigpiod with 1 ms sample rate
  enable-pigpiod-high           Enable pigpiod with 5 ms sample rate
  enable-pigpiod-disabled       Create empty service to indicate pigpiod is disabled
  update-pigpiod                Update to latest version of pigpiod service file
  update-logrotate              Install logrotate script
  update-packages               Install required apt packages are installed/up-to-date
  update-pip3                   Update pip
  update-pip3-packages          Update required pip packages
  update-swap-size              Ensure sqap size is sufficiently large (512 MB)
  upgrade                       Upgrade Mycodo to the latest release
  upgrade-major-release         Upgrade Mycodo to a major version release
  upgrade-master                Upgrade Mycodo to the master branch of the Mycodo github repository
  upgrade-post                  Post-Upgrade commands
"

case "${1:-''}" in
    'backup-create')
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/mycodo_backup_create.sh
    ;;
    'backup-restore')
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/mycodo_backup_restore.sh ${2}
    ;;
    'compile-translations')
        printf "\n#### Compiling Translations\n"
        cd ${MYCODO_PATH}/mycodo
        pybabel compile -d mycodo_flask/translations
    ;;
    'create-files-directories')
        printf "\n#### Creating files and directories\n"
        mkdir -p /var/mycodo/log
        mkdir -p /var/Mycodo-backups
        mkdir -p ${MYCODO_PATH}/note_attachments

        if [ ! -e /var/mycodo/log/mycodo.log ]; then
            touch /var/mycodo/log/mycodo.log
        fi
        if [ ! -e /var/mycodo/log/mycodobackup.log ]; then
            touch /var/mycodo/log/mycodobackup.log
        fi
        if [ ! -e /var/mycodo/log/mycodokeepup.log ]; then
            touch /var/mycodo/log/mycodokeepup.log
        fi
        if [ ! -e /var/mycodo/log/mycododependency.log ]; then
            touch /var/mycodo/log/mycododependency.log
        fi
        if [ ! -e /var/mycodo/log/mycodoupgrade.log ]; then
            touch /var/mycodo/log/mycodoupgrade.log
        fi
        if [ ! -e /var/mycodo/log/mycodorestore.log ]; then
            touch /var/mycodo/log/mycodorestore.log
        fi
        if [ ! -e /var/mycodo/log/login.log ]; then
            touch /var/mycodo/log/login.log
        fi

        # Create empty mycodo database file if it doesn't exist
        if [ ! -e ${MYCODO_PATH}/databases/mycodo.db ]; then
            touch ${MYCODO_PATH}/databases/mycodo.db
        fi
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh update-permissions
    ;;
    'restart-daemon')
        printf "\n#### Restarting the Mycodo daemon\n"
        python ${MYCODO_PATH}/mycodo/mycodo_client.py -t
    ;;
    'ssl-certs-generate')
        printf "\n#### Generating SSL certificates at ${MYCODO_PATH}/mycodo/mycodo_flask/ssl_certs (replace with your own if desired)\n"
        cd /var/mycodo/ssl_certs/
        rm -f ./*.pem ./*.csr ./*.crt ./*.key
        openssl genrsa \
            -out /var/mycodo/ssl_certs/server.pass.key 4096
        openssl rsa \
            -in /var/mycodo/ssl_certs/server.pass.key \
            -out /var/mycodo/ssl_certs/server.key
        rm -f /var/mycodo/ssl_certs/server.pass.key
        openssl req -new \
            -key /var/mycodo/ssl_certs/server.key \
            -out /var/mycodo/ssl_certs/server.csr \
            -subj "/O=mycodo/OU=mycodo/CN=mycodo"
        openssl x509 -req \
            -days 3653 \
            -in /var/mycodo/ssl_certs/server.csr \
            -signkey /var/mycodo/ssl_certs/server.key \
            -out /var/mycodo/ssl_certs/server.crt
    ;;
    'update-alembic')
        printf "\n#### Upgrading Mycodo database with alembic (if needed)\n"
        cd ${MYCODO_PATH}/mycodo/database_version
        ${MYCODO_PATH}/env/bin/alembic upgrade head
    ;;
    'update-apt')
        printf "\n\n#### Updating apt repositories\n"
        apt-get update
    ;;
    'install-bcm2835')
        printf "\n#### Installing bcm2835\n"
        cd ${MYCODO_PATH}/install
        apt-get install -y automake libtool
        wget http://www.airspayce.com/mikem/bcm2835/bcm2835-1.50.tar.gz
        tar zxvf bcm2835-1.50.tar.gz
        cd bcm2835-1.50
        autoreconf -vfi
        ./configure
        make
        sudo make check
        sudo make install
        cd ${MYCODO_PATH}/install
        rm -rf ./bcm2835-1.50
    ;;
    'install-wiringpi')
        cd ${MYCODO_PATH}/install
        git clone --recursive https://github.com/WiringPi/WiringPi-Python.git
        cd WiringPi-Python
        git submodule update --init
        cd WiringPi
        ./build
        cd ${MYCODO_PATH}/install
        rm -rf ./WiringPi-Python
    ;;
    'install-pigpiod')
        printf "\n#### Installing pigpiod\n"
        apt-get install -y python3-pigpio
        cd ${MYCODO_PATH}/install
        # wget --quiet -P ${MYCODO_PATH}/install abyz.co.uk/rpi/pigpio/pigpio.zip
        tar xf pigpio.tar
        cd ${MYCODO_PATH}/install/PIGPIO
        make -j4
        make install
        cd ${MYCODO_PATH}/install
        rm -rf ./PIGPIO
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh disable-pigpiod
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh enable-pigpiod-low
        mkdir -p /opt/mycodo
        touch /opt/mycodo/pigpio_installed
    ;;
    'uninstall-pigpiod')
        printf "\n#### Uninstalling pigpiod\n"
        apt-get remove -y python3-pigpio
        cd ${MYCODO_PATH}/install
        # wget --quiet -P ${MYCODO_PATH}/install abyz.co.uk/rpi/pigpio/pigpio.zip
        tar xf pigpio.tar
        cd ${MYCODO_PATH}/install/PIGPIO
        make uninstall
        cd ${MYCODO_PATH}/install
        rm -rf ./PIGPIO
        touch /etc/systemd/system/pigpiod_uninstalled.service
        rm -f /opt/mycodo/pigpio_installed
    ;;
    'disable-pigpiod')
        printf "\n#### Disabling installed pigpiod startup script\n"
        service pigpiod stop
        systemctl disable pigpiod.service
        rm -rf /etc/systemd/system/pigpiod.service
        systemctl disable pigpiod_low.service
        rm -rf /etc/systemd/system/pigpiod_low.service
        systemctl disable pigpiod_high.service
        rm -rf /etc/systemd/system/pigpiod_high.service
        rm -rf /etc/systemd/system/pigpiod_disabled.service
        rm -rf /etc/systemd/system/pigpiod_uninstalled.service
    ;;
    'enable-pigpiod-low')
        printf "\n#### Enabling pigpiod startup script (1 ms sample rate)\n"
        systemctl enable ${MYCODO_PATH}/install/pigpiod_low.service
        service pigpiod restart
    ;;
    'enable-pigpiod-high')
        printf "\n#### Enabling pigpiod startup script (5 ms sample rate)\n"
        systemctl enable ${MYCODO_PATH}/install/pigpiod_high.service
        service pigpiod restart
    ;;
    'enable-pigpiod-disabled')
        printf "\n#### pigpiod has been disabled. It can be enabled in the web UI configuration\n"
        touch /etc/systemd/system/pigpiod_disabled.service
    ;;
    'update-pigpiod')
        printf "\n#### Checking which pigpiod startup script is being used\n"
        GPIOD_SAMPLE_RATE=99
        if [ -e /etc/systemd/system/pigpiod_low.service ]; then
            GPIOD_SAMPLE_RATE=1
        elif [ -e /etc/systemd/system/pigpiod_high.service ]; then
            GPIOD_SAMPLE_RATE=5
        elif [ -e /etc/systemd/system/pigpiod_disabled.service ]; then
            GPIOD_SAMPLE_RATE=100
        fi

        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh disable-pigpiod

        if [ "$GPIOD_SAMPLE_RATE" -eq "1" ]; then
            /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh enable-pigpiod-low
        elif [ "$GPIOD_SAMPLE_RATE" -eq "5" ]; then
            /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh enable-pigpiod-high
        elif [ "$GPIOD_SAMPLE_RATE" -eq "100" ]; then
            /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh enable-pigpiod-disabled
        else
            printf "#### Could not determine pgiod sample rate. Setting up pigpiod with 1 ms sample rate\n"
            /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_commands.sh enable-pigpiod-low
        fi
    ;;
    'update-logrotate')
        printf "\n#### Installing logrotate scripts\n"
        if [ -e /etc/cron.daily/logrotate ]; then
            printf "#### logrotate execution moved from cron.daily to cron.hourly\n"
            mv -f /etc/cron.daily/logrotate /etc/cron.hourly/
        fi
        cp -f ${MYCODO_PATH}/install/logrotate_mycodo /etc/logrotate.d/mycodo
        printf "#### Mycodo logrotate script installed\n"
    ;;
    'update-packages')
        printf "\n#### Installing prerequisite apt packages and update pip\n"
        apt-get update -y
        apt-get remove -y apache2
        apt-get install -y ${APT_PKGS}
        easy_install pip
        pip install --upgrade pip
    ;;
    'update-pip3')
        printf "\n#### Updating pip\n"
        pip install --upgrade pip
    ;;
    'update-pip3-packages')
        printf "\n#### Installing pip requirements from requirements.txt\n"
        pip install --upgrade pip setuptools
        pip install --upgrade -r ${MYCODO_PATH}/install/requirements.txt
    ;;
    'upgrade')
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_mycodo_release.sh
    ;;
    'upgrade-master')
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_mycodo_release.sh force-upgrade-master
    ;;
    'upgrade-release-major')
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_mycodo_release_maj.sh ${2}
    ;;
    'upgrade-post')
        /bin/bash ${MYCODO_PATH}/mycodo/scripts/upgrade_post.sh
    ;;
    *)
        printf "Error: Unrecognized command: ${1}\n${HELP_OPTIONS}"
        exit 1
    ;;
esac
