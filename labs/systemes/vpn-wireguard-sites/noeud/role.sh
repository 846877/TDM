#!/bin/sh
/usr/local/bin/nommer-interfaces.sh
if [ "$ROLE" = intranet ]; then
  mkdir -p /www
  echo "<h1>Intranet du siege</h1>" > /www/index.html
  busybox httpd -p 80 -h /www
fi
