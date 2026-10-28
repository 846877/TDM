-- Base de gestion commerciale d'Ateliers Durand : clients et commandes.
CREATE TABLE clients (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nom VARCHAR(80) NOT NULL,
  ville VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE commandes (
  id INT PRIMARY KEY AUTO_INCREMENT,
  client_id INT NOT NULL,
  montant DECIMAL(10,2) NOT NULL,
  date_commande DATE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO clients (nom, ville) VALUES
('Boulangerie Petit', 'Lyon'),
('Garage Moreau', 'Villeurbanne'),
('Menuiserie Roux', 'Lyon'),
('Pharmacie du Parc', 'Grenoble'),
('Hôtel des Alpes', 'Grenoble'),
('Imprimerie Lefebvre', 'Lyon'),
('Cabinet Bertrand', 'Villeurbanne'),
('Fromagerie Simon', 'Annecy'),
('Transports Garcia', 'Lyon'),
('Librairie Laurent', 'Saint-Étienne'),
('Atelier Michel', 'Lyon'),
('Clinique David', 'Grenoble');

INSERT INTO commandes (client_id, montant, date_commande) VALUES
(1, 1250.00, '2026-01-12'), (2, 830.50, '2026-01-15'), (3, 2400.00, '2026-01-20'),
(1, 310.00, '2026-02-02'), (4, 1520.75, '2026-02-08'), (5, 980.00, '2026-02-11'),
(6, 4300.00, '2026-02-19'), (7, 615.20, '2026-03-01'), (1, 2210.00, '2026-03-04'),
(8, 450.00, '2026-03-09'), (9, 3890.00, '2026-03-15'), (10, 275.90, '2026-03-22'),
(11, 1340.00, '2026-04-02'), (12, 5120.00, '2026-04-07'), (3, 760.00, '2026-04-13'),
(2, 1999.99, '2026-04-21'), (6, 820.00, '2026-05-03'), (9, 1430.00, '2026-05-10'),
(1, 540.00, '2026-05-18'), (4, 2870.00, '2026-05-26'), (5, 395.00, '2026-06-02'),
(7, 1105.00, '2026-06-09'), (11, 2660.00, '2026-06-17'), (12, 980.40, '2026-06-24'),
(8, 1750.00, '2026-07-01'), (10, 620.00, '2026-07-08'), (3, 3300.00, '2026-07-15'),
(6, 1490.00, '2026-08-26'), (9, 705.50, '2026-09-02'), (2, 2150.00, '2026-09-09');
