-- Base d'exemple « ventes » créée au premier démarrage (docker-entrypoint-initdb.d).
CREATE DATABASE ventes;
\connect ventes

CREATE TABLE clients (
    id      integer PRIMARY KEY,
    nom     text NOT NULL,
    ville   text NOT NULL
);

CREATE TABLE commandes (
    id          bigserial PRIMARY KEY,
    client_id   integer NOT NULL,
    montant     numeric(10, 2) NOT NULL,
    cree_le     timestamptz NOT NULL
);

INSERT INTO clients
SELECT i, 'client-' || i, (ARRAY['Paris', 'Lyon', 'Lille', 'Nantes', 'Bordeaux'])[1 + i % 5]
FROM generate_series(1, 5000) AS i;

INSERT INTO commandes (client_id, montant, cree_le)
SELECT 1 + (i * 7919) % 5000, round((10 + (i % 490))::numeric, 2),
       timestamptz '2025-01-01' + (i || ' minutes')::interval
FROM generate_series(1, 200000) AS i;

ANALYZE;
