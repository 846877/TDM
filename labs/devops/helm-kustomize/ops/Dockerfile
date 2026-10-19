FROM ubuntu:24.04
ARG KUBECTL_VERSION=v1.30.6
ARG HELM_VERSION=v3.16.2
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       ca-certificates curl jq git openssl python3 bash-completion nano vim less \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod 755 /usr/local/bin/kubectl
RUN curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" | tar -xz -C /tmp \
    && mv /tmp/linux-amd64/helm /usr/local/bin/helm && rm -rf /tmp/linux-amd64
COPY demarrage /usr/local/bin/demarrage
COPY kustomize/ /root/kustomize/
RUN chmod 755 /usr/local/bin/demarrage \
    && echo 'source <(kubectl completion bash); source <(helm completion bash); alias k=kubectl; complete -o default -F __start_kubectl k' >> /root/.bashrc
WORKDIR /root
CMD ["/usr/local/bin/demarrage"]
