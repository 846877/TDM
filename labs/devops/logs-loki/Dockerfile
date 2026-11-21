# Poste Ubuntu avec Loki, logcli et Grafana Alloy (binaires officiels publiés par Grafana).
FROM ubuntu:24.04
ARG TARGETARCH=amd64
ARG LOKI_VERSION=3.5.7
ARG ALLOY_VERSION=1.11.3
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl unzip jq nano vim less procps \
    && rm -rf /var/lib/apt/lists/*
RUN set -e; cd /tmp; \
    for p in loki logcli; do \
      curl -fsSLo "$p.zip" "https://github.com/grafana/loki/releases/download/v${LOKI_VERSION}/${p}-linux-${TARGETARCH}.zip"; \
      unzip -q "$p.zip"; mv "${p}-linux-${TARGETARCH}" "/usr/local/bin/$p"; \
    done; \
    curl -fsSLo alloy.zip "https://github.com/grafana/alloy/releases/download/v${ALLOY_VERSION}/alloy-linux-${TARGETARCH}.zip"; \
    unzip -q alloy.zip; mv "alloy-linux-${TARGETARCH}" /usr/local/bin/alloy; \
    chmod +x /usr/local/bin/loki /usr/local/bin/logcli /usr/local/bin/alloy; rm -f /tmp/*.zip
COPY fichiers/loki.yaml /etc/loki/loki.yaml
COPY fichiers/generer-logs.sh /opt/boutique/generer-logs.sh
RUN chmod +x /opt/boutique/generer-logs.sh \
    && mkdir -p /var/lib/loki /var/lib/alloy /etc/alloy /root/requetes /root/export
WORKDIR /root
