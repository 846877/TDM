FROM prom/prometheus:v2.53.2 AS prometheus
FROM prom/alertmanager:v0.27.0 AS alertmanager

FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl jq nano vim less procps ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=prometheus /bin/prometheus /bin/promtool /usr/local/bin/
COPY --from=alertmanager /bin/amtool /usr/local/bin/
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY demarrer-prometheus /usr/local/bin/demarrer-prometheus
RUN chmod 755 /usr/local/bin/demarrer-prometheus && mkdir -p /etc/prometheus/rules /prometheus
WORKDIR /etc/prometheus
CMD ["sh", "-c", "/usr/local/bin/demarrer-prometheus; exec sleep infinity"]
