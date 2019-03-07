FROM python:3.6-slim-stretch

RUN mkdir -pv /home/mycodo
COPY . /home/mycodo

WORKDIR /home/mycodo/mycodo

RUN mkdir -pv /var/database
RUN mkdir -pv /var/lock
RUN mkdir -pv /var/mycodo/ssl_certs
RUN mkdir -pv /var/mycodo/database

RUN apt-get update && apt-get install -y moreutils wget gcc

RUN pip install --no-cache-dir -r /home/mycodo/requirements.txt

RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh create-files-directories
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh ssl-certs-generate
RUN /home/mycodo/mycodo/scripts/upgrade_commands.sh compile-translations
