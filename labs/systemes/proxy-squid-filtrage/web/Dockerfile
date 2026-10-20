# « Internet » : trois sites sur la même adresse (actu.example, jeux.example, social.example).
FROM ubuntu:24.04
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default \
    && mkdir -p /var/www/actu/video /var/www/jeux /var/www/social \
    && echo '<h1>Actualités du jour</h1>' > /var/www/actu/index.html \
    && head -c 200K /dev/urandom > /var/www/actu/video/bande-annonce.mp4 \
    && head -c 20K /dev/urandom > /var/www/actu/logo.png \
    && echo '<h1>Jeux en ligne</h1>' > /var/www/jeux/index.html \
    && echo '<h1>Réseau social</h1>' > /var/www/social/index.html
COPY web/sites.conf /etc/nginx/conf.d/sites.conf
CMD ["nginx", "-g", "daemon off;"]
