#!/bin/sh
# Fichiers de session : 40 anciens (plus de 30 jours) et 10 récents, datés au démarrage du lab.
if [ ! -e /srv/cache/sessions/.prepare ]; then
  i=1
  while [ $i -le 40 ]; do f=/srv/cache/sessions/sess-ancien-$i; echo session > $f; touch -d '45 days ago' $f; i=$((i+1)); done
  i=1
  while [ $i -le 10 ]; do f=/srv/cache/sessions/sess-recent-$i; echo session > $f; touch -d '2 days ago' $f; i=$((i+1)); done
  touch /srv/cache/sessions/.prepare
fi
# Une application garde ouvert un gros journal de débogage... qui a été supprimé.
if ! pgrep -x appli-dbg >/dev/null; then
  head -c 60M /dev/zero > /var/log/appli/debug.log
  /usr/local/bin/appli-dbg infinity 3</var/log/appli/debug.log &
  sleep 1
  rm -f /var/log/appli/debug.log
fi
exec "$@"
