#!/bin/sh
# Démarre (une seule fois) le bureau XFCE via TigerVNC puis le pont noVNC sur le port 6080.
# Sans mot de passe : le lab est isolé et le port n'est exposé que sur 127.0.0.1 de ta machine.
set -e
export USER=root HOME=/root

# Déjà en route ? On ne relance rien.
if pgrep -f "websockify" >/dev/null 2>&1; then
  echo "Bureau déjà démarré (noVNC sur 6080)."
  exit 0
fi

# Serveur X + VNC sur l'affichage :1 (port 5901), sans authentification.
vncserver -kill :1 >/dev/null 2>&1 || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true
vncserver :1 -geometry 1440x900 -depth 24 -localhost no -SecurityTypes None >/tmp/vnc.log 2>&1

# Pont noVNC : http://<hôte>:6080/vnc.html  ->  VNC local :5901
websockify -D --web=/usr/share/novnc 6080 localhost:5901 >/tmp/novnc.log 2>&1

echo "Bureau Kali prêt : noVNC sur le port 6080."
