install-docker:
    curl -sSL https://get.docker.com | sh
    sudo pip install docker-compose

dependencies:
    sudo apt install logrotate
    cp ./install/logrotate_docker /etc/logrotate.d/
    sudo service logrotate restart

build:
    docker-compose up --build -d

test:
    docker exec -ti flask /usr/local/bin/pip install --upgrade testfixtures==6.4.1 mock==2.0.0 pytest==4.0.2 factory_boy==2.11.1 webtest==2.0.32
    docker exec -ti flask pytest /home/mycodo/mycodo/tests/software_tests

clean:
    docker-compose down
    docker system prune -a
