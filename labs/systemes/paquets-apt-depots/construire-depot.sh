#!/bin/sh
# Construit le dépôt interne d'« Ateliers Durand » (/srv/depot) et le paquet téléchargé à la main.
# Exécuté une fois pendant la construction de l'image.
set -e
TMP=$(mktemp -d)
mkdir -p /srv/depot /root/telechargements

# paquet <nom> <version> <dépendances> <description> <dossier de sortie> ; fichiers déjà placés dans $TMP/<nom>-<version>
paquet() {
  d="$TMP/$1-$2"
  mkdir -p "$d/DEBIAN"
  {
    echo "Package: $1"
    echo "Version: $2"
    echo "Architecture: all"
    echo "Maintainer: Service informatique <informatique@durand.lan>"
    [ -n "$3" ] && echo "Depends: $3"
    echo "Section: misc"
    echo "Priority: optional"
    echo "Description: $4"
    echo " Paquet interne d'Ateliers Durand."
  } > "$d/DEBIAN/control"
  [ -d "$d/etc" ] && find "$d/etc" -type f | sed "s|^$d||" > "$d/DEBIAN/conffiles"
  dpkg-deb --root-owner-group --build "$d" "$5/$1_$2_all.deb" >/dev/null
}

script() { # script <chemin> <texte affiché>
  mkdir -p "$(dirname "$1")"
  printf '#!/bin/sh\necho "%s"\n' "$2" > "$1"
  chmod 755 "$1"
}

for v in 1.0 1.1; do
  mkdir -p "$TMP/durand-commun-$v/usr/share/durand"
  echo "Bibliothèque commune Durand $v" > "$TMP/durand-commun-$v/usr/share/durand/commun.txt"
  paquet durand-commun $v "" "fichiers communs des outils Durand" /srv/depot
done

script "$TMP/durand-outils-1.0/usr/bin/durand-info" "durand-info 1.0 - code=OUT-7731"
script "$TMP/durand-outils-1.1/usr/bin/durand-info" "durand-info 1.1 - ERREUR : version défectueuse"
for v in 1.0 1.1; do
  mkdir -p "$TMP/durand-outils-$v/etc/durand"
  printf '# Configuration des outils Durand\nserveur=srv-fichiers.durand.lan\n' > "$TMP/durand-outils-$v/etc/durand/outils.conf"
  paquet durand-outils $v "durand-commun (>= 1.0)" "outils d'administration du parc Durand" /srv/depot
done

script "$TMP/durand-inventaire-2.3/usr/bin/durand-inventaire" "Inventaire du parc : 42 postes, 6 serveurs"
paquet durand-inventaire 2.3 "" "outil d'inventaire du parc informatique" /srv/depot

script "$TMP/durand-pdf-1.4/usr/bin/durand-pdf" "Conversion PDF prête"
paquet durand-pdf 1.4 "" "conversion de documents en PDF" /srv/depot

mkdir -p "$TMP/durand-lib-ancien-0.9/usr/share/durand"
echo "ancienne bibliothèque" > "$TMP/durand-lib-ancien-0.9/usr/share/durand/lib-ancien.txt"
paquet durand-lib-ancien 0.9 "" "bibliothèque de l'ancien logiciel de gestion" /srv/depot
script "$TMP/durand-ancien-0.9/usr/bin/durand-ancien" "Ancien logiciel de gestion (plus maintenu)"
mkdir -p "$TMP/durand-ancien-0.9/etc/durand"
echo "base=ancienne" > "$TMP/durand-ancien-0.9/etc/durand/ancien.conf"
paquet durand-ancien 0.9 "durand-lib-ancien" "ancien logiciel de gestion" /srv/depot

# Paquet téléchargé sur le site d'un éditeur : absent du dépôt, dépend de durand-pdf.
script "$TMP/outil-rapport-2.0/usr/bin/outil-rapport" "Rapport mensuel généré"
paquet outil-rapport 2.0 "durand-pdf" "générateur de rapports mensuels" /root/telechargements

# Index du dépôt « plat » (deb file:/srv/depot ./).
cd /srv/depot && dpkg-scanpackages --multiversion . /dev/null 2>/dev/null > Packages && gzip -k Packages

# L'ancien logiciel est installé (avec sa bibliothèque comme dépendance automatique), puis le dépôt
# est retiré des sources : le stagiaire devra le déclarer lui-même.
echo "deb [trusted=yes] file:/srv/depot ./" > /etc/apt/sources.list.d/tmp-durand.list
apt-get update -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/tmp-durand.list -o Dir::Etc::sourceparts=- >/dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y durand-ancien >/dev/null
rm -f /etc/apt/sources.list.d/tmp-durand.list
rm -rf /var/lib/apt/lists/* "$TMP"
