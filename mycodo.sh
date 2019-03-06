#!/bin/bash

if [ "$EUID" -ne 0 ] ; then
  printf "Please run as root.\n"
  exit 1
fi

case "${1:-''}" in
    "install-dependencies")
        if [ -x "$(command -v docker)" ]; then
            printf "#### docker already installed, skipping.\n" 2>&1 | tee -a ${LOG_LOCATION}
        else
            printf "#### docker not found, installing...\n" 2>&1 | tee -a ${LOG_LOCATION}
            curl -sSL https://get.docker.com | sh
        fi

        if [ -x "$(command -v docker-compose)" ]; then
            printf "#### docker-compose already installed, skipping.\n" 2>&1 | tee -a ${LOG_LOCATION}
        else
            printf "#### docker-compose not found, installing...\n" 2>&1 | tee -a ${LOG_LOCATION}
            pip install docker-compose
        fi

        apt install logrotate
        cp ./install/logrotate_docker /etc/logrotate.d/
        service logrotate restart
    ;;
    "test")
        docker exec -ti flask /usr/local/bin/pip install --upgrade testfixtures==6.4.1 mock==2.0.0 pytest==4.0.2 factory_boy==2.11.1 webtest==2.0.32
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
