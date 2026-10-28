# Poste Ubuntu avec SOPS et age (binaires officiels) et un dépôt Git d'infrastructure.
FROM ubuntu:24.04
ARG TARGETARCH=amd64
ARG SOPS_VERSION=3.10.2
ARG AGE_VERSION=1.2.1
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       sudo nano vim less git jq curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash eleve \
    && echo "eleve ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/eleve
RUN set -e; \
    curl -fsSLo /usr/local/bin/sops "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${TARGETARCH}"; \
    chmod +x /usr/local/bin/sops; \
    curl -fsSL "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-${TARGETARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin --strip-components=1 age/age age/age-keygen
COPY infra/ /home/eleve/infra/
COPY preparer.sh /tmp/preparer.sh
RUN mkdir -p /home/eleve/infra/cles && chmod +x /home/eleve/infra/outils/*.sh && sh /tmp/preparer.sh && rm /tmp/preparer.sh
USER eleve
WORKDIR /home/eleve/infra
