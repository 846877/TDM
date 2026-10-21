# Poste « ops » : kubectl, un scénario de départ et des outils de vérification.
FROM ubuntu:24.04
ARG TARGETARCH=amd64
ARG KUBECTL_VERSION=v1.30.6
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl jq openssl bash-completion nano vim less \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl" \
    && chmod 755 /usr/local/bin/kubectl
COPY demarrage tdm-pod-conforme tdm-sonde /usr/local/bin/
COPY scenario/ /opt/scenario/
RUN chmod 755 /usr/local/bin/demarrage /usr/local/bin/tdm-pod-conforme /usr/local/bin/tdm-sonde \
    && mkdir -p /root/securite \
    && echo 'source <(kubectl completion bash); alias k=kubectl; complete -o default -F __start_kubectl k' >> /root/.bashrc
WORKDIR /root/securite
CMD ["/usr/local/bin/demarrage"]
