# Un « switch » Linux et ses postes : chaque poste est un espace de noms réseau (ip netns) relié au
# switch par un câble virtuel (paire veth). Le conteneur doit être privilégié.
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       iproute2 iputils-ping tcpdump nftables jq procps vim-tiny nano less bash-completion \
    && rm -rf /var/lib/apt/lists/*
COPY cablage.sh /usr/local/sbin/cablage.sh
COPY vlans-port.sh /usr/local/bin/vlans-port
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/sbin/cablage.sh /usr/local/bin/vlans-port /usr/local/bin/entrypoint.sh
WORKDIR /root
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
