#!/bin/sh
# Fabrique les sauvegardes de l'ancien srv-web (exécuté dans une étape de construction séparée).
set -e
OUT=/out/srv-web
mkdir -p $OUT /tmp/web

# Comptes de srv-web.
groupadd -g 1500 web && useradd -u 1500 -g 1500 -m -s /bin/bash -c "Site boutique" web
groupadd -g 1501 deploy && useradd -u 1501 -g 1501 -G web -m -s /bin/bash -c "Déploiements" deploy
echo 'web:Web-Boutique-2026' | chpasswd
echo 'deploy:Deploy-2026!' | chpasswd

# Site et configuration nginx.
mkdir -p /var/www/boutique/bin /var/www/boutique/images /etc/nginx/sites-available
cat > /var/www/boutique/index.html <<'EOF'
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Boutique</title></head>
<body><h1>Boutique Ateliers Durand</h1><p>Mobilier d'atelier sur mesure.</p></body></html>
EOF
printf '#!/bin/sh\ndate > /var/www/boutique/stock.txt\n' > /var/www/boutique/bin/maj-stock.sh
chmod 750 /var/www/boutique/bin/maj-stock.sh
for i in 1 2 3; do head -c 2K /dev/urandom > /var/www/boutique/images/produit-$i.jpg; done
chown -R web:web /var/www/boutique
cat > /etc/nginx/sites-available/boutique <<'EOF'
server {
    listen 80;
    server_name boutique.durand.lan;
    root /var/www/boutique;
    index index.html;
    access_log /var/log/nginx/boutique.access.log;
    location /bin/ { deny all; }
}
EOF

# Crontab de web.
mkdir -p /var/spool/cron/crontabs
printf '# Mise à jour du stock affiché\n*/15 * * * * /var/www/boutique/bin/maj-stock.sh\n' > /var/spool/cron/crontabs/web
chown 1500:crontab /var/spool/cron/crontabs/web 2>/dev/null || chown 1500 /var/spool/cron/crontabs/web
chmod 600 /var/spool/cron/crontabs/web

# Base de données.
mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld
mariadbd --user=mysql --skip-networking >/tmp/m.log 2>&1 &
i=0; until mariadb -e 'SELECT 1' >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 60 ] && exit 1; sleep 1; done
mariadb -e "CREATE DATABASE boutique CHARACTER SET utf8mb4; CREATE TABLE boutique.produits (id INT PRIMARY KEY AUTO_INCREMENT, nom VARCHAR(80), prix DECIMAL(8,2), stock INT)"
n=1; while [ $n -le 40 ]; do mariadb -e "INSERT INTO boutique.produits (nom, prix, stock) VALUES ('Établi modèle $n', $((150 + n * 10)).00, $((n % 9)))"; n=$((n+1)); done
cat > /tmp/droits.sql <<'EOF'
CREATE USER IF NOT EXISTS 'boutique'@'localhost' IDENTIFIED BY 'Boutique-Bdd-2026';
GRANT SELECT, INSERT, UPDATE, DELETE ON boutique.* TO 'boutique'@'localhost';
EOF

jour() { # jour <date> <nombre de produits à retirer pour simuler l'évolution>
  d=$OUT/$1; mkdir -p $d
  tar -czf $d/etc.tar.gz -C / etc/passwd etc/group etc/shadow etc/nginx/sites-available/boutique
  tar -czf $d/www.tar.gz --numeric-owner -C / var/www/boutique
  tar -czf $d/cron.tar.gz --numeric-owner -C / var/spool/cron/crontabs
  mariadb-dump --single-transaction --databases boutique | gzip > $d/bdd.sql.gz
  cp /tmp/droits.sql $d/droits.sql
  (cd $d && sha256sum etc.tar.gz www.tar.gz cron.tar.gz bdd.sql.gz droits.sql > SHA256SUMS)
}
jour 2026-10-17
mariadb -e "UPDATE boutique.produits SET stock = stock + 1 WHERE id <= 10"
jour 2026-10-18
mariadb -e "UPDATE boutique.produits SET stock = stock + 1 WHERE id <= 20"
jour 2026-10-19
# La sauvegarde du 19 a été écrite sur un disque défaillant : l'archive du site est abîmée.
printf 'XXXXXXXX' | dd of=$OUT/2026-10-19/www.tar.gz bs=1 seek=200 conv=notrunc 2>/dev/null
mariadb-admin shutdown
