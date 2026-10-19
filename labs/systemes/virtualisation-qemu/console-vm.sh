#!/bin/sh
# Ouvre la console série d'une VM (socket /srv/vms/<vm>.console). Quitter : Ctrl+C.
# Usage : console-vm vm1
exec socat -,raw,echo=0,escape=0x03 "UNIX-CONNECT:/srv/vms/${1:-vm1}.console"
