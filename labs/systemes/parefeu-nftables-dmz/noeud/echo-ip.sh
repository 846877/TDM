#!/bin/sh
# Réponse HTTP minimale donnant l'adresse IP du client (variable fournie par socat).
printf 'HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\nclient=%s\n' "$SOCAT_PEERADDR"
