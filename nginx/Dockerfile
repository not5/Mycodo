FROM nginx:1.15.9

RUN rm /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx/

RUN rm /etc/nginx/conf.d/default.conf
COPY project.conf /etc/nginx/conf.d/

RUN mkdir -pv /var/mycodo
COPY 502.html /var/mycodo/
