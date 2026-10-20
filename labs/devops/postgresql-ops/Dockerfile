# Serveur PostgreSQL 16 avec une base d'exemple (ventes) et des données à importer.
FROM postgres:16.4-alpine
# Mot de passe du superutilisateur du lab (environnement d'entraînement uniquement).
ENV POSTGRES_PASSWORD=postgres-lab \
    PGUSER=postgres
COPY initdb/ /docker-entrypoint-initdb.d/
COPY donnees/ /root/donnees/
COPY outils/ /root/outils/
RUN chmod +x /root/outils/*.sh && mkdir -p /root/sauvegardes
WORKDIR /root
