#!/bin/sh
# Sur srv-bdd, une attaque par force brute génère des messages d'authentification toutes les 15 s
# (ils n'arrivent au serveur central qu'une fois rsyslog configuré et démarré).
if [ "$ROLE" = bdd ]; then
  (
    while true; do
      logger -p auth.warning -t sshd "Failed password for invalid user oracle from 203.0.113.45 port 51122 ssh2" 2>/dev/null
      logger -p daemon.info -t postgres "checkpoint complete" 2>/dev/null
      sleep 15
    done
  ) >/dev/null 2>&1 &
fi
