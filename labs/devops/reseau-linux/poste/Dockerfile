FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       iproute2 iputils-ping dnsutils curl netcat-openbsd traceroute tcpdump iptables nmap python3 nano vim less procps \
    && rm -rf /var/lib/apt/lists/*
# Un service « inconnu » tourne sur le poste (exercice sur les ports en écoute).
RUN printf '#!/bin/sh\ncd /tmp && python3 -m http.server 4321 >/dev/null 2>&1 &\nexec sleep infinity\n' > /usr/local/bin/demarrage \
    && chmod 755 /usr/local/bin/demarrage
WORKDIR /root
CMD ["/usr/local/bin/demarrage"]
