#!/bin/sh
# Rôle de chaque machine. Au PREMIER démarrage, des pannes sont injectées (fichiers de configuration
# erronés, réglages faux). Aux démarrages suivants, on réapplique simplement les fichiers de configuration.
/usr/local/bin/nommer-interfaces.sh
premier=0
[ -f /etc/lab-initialise ] || premier=1
touch /etc/lab-initialise

case "$ROLE" in
  routeur)
    if [ $premier = 1 ]; then
      echo "net.ipv4.ip_forward = 0" > /etc/sysctl.d/99-routeur.conf
      cat > /etc/nftables.conf <<'EOF'
#!/usr/sbin/nft -f
flush ruleset

table inet filtre {
  chain forward {
    type filter hook forward priority 0; policy drop;
    ct state established,related accept
    ip daddr 10.20.0.53 udp dport 53 drop comment "test JPL 12/03 - a retirer"
    iifname "lan" oifname "serveurs" accept
    iifname "lan" oifname "wan" accept
  }
}

table ip nat {
  chain postrouting {
    type nat hook postrouting priority 100; policy accept;
    oifname "wan0" masquerade
  }
}
EOF
    fi
    sysctl -q -p /etc/sysctl.d/99-routeur.conf
    nft -f /etc/nftables.conf
    ;;
  poste)
    if [ $premier = 1 ]; then
      printf 'search durand.lan\nnameserver 10.20.0.35\n' > /etc/resolv.conf
      printf '# ajout temporaire pendant la migration (JPL)\n10.20.0.99\tintranet.durand.lan intranet\n' >> /etc/hosts
      ip route replace default via 192.168.20.253
    fi
    ;;
  web)
    if [ $premier = 1 ]; then
      mkdir -p /var/www/intranet
      echo "<h1>Intranet Ateliers Durand</h1>" > /var/www/intranet/index.html
      chmod 600 /var/www/intranet/index.html
      cat > /etc/nginx/sites-available/intranet <<'EOF'
server {
    listen 127.0.0.1:80 default_server;
    server_name intranet.durand.lan;
    root /var/www/intranet;
    index index.html;
}
EOF
      ln -sf /etc/nginx/sites-available/intranet /etc/nginx/sites-enabled/intranet
    fi
    nginx
    ;;
  dns)
    if [ $premier = 1 ]; then
      mkdir -p /etc/dnsmasq.d
      printf 'conf-dir=/etc/dnsmasq.d/,*.conf\nuser=root\n' > /etc/dnsmasq.conf
      cat > /etc/dnsmasq.d/durand.conf <<'EOF'
# Zone locale durand.lan
no-resolv
no-hosts
domain=durand.lan
local=/durand.lan/
host-record=srv-web.durand.lan,10.20.0.10
host-record=srv-dns.durand.lan,10.20.0.53
host-record=routeur.durand.lan,10.20.0.254
# intranet : ancien serveur (avant migration)
address=/intranet.durand.lan/10.20.0.100
EOF
    fi
    dnsmasq
    ;;
  internet)
    # Serveur « Internet » qui renvoie l'adresse source vue de l'extérieur.
    socat TCP-LISTEN:80,fork,reuseaddr EXEC:/usr/local/bin/echo-ip.sh >/dev/null 2>&1 &
    ;;
esac
