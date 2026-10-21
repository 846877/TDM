#!/bin/sh
# Prépare les services du lab (exécuté une fois pendant la construction de l'image).
set -e
U=/lib/systemd/system

# Export comptable : échoue tant que son fichier de configuration manque.
cat > $U/export-compta.service <<'EOF'
[Unit]
Description=Export quotidien vers le logiciel de comptabilité
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/export-compta

[Install]
WantedBy=multi-user.target
EOF
cat > /usr/local/bin/export-compta <<'EOF'
#!/bin/sh
if [ ! -f /srv/compta/export.cfg ]; then
  echo "ERREUR : fichier de configuration /srv/compta/export.cfg introuvable" >&2
  exit 1
fi
echo "Export comptable prêt (configuration : $(cat /srv/compta/export.cfg))"
EOF

# Pilote d'une imprimante retirée : tourne pour rien.
cat > $U/imprimante-ancienne.service <<'EOF'
[Unit]
Description=Pilote de l'ancienne imprimante réseau (matériel retiré en 2024)

[Service]
ExecStart=/bin/sleep infinity

[Install]
WantedBy=multi-user.target
EOF

# Lecteur de badges : perd sa connexion au bout de 90 s et n'est jamais relancé.
cat > $U/badge.service <<'EOF'
[Unit]
Description=Lecteur de badges de l'entrée de l'atelier
After=network.target

[Service]
ExecStart=/usr/local/bin/lecteur-badge

[Install]
WantedBy=multi-user.target
EOF
cat > /usr/local/bin/lecteur-badge <<'EOF'
#!/bin/sh
echo "Lecteur de badges connecté"
sleep 90
echo "ERREUR : perte de connexion avec le lecteur de badges" >&2
exit 1
EOF

# Sondes de température : un message de priorité « err » (préfixe <3>) au démarrage.
cat > $U/capteur.service <<'EOF'
[Unit]
Description=Relevé des sondes de température de l'atelier

[Service]
ExecStart=/usr/local/bin/capteur

[Install]
WantedBy=multi-user.target
EOF
cat > /usr/local/bin/capteur <<'EOF'
#!/bin/sh
echo "<3>Sonde 3 hors service : aucune mesure reçue"
while true; do
  echo "<6>Sondes 1, 2 et 4 : température normale"
  sleep 30
done
EOF

# Script de nettoyage à planifier.
cat > /usr/local/bin/nettoyage-tmp <<'EOF'
#!/bin/sh
# Supprime les fichiers temporaires de plus de 7 jours.
find /srv/tmp -type f -mtime +7 -print -delete
EOF

chmod 755 /usr/local/bin/export-compta /usr/local/bin/lecteur-badge /usr/local/bin/capteur /usr/local/bin/nettoyage-tmp
systemctl enable export-compta.service imprimante-ancienne.service badge.service capteur.service
systemctl disable nginx.service
# Pas d'IPv6 dans certains environnements Docker : nginx n'écoute qu'en IPv4.
sed -i '/listen \[::\]/d' /etc/nginx/sites-available/default
mkdir -p /srv/compta /srv/tmp /srv/planning
echo "<h1>Planning des ateliers</h1>" > /srv/planning/index.html
useradd -r -s /usr/sbin/nologin -d /srv/planning planning
touch -d '2026-01-10' /srv/tmp/vieux-1.tmp /srv/tmp/vieux-2.tmp
touch /srv/tmp/recent.tmp
