CREATE TABLE produits (id serial PRIMARY KEY, nom text NOT NULL, prix numeric(8, 2) NOT NULL);
INSERT INTO produits (nom, prix) VALUES ('Clavier', 49.90), ('Souris', 19.90), ('Écran', 189.00);
