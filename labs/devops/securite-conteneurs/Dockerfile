# Hôte Docker (Docker dans Docker) outillé pour la sécurité : trivy (scan, SBOM), hadolint (lint), jq.
FROM aquasec/trivy:0.56.2 AS trivy
FROM hadolint/hadolint:v2.12.0 AS hadolint
FROM docker:28-dind
COPY --from=trivy /usr/local/bin/trivy /usr/local/bin/trivy
COPY --from=hadolint /bin/hadolint /usr/local/bin/hadolint
ADD --chmod=755 https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64 /usr/local/bin/jq
COPY app/ /root/app/
# Le fichier .env (secret de démonstration) est créé ici car les .env sont ignorés par git.
RUN mkdir -p /root/rapports /root/secrets \
    && printf 'DB_PASSWORD=tdm-mot-de-passe-de-prod\n' > /root/app/.env
WORKDIR /root/app
