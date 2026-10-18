# Ajouter des exercices

Les contenus sont de simples fichiers YAML : pas besoin de toucher au code. Après avoir ajouté ou
modifié un fichier, recharge la page (ou appelle `POST /api/reload` si le serveur tourne déjà).

## Exercice Python (`content/python/<id>.yaml`)

Le nom du fichier sert d'identifiant. Préfixe-le par un numéro pour garder l'ordre (`0xx` débutant,
`1xx` intermédiaire, `2xx` avancé, `3xx` expert).

### Mode `function` (par défaut) : on teste des fonctions

```yaml
title: Ma première fonction
level: debutant            # debutant | intermediaire | avance | expert
order: 3                   # ordre dans le niveau
tags: [fonctions]
summary: Phrase courte affichée dans la liste.
description: |
  Énoncé en **Markdown**.
starter: |
  def addition(a, b):
      pass
tests: |
  def test_positifs():
      "addition(2, 3) vaut 5"          # la docstring est le libellé affiché
      assert solution.addition(2, 3) == 5, "message affiché en cas d'échec"
solution: |
  def addition(a, b):
      return a + b
```

Dans `tests`, le code de l'élève est accessible via le module `solution`. Chaque fonction `test_*`
est un test ; un `assert` qui échoue ou une exception le fait échouer.

### Mode `stdio` : on compare ce que le programme affiche

```yaml
mode: stdio
cases:
  - name: Alice
    input: "Alice\n"
    output: "Salut Alice !"
```

Les espaces en fin de ligne et les lignes vides finales sont ignorés.

## Exercice réseau (`content/network/<id>.yaml`)

```yaml
title: Configurer un trunk 802.1Q
level: intermediaire
device: switch             # switch | router
hostname: SW1              # optionnel
description: |
  Énoncé en Markdown.
initial: |                 # optionnel : configuration appliquée avant l'exercice
  vlan 10
checks:                    # expressions Python évaluées sur l'équipement
  - desc: Gi0/1 en mode trunk
    expr: intf("g0/1").mode == "trunk"
    hint: Indice affiché en cas d'échec
solution: |                # commandes de référence (depuis le mode privilégié)
  configure terminal
  interface g0/1
  switchport mode trunk
  end
```

Aides disponibles dans `expr` :

| Aide | Exemple |
|------|---------|
| `d` (l'équipement) | `d.hostname == "SW1"`, `d.saved`, `d.ssh_version == 2`, `d.default_gateway` |
| `intf(nom)` | `intf("fa0/1").access_vlan == 10`, `.mode`, `.shutdown`, `.ip`, `.mask`, `.allowed_vlans()` |
| `ports(plage)` | `all(i.portfast for i in ports("fa0/1-10"))` |
| `vlan(id)` | `vlan(10) == "ADMIN"` |
| `route(réseau, masque, saut)` | `route("0.0.0.0", "0.0.0.0", "203.0.113.1")` |
| `ospf_net(réseau, wildcard, zone)` | `ospf_net("10.0.0.0", "0.0.0.3", 0)` |
| `acl(nom)` | `"deny any" in acl(10)` |
| `line(type)` | `line("vty").transport_input == "ssh"` |
| `prefix(masque)` | `prefix(intf("g0/0").mask) == 24` |

Le simulateur est dans `backend/app/network/ios.py` : pour une nouvelle commande, ajoute une `Rule`
dans le mode concerné et le champ correspondant sur `Device` ou `Interface`.

## Lab DevOps

Voir [`labs/devops/README.md`](../labs/devops/README.md).
