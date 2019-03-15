FROM python:3.6-slim-stretch

RUN mkdir -pv /home/mycodo
COPY . /home/mycodo

WORKDIR /home/mycodo/mycodo

RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh create-files-directories
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh update-apt-packages
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh update-pip
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh update-pip-packages
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh ssl-certs-generate
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh compile-translations
