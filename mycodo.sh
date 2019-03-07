#!/bin/bash

if [ "$EUID" -ne 0 ] ; then
  printf "Please run as root.\n"
  exit 1
fi

INSTALL_PATH="$( cd -P "$( dirname "${SOURCE}" )" && pwd )"
cd ${INSTALL_PATH}

case "${1:-''}" in
    "install-dependencies")
        if ! [ -x "$(command -v docker)" ]; then
            printf "#### Installing docker\n" 2>&1 | tee -a ${LOG_LOCATION}
            curl -sSL https://get.docker.com | sh
        fi

        if ! [ -x "$(command -v docker-compose)" ]; then
            printf "#### Installing docker-compose\n" 2>&1 | tee -a ${LOG_LOCATION}
            pip install docker-compose
        fi

        if ! [ -x "$(command -v docker-compose)" ]; then
            printf "#### Installing logrotate\n" 2>&1 | tee -a ${LOG_LOCATION}
            apt install logrotate
        fi

        cp ./install/logrotate_docker /etc/logrotate.d/
        printf "#### Dependencies installed\n" 2>&1 | tee -a ${LOG_LOCATION}
    ;;
    "test")
        docker exec -ti flask /usr/local/bin/pip install --upgrade -r /home/mycodo/mycodo/tests/software_tests/requirements.txt
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
