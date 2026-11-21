#!/bin/sh
/usr/local/bin/nommer-interfaces.sh
# Journal système : keepalived y écrit (/var/log/syslog).
rsyslogd 2>/dev/null
if [ "$ROLE" = web ]; then
  mkdir -p /www
  echo "<h1>Application metier</h1>" > /www/index.html
  busybox httpd -p 80 -h /www
fi
