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
| `route(réseau, masque, saut[, distance])` | `route("0.0.0.0", "0.0.0.0", "203.0.113.1")`, route flottante : `route("0.0.0.0", "0.0.0.0", "192.0.2.1", 10)` |
| `route6(préfixe, saut[, distance])` | `route6("::/0", "2001:db8:feed::1")` (écriture IPv6 libre) |
| `ospf_net(réseau, wildcard, zone)` | `ospf_net("10.0.0.0", "0.0.0.3", 0)` ; zone par interface : `intf("g0/0").ospf_area == (1, "10")` |
| `eigrp_net(as, réseau[, wildcard])` | `eigrp_net(100, "192.168.20.0", "0.0.0.255")` |
| `rip_net(réseau)` | `rip_net("10.1.1.0")` (comparé par classe, comme IOS : `10.0.0.0`) |
| `nat(règle)` | `nat("ip nat inside source list 1 interface g0/1 overload")` (abréviations acceptées) |
| `acl(nom)` | `"deny any" in acl(10)` ; numéros de séquence : `d.acl_seqs("WEB")` |
| `line(type)` | `line("vty").transport_input == "ssh"`, `line("vty").access_class.get("in") == "ADMIN"` |
| `prefix(masque)` | `prefix(intf("g0/0").mask) == 24` |
| `ipv6(interface, adresse)` | `ipv6("g0/0", "2001:db8:acad:10::1/64")` ; link-local : `intf("g0/0").ipv6_link_local == "fe80::1"` |
| `hsrp(interface, groupe)` | `hsrp("g0/0", 10).ip == "192.168.10.1"`, `.priority`, `.preempt` |
| `members(groupe)` | `members(1) == ["Gi0/1", "Gi0/2"]` (ports du Port-channel 1) |

Champs utiles pour les autres commandes :

| Domaine | Exemples |
|---------|----------|
| Interface | `.description`, `.speed` / `.duplex` (`"auto"`, `"100"`, `"full"`), `.native_vlan`, `.voice_vlan`, `.nonegotiate`, `.is_switchport` (`False` après `no switchport`), `.channel_group` / `.channel_mode`, `.ospf_cost`, `.standby_version`, `.storm_control`, `.cdp_enabled`, `.lldp_transmit` |
| Spanning tree | `d.stp_mode`, `d.stp_priority.get(10)`, `d.stp_portfast_default`, `d.stp_bpduguard_default`, `.portfast`, `.bpduguard`, `.stp_guard == "root"` |
| VTP | `d.vtp_domain`, `d.vtp_mode`, `d.vtp_version`, `d.vtp_password` |
| Sécurité L2 | `d.dhcp_snooping`, `d.dhcp_snooping_vlans`, `d.dhcp_snooping_option82`, `d.arp_inspection_vlans`, `.dhcp_snooping_trust`, `.dhcp_snooping_rate`, `.arp_inspection_trust`, `d.errdisable_recovery`, `d.errdisable_interval` |
| Routage | `d.ip_routing`, `d.ipv6_routing`, `d.ospf[1].router_id`, `d.ospf[1].is_passive("g0/0")`, `.passive_default`, `.reference_bandwidth`, `.area_types`, `.default_originate`, `d.eigrp[100].auto_summary`, `d.rip.version` |
| Services | `d.ntp_servers`, `d.clock_timezone == ("CET", 1)`, `d.logging_hosts`, `d.logging_trap`, `d.snmp_communities.get("RO-COMM") == ("RO", "ACL")`, `d.snmp_location`, `d.lldp_run`, `d.cdp_run`, `d.http_server` |
| Sécurité | `d.enable_secret`, `d.password_encryption`, `d.min_password_length`, `d.aaa_new_model`, `d.aaa_authentication.get("login default")`, `d.login_block == (120, 3, 60)`, `d.users["admin"]["secret"]` |

Les commandes `show` correspondantes existent (`show etherchannel summary`, `show vtp status`,
`show spanning-tree summary`, `show standby brief`, `show ipv6 route`, `show ip nat translations`,
`show ip dhcp snooping`...) et acceptent les filtres `| include`, `| exclude`, `| begin` et `| section`.

Le simulateur est dans `backend/app/network/ios.py` : pour une nouvelle commande, ajoute une `Rule`
dans le mode concerné et le champ correspondant sur `Device` ou `Interface`. Les tests vérifient que
chaque `solution` valide toutes les vérifications (y compris tapée dans le terminal depuis le mode
utilisateur) et que l'état initial en échoue au moins une.

## Lab DevOps

Voir [`labs/devops/README.md`](../labs/devops/README.md).
