#!/bin/sh
# Démarrage du serveur. Au PREMIER démarrage, les pannes du lab sont injectées ; ensuite on démarre
# simplement les services (une configuration corrigée reste corrigée après un redémarrage).
if [ ! -f /etc/lab-initialise ]; then
  touch /etc/lab-initialise

  # --- Application web : erreur de syntaxe nginx et ancien portail qui occupe le port 80 ---
  mkdir -p /var/www/appli /srv/ancien-portail
  echo "<h1>Application Durand</h1>" > /var/www/appli/index.html
  echo "<h1>Ancien portail (obsolète)</h1>" > /srv/ancien-portail/index.html
  cat > /etc/nginx/conf.d/appli.conf <<'EOF'
server {
    listen 80 default_server;
    server_name appli.durand.lan;
    root /var/www/appli
    index index.html;
}
EOF
  busybox httpd -p 80 -h /srv/ancien-portail

  # --- Journal de débogage énorme, supprimé mais toujours ouvert ---
  mkdir -p /var/log/appli
  chown root:appli /var/log/appli
  chmod 775 /var/log/appli
  nohup /usr/local/bin/journal-appli >/dev/null 2>&1 &
  sleep 3
  rm -f /var/log/appli/debug.log

  # --- Rapport planifié : fichier cron.d invalide, script au format Windows et non exécutable ---
  printf '#!/bin/sh\r\n# Rapport d activite (copie depuis le poste de JPL)\r\necho "$(date +%%F_%%T) rapport OK $(uptime)" >> /var/log/rapport.log\r\n' > /usr/local/bin/rapport.sh
  chmod 644 /usr/local/bin/rapport.sh
  printf '# Rapport toutes les minutes\n* * * * * /usr/local/bin/rapport.sh\n' > /etc/cron.d/rapport
  chmod 664 /etc/cron.d/rapport

  # --- Compte comptable inutilisable ---
  usermod -s /usr/sbin/nologin comptable
  chage -E 2023-12-31 comptable
  chown root:root /home/comptable
  chmod 700 /home/comptable

  # --- Service applicatif : droits trop stricts ---
  mkdir -p /etc/appli /srv/appli/data
  printf 'base=bdd.durand.lan:5432\nutilisateur=appli\nmot_de_passe=S3cret-Appli\n' > /etc/appli/appli.conf
  chown root:root /etc/appli/appli.conf /srv/appli/data
  chmod 600 /etc/appli/appli.conf
  chmod 755 /srv/appli/data

  # --- Résolution de noms : nsswitch sans « files », /etc/hosts erroné ---
  sed -i 's/^hosts:.*/hosts:          dns/' /etc/nsswitch.conf
  printf '# base de donnees (ancien serveur)\n10.0.0.99\tbdd.durand.lan bdd\n' >> /etc/hosts

  # --- Rotation des journaux : fichier logrotate invalide ---
  touch /var/log/appli/app.log
  chown appli:appli /var/log/appli/app.log
  printf '/var/log/appli/app.log {\n    weekly\n    rotate sept\n    compress\n    missingok\n    notifempty\n    create 0640 appli appli\n}\n' > /etc/logrotate.d/appli
  chmod 666 /etc/logrotate.d/appli

  # --- SSH : clés d'hôte supprimées et options invalides ---
  rm -f /etc/ssh/ssh_host_*
  printf '# Durcissement (JPL)\nPermitRootLogin noo\nMaxAuthTries trois\nPasswordAuthentication no\n' > /etc/ssh/sshd_config.d/durcissement.conf
fi

# Données de l'application dans le journal (pour la rotation).
echo "$(date '+%F %T') INFO démarrage de l'application" >> /var/log/appli/app.log

# Services (certains refusent de démarrer tant que leur panne n'est pas corrigée).
mkdir -p /run/sshd
cron
nginx 2>/dev/null
/usr/sbin/sshd 2>/dev/null
# « Base de données » locale sur 127.0.0.2:5432.
socat TCP-LISTEN:5432,bind=127.0.0.2,fork,reuseaddr SYSTEM:'echo PGSQL-DURAND' >/dev/null 2>&1 &
runuser -u appli -- /usr/local/bin/appli-service >/dev/null 2>&1 &
exec "$@"
