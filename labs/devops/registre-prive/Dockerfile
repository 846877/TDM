# Hôte Docker (Docker dans Docker) pour héberger et utiliser un registre d'images privé.
FROM docker:28-dind
RUN apk add --no-cache curl apache2-utils jq
COPY appli/ /root/appli/
RUN mkdir -p /root/registre
WORKDIR /root
