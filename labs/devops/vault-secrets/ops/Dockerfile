FROM hashicorp/vault:1.17.6 AS vault
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl jq postgresql-client bash-completion nano vim less \
    && rm -rf /var/lib/apt/lists/*
COPY --from=vault /bin/vault /usr/local/bin/vault
ENV VAULT_ADDR=http://vault:8200
RUN vault -autocomplete-install
WORKDIR /root
CMD ["sleep", "infinity"]
