#!/bin/sh
# Contrôleur de domaine DURAND.LAN, provisionné au premier démarrage... avec quelques erreurs
# d'administration (les pannes du lab).
P='Durand@dmin2024'
premier=0
if [ ! -f /var/lib/samba/private/sam.ldb ]; then
  premier=1
  rm -f /etc/samba/smb.conf
  samba-tool domain provision --realm=DURAND.LAN --domain=DURAND --server-role=dc \
    --dns-backend=SAMBA_INTERNAL --use-rfc2307 --host-ip=10.62.0.10 --adminpass="$P" \
    --option="dns forwarder = 127.0.0.11" > /var/log/provision.log 2>&1
  samba-tool domain passwordsettings set --max-pwd-age=0 >/dev/null 2>&1
  for ou in "OU=Durand" "OU=Utilisateurs,OU=Durand" "OU=Groupes,OU=Durand" "OU=Ordinateurs,OU=Durand" "OU=Serveurs,OU=Durand"; do
    samba-tool ou create "$ou" >/dev/null 2>&1
  done
  U="OU=Utilisateurs,OU=Durand"
  samba-tool user create mdupont 'Compta!2024pass' --given-name=Marie --surname=Dupont --userou="$U" >/dev/null 2>&1
  samba-tool user create jmartin 'RhDurand!2024' --given-name=Julien --surname=Martin --userou="$U" >/dev/null 2>&1
  samba-tool user create tbernard 'Technicien!2024' --given-name=Thomas --surname=Bernard --userou="$U" >/dev/null 2>&1
  for g in GG_Compta GG_RH GG_Informatique; do
    samba-tool group add $g --groupou="OU=Groupes,OU=Durand" >/dev/null 2>&1
  done
  samba-tool group addmembers GG_Compta mdupont >/dev/null 2>&1
  samba-tool group addmembers GG_RH jmartin >/dev/null 2>&1
  # PANNE : tbernard a été mis dans GG_RH au lieu de GG_Informatique.
  samba-tool group addmembers GG_RH tbernard >/dev/null 2>&1
  # PANNE : compte de mdupont désactivé (« départ » confondu avec une homonyme).
  samba-tool user disable mdupont >/dev/null 2>&1
  # PANNE : compte de jmartin expiré (date de fin de CDD saisie par erreur).
  samba-tool user setexpiry jmartin --days=0 >/dev/null 2>&1
fi
cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
samba
(
  for i in $(seq 1 60); do
    samba-tool dns query 127.0.0.1 durand.lan @ SOA -U "administrator%$P" >/dev/null 2>&1 && break
    sleep 2
  done
  if [ $premier = 1 ]; then
    # PANNE : enregistrement de srv-fichiers resté sur l'adresse de l'ancien serveur.
    samba-tool dns add 127.0.0.1 durand.lan srv-fichiers A 10.62.0.200 -U "administrator%$P"
    samba-tool dns add 127.0.0.1 durand.lan poste01 A 10.62.0.30 -U "administrator%$P"
    # Ajouté en dernier : les membres attendent cet enregistrement pour se joindre au domaine.
    samba-tool dns add 127.0.0.1 durand.lan admin A 10.62.0.5 -U "administrator%$P"
  fi
  touch /run/lab-pret
) >/dev/null 2>&1 &
