#!/bin/sh
# Membres du domaine : jonction automatique au premier démarrage, puis injection des pannes.
P='Durand@dmin2024'
if [ -f /etc/lab-initialise ]; then
  # Démarrages suivants : on relance simplement les services.
  case "$ROLE" in
    fichiers) winbindd; smbd ;;
    poste) sssd -D ;;
  esac
  exit 0
fi

printf '[libdefaults]\n    default_realm = DURAND.LAN\n    dns_lookup_kdc = true\n    dns_lookup_realm = false\n    rdns = false\n' > /etc/krb5.conf
# Attente du contrôleur de domaine (enregistrement « admin » créé en dernier).
for i in $(seq 1 120); do
  dig +short @10.62.0.10 admin.durand.lan 2>/dev/null | grep -q '10.62.0.5' && break
  sleep 3
done
sleep 5

case "$ROLE" in
  fichiers)
    cat > /etc/samba/smb.conf <<'EOF'
[global]
   workgroup = DURAND
   realm = DURAND.LAN
   security = ADS
   idmap config * : backend = tdb
   idmap config * : range = 3000-7999
   idmap config DURAND : backend = rid
   idmap config DURAND : range = 10000-999999
   winbind use default domain = yes
   template shell = /bin/bash
   template homedir = /home/%U

[compta]
   path = /srv/partages/compta
   read only = no
   valid users = @gg_comptes
   create mask = 0660
   directory mask = 2770

[rh]
   path = /srv/partages/rh
   read only = no
   valid users = @gg_rh
   create mask = 0660
   directory mask = 2770
EOF
    net ads join -U "administrator%$P" createcomputer=Durand/Serveurs --no-dns-updates > /var/log/jonction.log 2>&1
    # Droits des dossiers : nécessite winbind le temps de la préparation.
    sed -i -E 's/^(passwd|group):(.*)$/\1:\2 winbind/' /etc/nsswitch.conf
    winbindd
    for i in $(seq 1 30); do wbinfo -p >/dev/null 2>&1 && getent group gg_compta >/dev/null && break; sleep 2; done
    mkdir -p /srv/partages/compta /srv/partages/rh
    chgrp gg_compta /srv/partages/compta; chgrp gg_rh /srv/partages/rh
    chmod 2770 /srv/partages/compta /srv/partages/rh
    echo "Bilan 2024 (confidentiel)" > /srv/partages/compta/bilan-2024.txt
    chgrp gg_compta /srv/partages/compta/bilan-2024.txt; chmod 660 /srv/partages/compta/bilan-2024.txt
    # PANNE : « nettoyage » de nsswitch.conf et winbind arrêté.
    pkill winbindd
    sed -i -E 's/ winbind//g' /etc/nsswitch.conf
    # PANNE : relation d'approbation rompue (mot de passe du compte ordinateur désynchronisé,
    # comme après la restauration d'un vieil instantané de la VM).
    echo 'Instantane-2023-perime' | net changesecretpw -f -i >/dev/null 2>&1
    smbd
    ;;
  poste)
    echo "$P" | adcli join --domain=durand.lan --host-fqdn=poste01.durand.lan \
      --domain-ou='OU=Ordinateurs,OU=Durand,DC=durand,DC=lan' -U administrator --stdin-password > /var/log/jonction.log 2>&1
    mkdir -p /etc/sssd
    cat > /etc/sssd/sssd.conf <<'EOF'
[sssd]
services = nss, pam
domains = durand.lan

[domain/durand.lan]
id_provider = ad
ad_domain = durand.lan
krb5_realm = DURAND.LAN
use_fully_qualified_names = False
fallback_homedir = /home/%u
default_shell = /bin/bash
access_provider = simple
simple_allow_groups = gg_informatque
EOF
    # PANNE : droits trop ouverts (sssd refuse alors de démarrer) et nom de groupe mal orthographié.
    chmod 644 /etc/sssd/sssd.conf
    pam-auth-update --enable mkhomedir >/dev/null 2>&1
    sssd -D 2>/dev/null
    ;;
esac
touch /etc/lab-initialise
