FROM python:3.6-slim-stretch

RUN mkdir -pv /home/mycodo
COPY . /home/mycodo

WORKDIR /home/mycodo/mycodo

RUN mkdir -pv /var/database
RUN mkdir -pv /var/lock
RUN mkdir -pv /var/mycodo/ssl_certs
RUN mkdir -pv /var/mycodo/database

RUN mkdir -pv /var/mycodo/log
RUN touch /var/mycodo/log/mycodo.log
RUN touch /var/mycodo/log/mycodobackup.log
RUN touch /var/mycodo/log/mycodokeepup.log
RUN touch /var/mycodo/log/mycododependency.log
RUN touch /var/mycodo/log/mycodoupgrade.log
RUN touch /var/mycodo/log/mycodorestore.log
RUN touch /var/mycodo/log/login.log

RUN apt-get update
RUN apt-get install -y fswebcam gawk gcc libffi-dev libi2c-dev logrotate moreutils sqlite3 wget

RUN pip install --no-cache-dir -r /home/mycodo/requirements.txt

RUN openssl genrsa \
    -out /var/mycodo/ssl_certs/server.pass.key 4096
RUN openssl rsa \
    -in /var/mycodo/ssl_certs/server.pass.key \
    -out /var/mycodo/ssl_certs/server.key
RUN rm -f /var/mycodo/ssl_certs/server.pass.key
RUN openssl req -new \
    -key /var/mycodo/ssl_certs/server.key \
    -out /var/mycodo/ssl_certs/server.csr \
    -subj "/O=mycodo/OU=mycodo/CN=mycodo"
RUN openssl x509 -req \
    -days 3653 \
    -in /var/mycodo/ssl_certs/server.csr \
    -signkey /var/mycodo/ssl_certs/server.key \
    -out /var/mycodo/ssl_certs/server.crt
