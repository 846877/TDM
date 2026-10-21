#!/bin/sh
# Prépare l'état initial de MariaDB pendant la construction de l'image, puis arrête le serveur.
set -e
mkdir -p /run/mysqld /srv/sauvegardes
chown mysql:mysql /run/mysqld
mariadbd --user=mysql --skip-networking --socket=/run/mysqld/mysqld.sock >/tmp/mariadbd.log 2>&1 &
i=0
until mariadb -e 'SELECT 1' >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 60 ] && exit 1; sleep 1; done

# Héritage d'une vieille installation : compte anonyme et base de test ouverte à tous.
mariadb <<'EOF'
CREATE USER ''@'localhost';
CREATE USER ''@'srv-bdd';
CREATE DATABASE test;
GRANT ALL ON test.* TO ''@'localhost';
EOF

# Base « stock » sauvegardée avant-hier... puis supprimée par erreur.
mariadb <<'EOF'
CREATE DATABASE stock CHARACTER SET utf8mb4;
CREATE TABLE stock.articles (id INT PRIMARY KEY AUTO_INCREMENT, reference VARCHAR(20), libelle VARCHAR(80), quantite INT);
EOF
n=1
while [ $n -le 25 ]; do
  mariadb -e "INSERT INTO stock.articles (reference, libelle, quantite) VALUES ('ART-$n', 'Article $n', $((n * 7 % 50)))"
  n=$((n + 1))
done
mariadb-dump --single-transaction --databases stock | gzip > /srv/sauvegardes/stock-2026-10-18.sql.gz
mariadb -e 'DROP DATABASE stock'

mariadb-admin shutdown
wait
