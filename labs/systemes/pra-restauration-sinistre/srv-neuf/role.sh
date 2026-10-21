#!/bin/sh
# Kit PRA : clé SSH du compte « sauvegarde » du NAS, déposée par le NAS dans le volume partagé.
mkdir -p /root/kit-pra
i=0
while [ ! -s /kit-pra-partage/cle-sauvegarde ] && [ $i -lt 60 ]; do sleep 1; i=$((i+1)); done
if [ ! -e /root/kit-pra/cle-sauvegarde ]; then
  cp /kit-pra-partage/cle-sauvegarde /root/kit-pra/cle-sauvegarde
  chmod 600 /root/kit-pra/cle-sauvegarde
  cat > /root/kit-pra/LISEZMOI.txt <<'EOF'
KIT DE REPRISE D'ACTIVITÉ - srv-web (boutique en ligne)

Sauvegardes : NAS 10.177.0.30, compte « sauvegarde », dossier /srv/sauvegardes/srv-web/<date>/
Clé SSH du compte : /root/kit-pra/cle-sauvegarde  (ssh -i /root/kit-pra/cle-sauvegarde sauvegarde@10.177.0.30)

Contenu de chaque sauvegarde :
  SHA256SUMS   empreintes de contrôle (sha256sum -c SHA256SUMS)
  etc.tar.gz   /etc/passwd, /etc/group, /etc/shadow, configuration nginx (site « boutique »)
  www.tar.gz   /var/www/boutique (propriétaire : compte « web », UID 1500)
  cron.tar.gz  crontabs des utilisateurs (/var/spool/cron/crontabs)
  bdd.sql.gz   base MariaDB « boutique » (mariadb-dump --databases)
  droits.sql   compte MariaDB de l'application et ses droits

Comptes de srv-web : web (UID/GID 1500, propriétaire du site), deploy (UID/GID 1501, déploiements).
Site : http://boutique.durand.lan/ (nginx). La boutique lit la base « boutique » avec le compte MariaDB « boutique ».
EOF
fi
