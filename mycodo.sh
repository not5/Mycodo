#!/bin/bash

if [ "$EUID" -ne 0 ] ; then
  printf "Please run as root.\n"
  exit 1
fi

INSTALL_PATH="$( cd -P "$( dirname "${SOURCE}" )" && pwd )"
cd ${INSTALL_PATH}

case "${1:-''}" in
    "install-dependencies")
        printf "\n#### Checking for python 3 virtualenv at ${INSTALL_PATH}/env/bin/python3\n" 2>&1 | tee -a ${LOG_LOCATION}
        if [ ! -L ${INSTALL_PATH}/env/bin/python3 ]; then
            printf "#### Virtualenv doesn't exist. Creating...\n" 2>&1 | tee -a ${LOG_LOCATION}
            pip install virtualenv --upgrade
            rm -rf ${INSTALL_PATH}/env
            PYTHON_BINARY_SYS_LOC="$(python3.5 -c "import os; print(os.environ['_'])")"
            virtualenv --system-site-packages -p ${PYTHON_BINARY_SYS_LOC} ${INSTALL_PATH}/env
        else
            printf "#### Virtualenv already exists, skipping creation\n" 2>&1 | tee -a ${LOG_LOCATION}
        fi

        apt install -y python3-dev libffi-dev libssl-dev

        if ! [ -x "$(command -v docker)" ]; then
            printf "#### Installing docker\n" 2>&1 | tee -a ${LOG_LOCATION}
            curl -sSL https://get.docker.com | sh
        fi

        if ! [ -x "$(command -v docker-compose)" ]; then
            printf "#### Installing docker-compose\n" 2>&1 | tee -a ${LOG_LOCATION}
            ${INSTALL_PATH}/env/bin/pip install docker-compose
        fi

        if ! [ -x "$(command -v docker-compose)" ]; then
            printf "#### Installing logrotate\n" 2>&1 | tee -a ${LOG_LOCATION}
            apt install logrotate
        fi

        cp ./install/logrotate_docker /etc/logrotate.d/
        printf "#### Dependencies installed\n" 2>&1 | tee -a ${LOG_LOCATION}
    ;;
    "test")
        docker exec -ti flask ${INSTALL_PATH}/env/bin/pip install --upgrade -r /home/mycodo/mycodo/tests/software_tests/requirements.txt
        docker exec -ti flask pytest /home/mycodo/mycodo/tests/software_tests
    ;;
    "clean-all")
        docker container stop $(docker container ls -a -q) && docker system prune -a -f --volumes
    ;;
    *)
        printf "Error: Unrecognized command: ${1}\n${HELP_OPTIONS}"
        exit 1
    ;;
esac
