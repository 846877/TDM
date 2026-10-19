#!/bin/sh
mkdir -p /www
case "$ROLE" in
  bastion)
    echo 'tech ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/tech && chmod 440 /etc/sudoers.d/tech
    ;;
  interne)
    echo "<h1>Intranet interne</h1><p>Accessible uniquement depuis le reseau interne.</p>" > /www/index.html
    busybox httpd -p 80 -h /www
    ;;
  bdd)
    # Console d'administration de la base : n'écoute que sur la boucle locale.
    echo "<h1>Console BDD</h1><p>Administration PostgreSQL - acces local uniquement.</p>" > /www/index.html
    busybox httpd -p 127.0.0.1:8080 -h /www
    ;;
esac
# sshd tourne en arrière-plan : une configuration invalide l'arrêterait, teste-la avec sshd -t.
/usr/sbin/sshd
exec sleep infinity
