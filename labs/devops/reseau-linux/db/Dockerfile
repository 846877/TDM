# Redis « dans la DMZ » : il écoute sur l'adresse 10.89.20.10, ajoutée au démarrage.
FROM redis:7.2-alpine
RUN printf '#!/bin/sh\nip addr add 10.89.20.10/24 dev eth0 2>/dev/null || true\nexec redis-server --port 6380 --bind 10.89.20.10 --protected-mode no\n' > /usr/local/bin/demarrage \
    && chmod 755 /usr/local/bin/demarrage
ENTRYPOINT ["/usr/local/bin/demarrage"]
