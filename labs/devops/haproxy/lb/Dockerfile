FROM haproxy:2.9
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /run/haproxy && printf 'global\n    log stdout format raw local0\n\ndefaults\n    mode http\n    timeout connect 5s\n    timeout client 30s\n    timeout server 30s\n\n# À toi de jouer : ajoute tes frontend et backend ici.\n' > /usr/local/etc/haproxy/haproxy.cfg
CMD ["sleep", "infinity"]
