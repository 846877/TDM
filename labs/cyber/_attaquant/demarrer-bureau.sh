#!/bin/sh
# Démarre (une seule fois) le bureau léger (Fluxbox) via TigerVNC puis le pont noVNC sur le port 6080.
# Sans mot de passe : le lab est isolé et le port n'est exposé que sur 127.0.0.1 de ta machine.
#
# On lance le serveur X directement avec Xtigervnc (et PAS le script `vncserver`) : sur Kali, `vncserver`
# échoue sur sa migration de config (« Could not migrate /root/.vnc … ») et renvoie un code non nul, ce
# qui empêchait le démarrage du pont noVNC. En appelant Xtigervnc directement on évite tout ça.
export USER=root HOME=/root DISPLAY=:1

# Déjà en route ? On ne relance rien.
if pgrep -f websockify >/dev/null 2>&1; then
  echo "Bureau déjà démarré (noVNC sur 6080)."
  exit 0
fi

# Nettoyage d'un éventuel affichage précédent.
pkill -f "Xtigervnc :1" 2>/dev/null || true
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true

# Serveur X + VNC sur l'affichage :1 (port 5901, accès local), sans authentification (lab isolé).
Xtigervnc :1 -geometry 1440x900 -depth 24 -rfbport 5901 -SecurityTypes None -desktop Kali \
  >/tmp/vnc.log 2>&1 &

# On attend que le serveur X réponde avant de lancer les applis (le socket X apparaît une fois prêt).
i=0
while [ ! -S /tmp/.X11-unix/X1 ] && [ "$i" -lt 15 ]; do
  i=$((i + 1))
  sleep 1
done

# Gestionnaire de fenêtres + terminal + navigateur, dans l'affichage VNC.
fluxbox >/tmp/fluxbox.log 2>&1 &
xterm -geometry 100x28+20+20 >/dev/null 2>&1 &
firefox-esr http://cible/ >/dev/null 2>&1 &

# Pont noVNC : http://<hôte>:6080/vnc.html -> VNC local :5901. On écoute sur 0.0.0.0 pour que le port
# publié par Docker, redirigé par la VM jusqu'à 127.0.0.1 de l'hôte, atteigne bien le pont.
websockify -D --web=/usr/share/novnc 0.0.0.0:6080 localhost:5901 >/tmp/novnc.log 2>&1

echo "Bureau Kali prêt : noVNC sur le port 6080."
