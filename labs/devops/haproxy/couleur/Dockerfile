# Petite application « colorée » : répond sur le port 8080 avec le nom de sa couleur.
FROM nginx:1.27-alpine
ARG COULEUR=red
COPY default.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s/COULEUR/${COULEUR}/g" /etc/nginx/conf.d/default.conf
