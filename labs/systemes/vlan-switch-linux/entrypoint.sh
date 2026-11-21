#!/bin/sh
/usr/local/sbin/cablage.sh || echo "Câblage impossible : le lab doit tourner en conteneur privilégié." >&2
exec "$@"
