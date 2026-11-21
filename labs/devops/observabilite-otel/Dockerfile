# Poste Ubuntu avec le collecteur OpenTelemetry (distribution contrib), Jaeger v2 et le SDK Python
# OpenTelemetry (binaires et paquets officiels, versions épinglées).
FROM ubuntu:24.04
ARG TARGETARCH=amd64
ARG OTELCOL_VERSION=0.120.0
ARG JAEGER_TAG=v1.66.0
ARG JAEGER_VERSION=2.3.0
ARG OTEL_PY_VERSION=1.30.0
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl jq python3 python3-venv nano vim less procps iproute2 \
    && rm -rf /var/lib/apt/lists/*
RUN set -e; cd /tmp; \
    curl -fsSL "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${OTELCOL_VERSION}/otelcol-contrib_${OTELCOL_VERSION}_linux_${TARGETARCH}.tar.gz" \
      | tar -xz -C /usr/local/bin otelcol-contrib; \
    curl -fsSL "https://github.com/jaegertracing/jaeger/releases/download/${JAEGER_TAG}/jaeger-${JAEGER_VERSION}-linux-${TARGETARCH}.tar.gz" \
      | tar -xz; \
    mv "jaeger-${JAEGER_VERSION}-linux-${TARGETARCH}/jaeger" /usr/local/bin/jaeger; \
    rm -rf /tmp/jaeger-*; chmod +x /usr/local/bin/otelcol-contrib /usr/local/bin/jaeger
RUN python3 -m venv /opt/otel \
    && /opt/otel/bin/pip install --no-cache-dir -q \
       "opentelemetry-sdk==${OTEL_PY_VERSION}" "opentelemetry-exporter-otlp-proto-http==${OTEL_PY_VERSION}"
# « python » désigne le Python du venv, qui contient le SDK OpenTelemetry.
ENV PATH=/opt/otel/bin:$PATH
COPY fichiers/jaeger.yaml /etc/jaeger/jaeger.yaml
COPY fichiers/appli/ /opt/appli/
COPY fichiers/tdm-trace fichiers/tdm-envoyer-span /usr/local/bin/
RUN chmod +x /usr/local/bin/tdm-trace /usr/local/bin/tdm-envoyer-span && mkdir -p /etc/otelcol
WORKDIR /opt/appli
