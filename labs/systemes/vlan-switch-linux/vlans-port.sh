#!/bin/sh
# Résumé des VLAN d'un port du switch : 10PU = VLAN 10 natif (PVID) non étiqueté, 20T = VLAN 20 étiqueté.
# Usage : vlans-port sw-p1
bridge -j vlan show dev "$1" 2>/dev/null | jq -r '
  [ .[0].vlans[]? ] | sort_by(.vlan) | map(
    (.vlan|tostring)
    + (if ((.flags // []) | any(. == "PVID")) then "P" else "" end)
    + (if ((.flags // []) | any(. == "Egress Untagged")) then "U" else "T" end)
  ) | join(" ")'
