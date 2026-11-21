#!/bin/sh
# Script de maintenance à déposer et lancer sur srv-web.
echo "maintenance effectuee sur $(hostname) le $(date +%F)" > "$HOME/maj-ok"
echo "OK"
