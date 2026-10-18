# Image de la plateforme TDM. Elle pilote le Docker de la machine hôte (socket monté)
# pour le bac à sable Python et les labs DevOps.
FROM docker:28-cli AS docker-cli

FROM python:3.12-slim
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY . .
ENV TDM_SANDBOX=docker \
    PYTHONUNBUFFERED=1
EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
