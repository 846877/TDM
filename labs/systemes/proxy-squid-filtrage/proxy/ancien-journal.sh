#!/bin/sh
# Génère le journal Squid de la semaine dernière (format natif) : heure durée client code/statut octets
# méthode URL utilisateur hiérarchie/pair type.
t=1760000000
i=0
for u in alice alice bleroy alice cpetit bleroy alice jmartin alice bleroy cpetit alice; do
  for site in actu.example/une actu.example/meteo jeux.example/partie social.example/fil actu.example/sport; do
    i=$((i + 1))
    case $site in
      jeux.*|social.*) code=TCP_DENIED/403; taille=3900 ;;
      *) code=TCP_MISS/200; taille=$((1000 + i * 37)) ;;
    esac
    if [ "$u" = jmartin ] && [ "${site%%/*}" = social.example ]; then code=TCP_MISS/200; fi
    printf '%s.%03d %6d 10.173.0.%d %s %d GET http://%s %s HIER_DIRECT/10.173.1.80 text/html\n' \
      $((t + i * 61)) $((i % 1000)) $((40 + i % 90)) $((20 + i % 7)) "$code" "$taille" "$site" "$u"
  done
done
