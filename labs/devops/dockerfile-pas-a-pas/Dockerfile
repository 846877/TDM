# Hôte Docker (Docker dans Docker) avec un petit projet à conteneuriser étape par étape.
FROM docker:28-dind
COPY projet/ /root/projet/
RUN chmod +x /root/projet/generer.sh
WORKDIR /root/projet
