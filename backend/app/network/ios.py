"""Simulateur simplifié de CLI Cisco IOS (switch et routeur).

L'objectif n'est pas d'émuler IOS à 100 %, mais de reproduire les commandes et les
modes qu'on pratique dans les TP réseaux (VLAN, trunks, adressage, routage statique,
OSPF, DHCP, ACL, SSH, sécurité de ports...) afin qu'une moulinette puisse vérifier
la configuration obtenue. Les abréviations IOS (``conf t``, ``int fa0/1``,
``sh vlan br``...) sont acceptées.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------
# Modèle de l'équipement
# ---------------------------------------------------------------------------

IFACE_TYPES = {
    "fastethernet": "FastEthernet",
    "gigabitethernet": "GigabitEthernet",
    "serial": "Serial",
    "vlan": "Vlan",
    "loopback": "Loopback",
}
IFACE_SHORT = {"FastEthernet": "Fa", "GigabitEthernet": "Gi", "Serial": "Se", "Vlan": "Vlan", "Loopback": "Lo"}


@dataclass
class Interface:
    name: str
    description: str = ""
    shutdown: bool = True
    mode: str | None = None  # "access", "trunk" ou None (dynamique)
    access_vlan: int = 1
    voice_vlan: int | None = None
    trunk_allowed: str = "all"
    native_vlan: int = 1
    ip: str | None = None
    mask: str | None = None
    secondary: list[tuple[str, str]] = field(default_factory=list)
    encapsulation_vlan: int | None = None
    access_groups: dict[str, str] = field(default_factory=dict)  # "in"/"out" -> acl
    portfast: bool = False
    bpduguard: bool = False
    port_security: bool = False
    port_security_max: int = 1
    port_security_violation: str = "shutdown"
    port_security_sticky: bool = False
    nat: str | None = None  # "inside" / "outside"
    helper_addresses: list[str] = field(default_factory=list)
    clock_rate: int | None = None
    channel_group: int | None = None

    @property
    def short(self) -> str:
        kind = re.match(r"[A-Za-z]+", self.name).group(0)
        return IFACE_SHORT.get(kind, kind) + self.name[len(kind):]

    @property
    def is_physical(self) -> bool:
        return not self.name.startswith(("Vlan", "Loopback")) and "." not in self.name

    @property
    def is_switchport(self) -> bool:
        return self._switch_owned

    _switch_owned: bool = False

    def allowed_vlans(self) -> set[int] | None:
        """Ensemble des VLAN autorisés sur le trunk (None = tous)."""
        if self.trunk_allowed in ("all", ""):
            return None
        if self.trunk_allowed == "none":
            return set()
        return parse_vlan_list(self.trunk_allowed)


@dataclass
class Line:
    password: str | None = None
    login: str | None = None  # None, "login" ou "local"
    transport_input: str | None = None
    exec_timeout: str | None = None
    logging_synchronous: bool = False


@dataclass
class DhcpPool:
    name: str
    network: str | None = None
    mask: str | None = None
    default_router: str | None = None
    dns_server: str | None = None
    domain_name: str | None = None


@dataclass
class OspfProcess:
    pid: int
    router_id: str | None = None
    networks: list[tuple[str, str, str]] = field(default_factory=list)  # (réseau, wildcard, zone)
    passive: set[str] = field(default_factory=set)
    default_originate: bool = False


class Device:
    def __init__(self, kind: str = "switch", hostname: str | None = None):
        self.kind = kind
        self.hostname = hostname or ("Switch" if kind == "switch" else "Router")
        self.enable_secret: str | None = None
        self.enable_password: str | None = None
        self.password_encryption = False
        self.banner_motd: str | None = None
        self.domain_name: str | None = None
        self.domain_lookup = True
        self.default_gateway: str | None = None
        self.ip_routing = kind == "router"
        self.rsa_modulus: int | None = None
        self.ssh_version: int | None = None
        self.users: dict[str, dict] = {}
        self.vlans: dict[int, str] = {1: "default"}
        self.interfaces: dict[str, Interface] = {}
        self.lines = {"console": Line(), "vty": Line()}
        self.static_routes: list[tuple[str, str, str]] = []
        self.ospf: dict[int, OspfProcess] = {}
        self.dhcp_pools: dict[str, DhcpPool] = {}
        self.dhcp_excluded: list[tuple[str, str]] = []
        self.acls: dict[str, list[str]] = {}
        self.nat_rules: list[str] = []
        self.vtp_mode = "server"
        self.vtp_domain: str | None = None
        self.stp_mode = "pvst"
        self.stp_priority: dict[int, int] = {}
        self.startup_config: str | None = None
        self._build_ports()

    def _build_ports(self) -> None:
        if self.kind == "switch":
            names = [f"FastEthernet0/{i}" for i in range(1, 25)] + ["GigabitEthernet0/1", "GigabitEthernet0/2"]
            for name in names:
                iface = Interface(name, shutdown=False)
                iface._switch_owned = True
                self.interfaces[name] = iface
            self.interfaces["Vlan1"] = Interface("Vlan1", shutdown=True)
        else:
            for name in ["GigabitEthernet0/0", "GigabitEthernet0/1", "GigabitEthernet0/2",
                         "Serial0/0/0", "Serial0/0/1"]:
                self.interfaces[name] = Interface(name)

    # -- aides utilisées par les moulinettes ---------------------------------

    def intf(self, name: str) -> Interface:
        canonical = normalize_iface(name)
        if canonical is None or canonical not in self.interfaces:
            raise KeyError(f"interface inconnue : {name}")
        return self.interfaces[canonical]

    def has_intf(self, name: str) -> bool:
        canonical = normalize_iface(name)
        return canonical is not None and canonical in self.interfaces

    def vlan_name(self, vlan_id: int) -> str | None:
        return self.vlans.get(vlan_id)

    def vlan_ports(self, vlan_id: int) -> list[str]:
        return [i.short for i in self.interfaces.values()
                if i.is_switchport and i.mode != "trunk" and i.access_vlan == vlan_id]

    def has_route(self, network: str, mask: str, next_hop: str | None = None) -> bool:
        return any(r[0] == network and r[1] == mask and (next_hop is None or r[2] == next_hop)
                   for r in self.static_routes)

    def ospf_has_network(self, network: str, wildcard: str, area: str | int) -> bool:
        return any((network, wildcard, str(area)) in p.networks for p in self.ospf.values())

    @property
    def saved(self) -> bool:
        return self.startup_config is not None and self.startup_config == self.running_config()

    # -- génération de la configuration --------------------------------------

    def running_config(self) -> str:
        out = ["!", "version 15.2", "no service pad", "service timestamps debug datetime msec",
               "service timestamps log datetime msec"]
        out.append("service password-encryption" if self.password_encryption else "no service password-encryption")
        out += ["!", f"hostname {self.hostname}", "!"]
        if self.enable_secret:
            out.append(f"enable secret 5 {_fake_hash(self.enable_secret)}")
        if self.enable_password:
            pwd = _type7(self.enable_password) if self.password_encryption else self.enable_password
            out.append(f"enable password {'7 ' if self.password_encryption else ''}{pwd}")
        for name, user in self.users.items():
            if user.get("secret"):
                out.append(f"username {name} privilege {user.get('privilege', 1)} secret 5 {_fake_hash(user['secret'])}")
            else:
                out.append(f"username {name} privilege {user.get('privilege', 1)} password {user.get('password', '')}")
        out.append("!")
        if not self.domain_lookup:
            out.append("no ip domain-lookup")
        if self.domain_name:
            out.append(f"ip domain-name {self.domain_name}")
        if self.ssh_version:
            out.append(f"ip ssh version {self.ssh_version}")
        if self.kind == "switch" and self.ip_routing:
            out.append("ip routing")
        for start, end in self.dhcp_excluded:
            out.append(f"ip dhcp excluded-address {start}{' ' + end if end else ''}")
        for pool in self.dhcp_pools.values():
            out.append(f"ip dhcp pool {pool.name}")
            if pool.network:
                out.append(f" network {pool.network} {pool.mask}")
            if pool.default_router:
                out.append(f" default-router {pool.default_router}")
            if pool.dns_server:
                out.append(f" dns-server {pool.dns_server}")
            if pool.domain_name:
                out.append(f" domain-name {pool.domain_name}")
        if self.kind == "switch":
            out += ["!", f"spanning-tree mode {self.stp_mode}"]
            for vlan, prio in sorted(self.stp_priority.items()):
                out.append(f"spanning-tree vlan {vlan} priority {prio}")
            if self.vtp_mode != "server":
                out.append(f"vtp mode {self.vtp_mode}")
            if self.vtp_domain:
                out.append(f"vtp domain {self.vtp_domain}")
        out.append("!")
        for vid, name in sorted(self.vlans.items()):
            if vid == 1:
                continue
            out.append(f"vlan {vid}")
            if name != default_vlan_name(vid):
                out.append(f" name {name}")
            out.append("!")
        for iface in sorted(self.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            out.append(f"interface {iface.name}")
            out += [" " + line for line in self._iface_lines(iface)]
            out.append("!")
        if self.default_gateway:
            out.append(f"ip default-gateway {self.default_gateway}")
        for pid, proc in sorted(self.ospf.items()):
            out.append(f"router ospf {pid}")
            if proc.router_id:
                out.append(f" router-id {proc.router_id}")
            for name in sorted(proc.passive):
                out.append(f" passive-interface {name}")
            for net, wild, area in proc.networks:
                out.append(f" network {net} {wild} area {area}")
            if proc.default_originate:
                out.append(" default-information originate")
            out.append("!")
        for rule in self.nat_rules:
            out.append(rule)
        for net, mask, nh in self.static_routes:
            out.append(f"ip route {net} {mask} {nh}")
        out.append("!")
        for name, entries in self.acls.items():
            if name.isdigit():
                out += [f"access-list {name} {entry}" for entry in entries]
            else:
                kind = "extended" if entries and entries[0].startswith("__ext__") else "standard"
                out.append(f"ip access-list {kind} {name}")
                out += [" " + e.replace("__ext__ ", "") for e in entries if e != "__ext__"]
        if self.banner_motd:
            out += ["!", f"banner motd ^C{self.banner_motd}^C"]
        out.append("!")
        for kind, label in (("console", "line con 0"), ("vty", "line vty 0 4" if self.kind == "router" else "line vty 0 15")):
            line = self.lines[kind]
            out.append(label)
            if line.exec_timeout:
                out.append(f" exec-timeout {line.exec_timeout}")
            if line.password:
                pwd = _type7(line.password) if self.password_encryption else line.password
                out.append(f" password {'7 ' if self.password_encryption else ''}{pwd}")
            if line.logging_synchronous:
                out.append(" logging synchronous")
            if line.login == "local":
                out.append(" login local")
            elif line.login == "login":
                out.append(" login")
            if line.transport_input:
                out.append(f" transport input {line.transport_input}")
        out += ["!", "end"]
        return "\n".join(out)

    def _iface_lines(self, iface: Interface) -> list[str]:
        lines = []
        if iface.description:
            lines.append(f"description {iface.description}")
        if iface.encapsulation_vlan is not None:
            lines.append(f"encapsulation dot1Q {iface.encapsulation_vlan}")
        if iface.is_switchport:
            if iface.mode == "trunk":
                if iface.native_vlan != 1:
                    lines.append(f"switchport trunk native vlan {iface.native_vlan}")
                if iface.trunk_allowed != "all":
                    lines.append(f"switchport trunk allowed vlan {iface.trunk_allowed}")
                lines.append("switchport mode trunk")
            else:
                if iface.access_vlan != 1:
                    lines.append(f"switchport access vlan {iface.access_vlan}")
                if iface.mode == "access":
                    lines.append("switchport mode access")
            if iface.voice_vlan:
                lines.append(f"switchport voice vlan {iface.voice_vlan}")
            if iface.port_security:
                lines.append("switchport port-security")
                if iface.port_security_max != 1:
                    lines.append(f"switchport port-security maximum {iface.port_security_max}")
                if iface.port_security_violation != "shutdown":
                    lines.append(f"switchport port-security violation {iface.port_security_violation}")
                if iface.port_security_sticky:
                    lines.append("switchport port-security mac-address sticky")
            if iface.channel_group:
                lines.append(f"channel-group {iface.channel_group} mode active")
            if iface.portfast:
                lines.append("spanning-tree portfast")
            if iface.bpduguard:
                lines.append("spanning-tree bpduguard enable")
        if iface.ip:
            lines.append(f"ip address {iface.ip} {iface.mask}")
            for ip, mask in iface.secondary:
                lines.append(f"ip address {ip} {mask} secondary")
        elif not iface.is_switchport:
            lines.append("no ip address")
        for helper in iface.helper_addresses:
            lines.append(f"ip helper-address {helper}")
        for direction, acl in sorted(iface.access_groups.items()):
            lines.append(f"ip access-group {acl} {direction}")
        if iface.nat:
            lines.append(f"ip nat {iface.nat}")
        if iface.clock_rate:
            lines.append(f"clock rate {iface.clock_rate}")
        if iface.shutdown:
            lines.append("shutdown")
        return lines


def default_vlan_name(vid: int) -> str:
    return "default" if vid == 1 else f"VLAN{vid:04d}"


def _fake_hash(secret: str) -> str:
    import hashlib

    return "$1$" + hashlib.md5(secret.encode()).hexdigest()[:4] + "$" + hashlib.md5(secret[::-1].encode()).hexdigest()[:22]


def _type7(password: str) -> str:
    return "".join(f"{(ord(c) ^ 0x5A):02X}" for c in password)[:24].rjust(4, "0")


def iface_sort_key(name: str):
    order = ["FastEthernet", "GigabitEthernet", "Serial", "Loopback", "Vlan"]
    kind = re.match(r"[A-Za-z]+", name).group(0)
    nums = [int(n) for n in re.findall(r"\d+", name[len(kind):])]
    return (order.index(kind) if kind in order else 99, nums)


def parse_vlan_list(text: str) -> set[int]:
    result: set[int] = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            result.update(range(int(start), int(end) + 1))
        else:
            result.add(int(part))
    return result


def format_vlan_list(vlans: set[int]) -> str:
    ordered = sorted(vlans)
    parts = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        parts.append(str(ordered[i]) if i == j else f"{ordered[i]}-{ordered[j]}")
        i = j + 1
    return ",".join(parts)


def normalize_iface(text: str) -> str | None:
    """``fa0/1`` -> ``FastEthernet0/1``, ``g0/0.10`` -> ``GigabitEthernet0/0.10``, ``vlan 10`` -> ``Vlan10``."""
    text = text.replace(" ", "")
    match = re.match(r"^([A-Za-z]+)([\d/.]+)$", text)
    if not match:
        return None
    prefix, number = match.group(1).lower(), match.group(2)
    candidates = [full for key, full in IFACE_TYPES.items() if key.startswith(prefix)]
    if len(candidates) != 1:
        if prefix in ("f", "fa"):
            candidates = ["FastEthernet"]
        elif prefix in ("g", "gi"):
            candidates = ["GigabitEthernet"]
        elif prefix in ("s", "se"):
            candidates = ["Serial"]
        elif prefix in ("lo",):
            candidates = ["Loopback"]
        else:
            return None
    return candidates[0] + number


def valid_ip(text: str) -> bool:
    try:
        ipaddress.IPv4Address(text)
    except ValueError:
        return False
    return True


def valid_mask(text: str) -> bool:
    if not valid_ip(text):
        return False
    bits = "".join(f"{int(o):08b}" for o in text.split("."))
    return "01" not in bits


def mask_to_prefix(mask: str) -> int:
    return sum(bin(int(o)).count("1") for o in mask.split("."))


# ---------------------------------------------------------------------------
# Analyseur de commandes avec abréviations
# ---------------------------------------------------------------------------

class CommandError(Exception):
    pass


INVALID = "% Invalid input detected at '^' marker."
INCOMPLETE = "% Incomplete command."


@dataclass
class Rule:
    pattern: list[str]
    handler: Callable
    help: str = ""
    negatable: bool = True


def _is_placeholder(word: str) -> bool:
    return word.startswith("<")


def match_rules(rules: list[Rule], tokens: list[str]) -> tuple[Rule, list[str]]:
    """Trouve la règle correspondant aux mots tapés, en acceptant les abréviations."""
    candidates = [(rule, []) for rule in rules]
    for position, token in enumerate(tokens):
        low = token.lower()
        next_candidates = []
        rest_matches = [(r, a) for r, a in candidates
                        if position < len(r.pattern) + 1 and _rest_at(r, position)]
        keyword_rules = [(r, a) for r, a in candidates
                         if position < len(r.pattern) and not _is_placeholder(r.pattern[position])]
        exact = [(r, a) for r, a in keyword_rules if r.pattern[position] == low]
        if exact:
            next_candidates = exact
        else:
            prefixed = [(r, a) for r, a in keyword_rules if r.pattern[position].startswith(low)]
            keywords = {r.pattern[position] for r, _ in prefixed}
            if len(keywords) > 1:
                raise CommandError(f'% Ambiguous command:  "{" ".join(tokens[:position + 1])}"')
            next_candidates = prefixed
        if not next_candidates:
            placeholders = [(r, a + [token]) for r, a in candidates
                            if position < len(r.pattern) and _is_placeholder(r.pattern[position])
                            and r.pattern[position] != "<rest>"]
            next_candidates = placeholders
        if not next_candidates and rest_matches:
            rule, args = rest_matches[0]
            return rule, args + [" ".join(tokens[position:])]
        if not next_candidates:
            raise CommandError(INVALID)
        candidates = next_candidates
    complete = [(r, a) for r, a in candidates if len(r.pattern) == len(tokens)]
    if complete:
        return complete[0]
    optional_rest = [(r, a) for r, a in candidates
                     if len(r.pattern) == len(tokens) + 1 and r.pattern[-1] == "<rest>"]
    if optional_rest:
        rule, args = optional_rest[0]
        return rule, args + [""]
    raise CommandError(INCOMPLETE)


def _rest_at(rule: Rule, position: int) -> bool:
    return position < len(rule.pattern) and rule.pattern[position] == "<rest>"


def help_for(rules: list[Rule], tokens: list[str], partial: str) -> list[str]:
    """Aide contextuelle « ? » : mots possibles à la position suivante."""
    words: dict[str, str] = {}
    for rule in rules:
        pattern = rule.pattern
        if len(pattern) <= len(tokens):
            continue
        ok = True
        for position, token in enumerate(tokens):
            word = pattern[position]
            if _is_placeholder(word):
                continue
            if not word.startswith(token.lower()):
                ok = False
                break
        if not ok:
            continue
        nxt = pattern[len(tokens)]
        if nxt.startswith(partial.lower()) or _is_placeholder(nxt):
            words.setdefault(nxt, rule.help if len(pattern) == len(tokens) + 1 else "")
    return [f"  {w:<22}{h}" for w, h in sorted(words.items())]


# ---------------------------------------------------------------------------
# Session CLI
# ---------------------------------------------------------------------------

MODE_PROMPTS = {
    "user": "{h}>",
    "exec": "{h}#",
    "config": "{h}(config)#",
    "if": "{h}(config-if)#",
    "if-range": "{h}(config-if-range)#",
    "subif": "{h}(config-subif)#",
    "vlan": "{h}(config-vlan)#",
    "line": "{h}(config-line)#",
    "router": "{h}(config-router)#",
    "dhcp": "{h}(dhcp-config)#",
    "acl-std": "{h}(config-std-nacl)#",
    "acl-ext": "{h}(config-ext-nacl)#",
}


class Session:
    def __init__(self, device: Device):
        self.device = device
        self.mode = "user"
        self.ifaces: list[str] = []
        self.vlan_ids: list[int] = []
        self.line_kind: str | None = None
        self.ospf_pid: int | None = None
        self.dhcp_pool: str | None = None
        self.acl_name: str | None = None
        self.history: list[str] = []
        self.rules = self._build_rules()

    @property
    def prompt(self) -> str:
        mode = self.mode
        if mode == "if" and self.ifaces and "." in self.ifaces[0]:
            mode = "subif"
        return MODE_PROMPTS[mode].format(h=self.device.hostname)

    # -- exécution -----------------------------------------------------------

    def execute(self, line: str) -> str:
        raw = line.strip()
        if not raw or raw.startswith("!"):
            return ""
        self.history.append(raw)
        if raw.endswith("?"):
            return self._help(raw[:-1])
        tokens = raw.split()
        try:
            return self._dispatch(tokens) or ""
        except CommandError as exc:
            return str(exc)

    def _dispatch(self, tokens: list[str]) -> str | None:
        mode = self.mode
        if mode not in ("user", "exec") and tokens[0].lower() == "do" and len(tokens) > 1:
            previous = self.mode
            self.mode = "exec"
            try:
                return self._dispatch(tokens[1:])
            finally:
                self.mode = previous
        negate = False
        if mode not in ("user", "exec") and tokens[0].lower() == "no" and len(tokens) > 1:
            negate = True
            tokens = tokens[1:]
        rules = self.rules[self._rule_mode()]
        if mode not in ("user", "exec", "config"):
            # Comme IOS, une commande de configuration globale tapée dans un sous-mode
            # y est acceptée (et nous ramène en mode config).
            try:
                rule, args = match_rules(rules, tokens)
            except CommandError as first_error:
                try:
                    rule, args = match_rules(self.rules["config"], tokens)
                except CommandError:
                    raise first_error from None
                self._exit_to_config()
        else:
            rule, args = match_rules(rules, tokens)
        if negate and not rule.negatable:
            raise CommandError(INVALID)
        return rule.handler(args, negate)

    def _rule_mode(self) -> str:
        return "if" if self.mode == "if-range" else self.mode

    def _help(self, text: str) -> str:
        tokens = text.split()
        partial = ""
        if text and not text.endswith(" "):
            partial = tokens.pop() if tokens else ""
        if tokens and tokens[0].lower() in ("no", "do") and self.mode not in ("user", "exec"):
            tokens = tokens[1:]
        lines = help_for(self.rules[self._rule_mode()], tokens, partial)
        return "\n".join(lines) if lines else "% Unrecognized command"

    def _exit_to_config(self) -> None:
        self.mode = "config"
        self.ifaces = []
        self.vlan_ids = []
        self.line_kind = None
        self.ospf_pid = None
        self.dhcp_pool = None
        self.acl_name = None

    # -- règles --------------------------------------------------------------

    def _build_rules(self) -> dict[str, list[Rule]]:
        R = Rule
        show = [
            R(["show", "running-config"], self.show_run, "Configuration courante"),
            R(["show", "startup-config"], self.show_startup, "Configuration sauvegardée"),
            R(["show", "vlan", "brief"], self.show_vlan_brief, "Résumé des VLAN"),
            R(["show", "vlan"], self.show_vlan_brief, "Liste des VLAN"),
            R(["show", "ip", "interface", "brief"], self.show_ip_int_brief, "Résumé des interfaces"),
            R(["show", "interfaces", "trunk"], self.show_trunk, "Interfaces en trunk"),
            R(["show", "interfaces", "status"], self.show_int_status, "État des ports"),
            R(["show", "ip", "route"], self.show_ip_route, "Table de routage"),
            R(["show", "ip", "protocols"], self.show_ip_protocols, "Protocoles de routage"),
            R(["show", "ip", "dhcp", "pool"], self.show_dhcp_pool, "Pools DHCP"),
            R(["show", "access-lists"], self.show_acls, "Listes de contrôle d'accès"),
            R(["show", "port-security"], self.show_port_security, "Sécurité des ports"),
            R(["show", "version"], self.show_version, "Version du système"),
            R(["show", "history"], lambda a, n: "\n".join("  " + h for h in self.history), "Historique"),
            R(["show", "ip", "ssh"], self.show_ssh, "État SSH"),
        ]
        exit_rule = R(["exit"], self.cmd_exit, "Quitter le mode courant", negatable=False)
        end_rule = R(["end"], self.cmd_end, "Revenir au mode privilégié", negatable=False)
        user = [
            R(["enable"], self.cmd_enable, "Passer en mode privilégié"),
            R(["show", "version"], self.show_version, "Version du système"),
            R(["show", "ip", "interface", "brief"], self.show_ip_int_brief, "Résumé des interfaces"),
            R(["ping", "<ip>"], self.cmd_ping, "Tester la connectivité"),
            exit_rule,
        ]
        exec_ = show + [
            R(["configure", "terminal"], self.cmd_conf_t, "Entrer en configuration"),
            R(["disable"], self.cmd_disable, "Revenir au mode utilisateur"),
            R(["copy", "running-config", "startup-config"], self.cmd_write, "Sauvegarder la configuration"),
            R(["write", "memory"], self.cmd_write, "Sauvegarder la configuration"),
            R(["write"], self.cmd_write, "Sauvegarder la configuration"),
            R(["erase", "startup-config"], self.cmd_erase, "Effacer la configuration sauvegardée"),
            R(["reload"], self.cmd_reload, "Redémarrer"),
            R(["ping", "<ip>"], self.cmd_ping, "Tester la connectivité"),
            R(["enable"], lambda a, n: None, ""),
            exit_rule,
        ]
        config = [
            R(["hostname", "<name>"], self.cfg_hostname, "Nom de l'équipement"),
            R(["enable", "secret", "<rest>"], self.cfg_enable_secret, "Mot de passe privilégié chiffré"),
            R(["enable", "password", "<rest>"], self.cfg_enable_password, "Mot de passe privilégié"),
            R(["service", "password-encryption"], self.cfg_service_pwd, "Chiffrer les mots de passe"),
            R(["banner", "motd", "<rest>"], self.cfg_banner, "Bannière"),
            R(["ip", "domain-name", "<name>"], self.cfg_domain_name, "Nom de domaine"),
            R(["ip", "domain", "name", "<name>"], self.cfg_domain_name, "Nom de domaine"),
            R(["ip", "domain-lookup"], self.cfg_domain_lookup, "Résolution DNS"),
            R(["ip", "default-gateway", "<ip>"], self.cfg_default_gw, "Passerelle par défaut"),
            R(["ip", "routing"], self.cfg_ip_routing, "Activer le routage"),
            R(["ip", "route", "<net>", "<mask>", "<nh>"], self.cfg_ip_route, "Route statique"),
            R(["ip", "ssh", "version", "<n>"], self.cfg_ssh_version, "Version SSH"),
            R(["ip", "dhcp", "pool", "<name>"], self.cfg_dhcp_pool, "Pool DHCP"),
            R(["ip", "dhcp", "excluded-address", "<ip>", "<rest>"], self.cfg_dhcp_excluded, "Adresses exclues"),
            R(["ip", "access-list", "standard", "<name>"], self.cfg_named_acl_std, "ACL nommée standard"),
            R(["ip", "access-list", "extended", "<name>"], self.cfg_named_acl_ext, "ACL nommée étendue"),
            R(["ip", "nat", "<rest>"], self.cfg_nat, "Traduction d'adresses"),
            R(["access-list", "<num>", "<rest>"], self.cfg_access_list, "Liste de contrôle d'accès"),
            R(["crypto", "key", "generate", "rsa", "<rest>"], self.cfg_crypto, "Générer les clés RSA"),
            R(["username", "<name>", "<rest>"], self.cfg_username, "Utilisateur local"),
            R(["vlan", "<id>"], self.cfg_vlan, "Créer/modifier un VLAN"),
            R(["interface", "range", "<rest>"], self.cfg_interface_range, "Plage d'interfaces"),
            R(["interface", "<if>", "<rest>"], self.cfg_interface, "Configurer une interface"),
            R(["line", "console", "<n>"], self.cfg_line_con, "Ligne console"),
            R(["line", "vty", "<a>", "<b>"], self.cfg_line_vty, "Lignes virtuelles (telnet/ssh)"),
            R(["router", "ospf", "<pid>"], self.cfg_router_ospf, "Routage OSPF"),
            R(["spanning-tree", "mode", "<mode>"], self.cfg_stp_mode, "Mode spanning-tree"),
            R(["spanning-tree", "vlan", "<id>", "priority", "<n>"], self.cfg_stp_priority, "Priorité STP"),
            R(["spanning-tree", "vlan", "<id>", "root", "<kind>"], self.cfg_stp_root, "Pont racine STP"),
            R(["vtp", "mode", "<mode>"], self.cfg_vtp_mode, "Mode VTP"),
            R(["vtp", "domain", "<name>"], self.cfg_vtp_domain, "Domaine VTP"),
            exit_rule, end_rule,
        ]
        iface = [
            R(["description", "<rest>"], self.if_description, "Description"),
            R(["shutdown"], self.if_shutdown, "Désactiver l'interface"),
            R(["switchport", "mode", "<mode>"], self.if_sw_mode, "Mode access/trunk"),
            R(["switchport", "access", "vlan", "<id>"], self.if_access_vlan, "VLAN d'accès"),
            R(["switchport", "voice", "vlan", "<id>"], self.if_voice_vlan, "VLAN voix"),
            R(["switchport", "trunk", "allowed", "vlan", "<rest>"], self.if_trunk_allowed, "VLAN autorisés"),
            R(["switchport", "trunk", "native", "vlan", "<id>"], self.if_native, "VLAN natif"),
            R(["switchport", "trunk", "encapsulation", "dot1q"], lambda a, n: None, "Encapsulation 802.1Q"),
            R(["switchport", "nonegotiate"], lambda a, n: None, "Désactiver DTP"),
            R(["switchport", "port-security"], self.if_port_security, "Sécurité de port"),
            R(["switchport", "port-security", "maximum", "<n>"], self.if_ps_max, "Nombre max d'adresses MAC"),
            R(["switchport", "port-security", "violation", "<mode>"], self.if_ps_violation, "Action en cas de violation"),
            R(["switchport", "port-security", "mac-address", "sticky"], self.if_ps_sticky, "Apprentissage sticky"),
            R(["spanning-tree", "portfast"], self.if_portfast, "PortFast"),
            R(["spanning-tree", "bpduguard", "enable"], self.if_bpduguard, "BPDU Guard"),
            R(["ip", "address", "<ip>", "<mask>", "<rest>"], self.if_ip, "Adresse IP"),
            R(["ip", "address", "dhcp"], self.if_ip_dhcp, "Adresse par DHCP"),
            R(["ip", "helper-address", "<ip>"], self.if_helper, "Relais DHCP"),
            R(["ip", "access-group", "<acl>", "<dir>"], self.if_access_group, "Appliquer une ACL"),
            R(["ip", "nat", "<dir>"], self.if_nat, "Interface NAT inside/outside"),
            R(["encapsulation", "dot1q", "<id>"], self.if_encapsulation, "Sous-interface 802.1Q"),
            R(["clock", "rate", "<n>"], self.if_clock_rate, "Horloge (DCE)"),
            R(["channel-group", "<n>", "mode", "<mode>"], self.if_channel_group, "EtherChannel"),
            R(["speed", "<rest>"], lambda a, n: None, "Vitesse"),
            R(["duplex", "<rest>"], lambda a, n: None, "Duplex"),
            R(["interface", "range", "<rest>"], self.cfg_interface_range, "Plage d'interfaces"),
            R(["interface", "<if>", "<rest>"], self.cfg_interface, "Changer d'interface"),
            exit_rule, end_rule,
        ]
        vlan = [
            R(["name", "<name>"], self.vlan_name_cmd, "Nom du VLAN"),
            R(["vlan", "<id>"], self.cfg_vlan, "Créer/modifier un VLAN"),
            exit_rule, end_rule,
        ]
        line = [
            R(["password", "<rest>"], self.line_password, "Mot de passe"),
            R(["login"], self.line_login, "Exiger l'authentification"),
            R(["login", "local"], self.line_login_local, "Authentification par utilisateurs locaux"),
            R(["transport", "input", "<rest>"], self.line_transport, "Protocoles autorisés"),
            R(["exec-timeout", "<rest>"], self.line_exec_timeout, "Délai d'inactivité"),
            R(["logging", "synchronous"], self.line_logging_sync, "Messages synchronisés"),
            exit_rule, end_rule,
        ]
        router = [
            R(["network", "<net>", "<wild>", "area", "<area>"], self.ospf_network, "Annoncer un réseau"),
            R(["router-id", "<ip>"], self.ospf_router_id, "Identifiant du routeur"),
            R(["passive-interface", "<rest>"], self.ospf_passive, "Interface passive"),
            R(["default-information", "originate"], self.ospf_default, "Propager la route par défaut"),
            exit_rule, end_rule,
        ]
        dhcp = [
            R(["network", "<net>", "<mask>"], self.dhcp_network, "Réseau du pool"),
            R(["default-router", "<ip>"], self.dhcp_router, "Passerelle distribuée"),
            R(["dns-server", "<ip>"], self.dhcp_dns, "Serveur DNS distribué"),
            R(["domain-name", "<name>"], self.dhcp_domain, "Domaine distribué"),
            exit_rule, end_rule,
        ]
        acl = [
            R(["permit", "<rest>"], lambda a, n: self.acl_entry("permit", a, n), "Autoriser"),
            R(["deny", "<rest>"], lambda a, n: self.acl_entry("deny", a, n), "Refuser"),
            R(["remark", "<rest>"], lambda a, n: self.acl_entry("remark", a, n), "Commentaire"),
            exit_rule, end_rule,
        ]
        return {"user": user, "exec": exec_, "config": config, "if": iface, "vlan": vlan,
                "line": line, "router": router, "dhcp": dhcp, "acl-std": acl, "acl-ext": acl}

    # -- commandes exec ------------------------------------------------------

    def cmd_enable(self, args, negate):
        self.mode = "exec"

    def cmd_disable(self, args, negate):
        self.mode = "user"

    def cmd_conf_t(self, args, negate):
        self.mode = "config"
        return "Enter configuration commands, one per line.  End with CNTL/Z."

    def cmd_exit(self, args, negate):
        if self.mode in ("user", "exec"):
            self.mode = "user"
            return "\n" + self.device.hostname + " con0 is now available\n\nPress RETURN to get started."
        if self.mode == "config":
            self.mode = "exec"
        else:
            self._exit_to_config()

    def cmd_end(self, args, negate):
        self._exit_to_config()
        self.mode = "exec"

    def cmd_write(self, args, negate):
        self.device.startup_config = self.device.running_config()
        return "Building configuration...\n[OK]"

    def cmd_erase(self, args, negate):
        self.device.startup_config = None
        return "Erasing the nvram filesystem will remove all configuration files! Continue? [confirm]\n[OK]\nErase of nvram: complete"

    def cmd_reload(self, args, negate):
        return "% Rechargement simulé : la configuration courante est conservée dans ce simulateur."

    def cmd_ping(self, args, negate):
        target = args[0]
        if not valid_ip(target):
            raise CommandError("% Unrecognized host or address.")
        connected = any(
            i.ip and not i.shutdown and ipaddress.IPv4Address(target) in
            ipaddress.IPv4Network(f"{i.ip}/{i.mask}", strict=False)
            for i in self.device.interfaces.values()
        )
        own = any(i.ip == target and not i.shutdown for i in self.device.interfaces.values())
        result = "!!!!!" if own or connected else "....."
        rate = "100 percent (5/5)" if result == "!!!!!" else "0 percent (0/5)"
        return ("Type escape sequence to abort.\n"
                f"Sending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n"
                f"{result}\nSuccess rate is {rate}"
                + ("" if result == "!!!!!" else "\n(simulateur : seules les adresses des réseaux connectés répondent)"))

    # -- show ----------------------------------------------------------------

    def show_run(self, args, negate):
        cfg = self.device.running_config()
        return f"Building configuration...\n\nCurrent configuration : {len(cfg)} bytes\n{cfg}"

    def show_startup(self, args, negate):
        if not self.device.startup_config:
            return "startup-config is not present"
        return self.device.startup_config

    def show_vlan_brief(self, args, negate):
        if self.device.kind != "switch":
            raise CommandError(INVALID)
        lines = ["", "VLAN Name                             Status    Ports",
                 "---- -------------------------------- --------- -------------------------------"]
        for vid, name in sorted(self.device.vlans.items()):
            ports = self.device.vlan_ports(vid)
            chunks = [", ".join(ports[i:i + 4]) for i in range(0, len(ports), 4)] or [""]
            lines.append(f"{vid:<4} {name:<32} active    {chunks[0]}")
            for chunk in chunks[1:]:
                lines.append(" " * 48 + chunk)
        for vid, name in ((1002, "fddi-default"), (1003, "token-ring-default"),
                          (1004, "fddinet-default"), (1005, "trnet-default")):
            lines.append(f"{vid:<4} {name:<32} act/unsup")
        return "\n".join(lines)

    def show_ip_int_brief(self, args, negate):
        lines = ["Interface              IP-Address      OK? Method Status                Protocol"]
        for iface in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            status = "administratively down" if iface.shutdown else "up"
            proto = "down" if iface.shutdown else "up"
            if not iface.shutdown and iface.is_switchport:
                status, proto = "down", "down"
            if iface.name.startswith("Vlan") and not iface.shutdown:
                active = any(i.access_vlan == int(iface.name[4:]) and i.is_switchport
                             for i in self.device.interfaces.values())
                proto = "up" if active or iface.name == "Vlan1" else "down"
            ip = iface.ip or "unassigned"
            method = "manual" if iface.ip else "unset"
            lines.append(f"{iface.name:<23}{ip:<16}YES {method:<7}{status:<22}{proto}")
        return "\n".join(lines)

    def show_trunk(self, args, negate):
        trunks = [i for i in self.device.interfaces.values() if i.mode == "trunk"]
        if not trunks:
            return ""
        lines = ["Port        Mode         Encapsulation  Status        Native vlan"]
        for i in trunks:
            lines.append(f"{i.short:<12}on           802.1q         trunking      {i.native_vlan}")
        lines += ["", "Port        Vlans allowed on trunk"]
        for i in trunks:
            lines.append(f"{i.short:<12}{'1-4094' if i.trunk_allowed == 'all' else i.trunk_allowed}")
        return "\n".join(lines)

    def show_int_status(self, args, negate):
        lines = ["Port      Name               Status       Vlan       Duplex  Speed Type"]
        for i in self.device.interfaces.values():
            if not i.is_switchport:
                continue
            status = "disabled" if i.shutdown else "notconnect"
            vlan = "trunk" if i.mode == "trunk" else str(i.access_vlan)
            lines.append(f"{i.short:<10}{i.description[:18]:<19}{status:<13}{vlan:<11}auto    auto  10/100BaseTX")
        return "\n".join(lines)

    def show_ip_route(self, args, negate):
        lines = ["Codes: L - local, C - connected, S - static, O - OSPF", "",
                 "Gateway of last resort is " + (
                     next((r[2] for r in self.device.static_routes if r[0] == "0.0.0.0"), None) or "not set"), ""]
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            if i.ip and not i.shutdown:
                net = ipaddress.IPv4Network(f"{i.ip}/{i.mask}", strict=False)
                lines.append(f"C        {net} is directly connected, {i.name}")
                lines.append(f"L        {i.ip}/32 is directly connected, {i.name}")
        for net, mask, nh in self.device.static_routes:
            prefix = mask_to_prefix(mask)
            star = "*" if net == "0.0.0.0" else " "
            lines.append(f"S{star}       {net}/{prefix} [1/0] via {nh}")
        return "\n".join(lines)

    def show_ip_protocols(self, args, negate):
        if not self.device.ospf:
            return ""
        lines = []
        for pid, proc in self.device.ospf.items():
            lines.append(f'Routing Protocol is "ospf {pid}"')
            lines.append(f"  Router ID {proc.router_id or self._auto_router_id()}")
            lines.append("  Routing for Networks:")
            lines += [f"    {n} {w} area {a}" for n, w, a in proc.networks]
            if proc.passive:
                lines.append("  Passive Interface(s):")
                lines += [f"    {p}" for p in sorted(proc.passive)]
        return "\n".join(lines)

    def _auto_router_id(self) -> str:
        loopbacks = [i.ip for i in self.device.interfaces.values() if i.name.startswith("Loopback") and i.ip]
        ips = loopbacks or [i.ip for i in self.device.interfaces.values() if i.ip]
        return max(ips, key=lambda ip: ipaddress.IPv4Address(ip)) if ips else "0.0.0.0"

    def show_dhcp_pool(self, args, negate):
        lines = []
        for pool in self.device.dhcp_pools.values():
            lines += [f"Pool {pool.name} :", f" Network {pool.network} {pool.mask}",
                      f" Default router {pool.default_router}", f" DNS server {pool.dns_server}"]
        return "\n".join(lines)

    def show_acls(self, args, negate):
        lines = []
        for name, entries in self.device.acls.items():
            kind = "Extended" if (not name.isdigit() and entries and entries[0] == "__ext__") or (
                name.isdigit() and 100 <= int(name) <= 199) else "Standard"
            lines.append(f"{kind} IP access list {name}")
            seq = 10
            for entry in entries:
                if entry == "__ext__":
                    continue
                lines.append(f"    {seq} {entry}")
                seq += 10
        return "\n".join(lines)

    def show_port_security(self, args, negate):
        lines = ["Secure Port  MaxSecureAddr  CurrentAddr  SecurityViolation  Security Action"]
        for i in self.device.interfaces.values():
            if i.port_security:
                lines.append(f"{i.short:>11}{i.port_security_max:>15}{0:>13}{0:>19}  {i.port_security_violation.capitalize()}")
        return "\n".join(lines)

    def show_ssh(self, args, negate):
        if not self.device.rsa_modulus:
            return "SSH Disabled - version 1.99\n%Please create RSA keys to enable SSH."
        return f"SSH Enabled - version {self.device.ssh_version or '1.99'}"

    def show_version(self, args, negate):
        model = "WS-C2960-24TT-L" if self.device.kind == "switch" else "ISR4331/K9"
        return (f"Cisco IOS Software (simulateur TDM), Version 15.2\n"
                f"{self.device.hostname} uptime is 1 hour, 2 minutes\n"
                f"cisco {model} processor with 65536K bytes of memory.")

    # -- configuration globale -----------------------------------------------

    def cfg_hostname(self, args, negate):
        name = "Switch" if negate else args[0]
        if not re.match(r"^[A-Za-z][A-Za-z0-9_-]{0,62}$", name):
            raise CommandError("% Hostname contains one or more illegal characters.")
        self.device.hostname = name

    def cfg_enable_secret(self, args, negate):
        self.device.enable_secret = None if negate else _strip_level(args[0])

    def cfg_enable_password(self, args, negate):
        self.device.enable_password = None if negate else _strip_level(args[0])

    def cfg_service_pwd(self, args, negate):
        self.device.password_encryption = not negate

    def cfg_banner(self, args, negate):
        if negate:
            self.device.banner_motd = None
            return
        text = args[0]
        if len(text) >= 2 and text[0] == text[-1]:
            text = text[1:-1]
        elif text[:1] in "#^$%&":
            text = text[1:].rstrip(text[0])
        self.device.banner_motd = text

    def cfg_domain_name(self, args, negate):
        self.device.domain_name = None if negate else args[0]

    def cfg_domain_lookup(self, args, negate):
        self.device.domain_lookup = not negate

    def cfg_default_gw(self, args, negate):
        if not negate and not valid_ip(args[0]):
            raise CommandError(INVALID)
        self.device.default_gateway = None if negate else args[0]

    def cfg_ip_routing(self, args, negate):
        self.device.ip_routing = not negate

    def cfg_ip_route(self, args, negate):
        net, mask, nh = args
        if not (valid_ip(net) and valid_mask(mask)):
            raise CommandError(INVALID)
        if not valid_ip(nh):
            canonical = normalize_iface(nh)
            if not canonical or canonical not in self.device.interfaces:
                raise CommandError(INVALID)
            nh = canonical
        route = (net, mask, nh)
        if negate:
            self.device.static_routes = [r for r in self.device.static_routes if r != route]
        elif route not in self.device.static_routes:
            self.device.static_routes.append(route)

    def cfg_ssh_version(self, args, negate):
        if args[0] not in ("1", "2"):
            raise CommandError(INVALID)
        self.device.ssh_version = None if negate else int(args[0])

    def cfg_crypto(self, args, negate):
        match = re.search(r"modulus\s+(\d+)", args[0])
        if not match:
            return ("The name for the keys will be: "
                    f"{self.device.hostname}.{self.device.domain_name}\n"
                    "% Précise la taille : crypto key generate rsa general-keys modulus 1024")
        if not self.device.domain_name:
            return "% Please define a domain-name first."
        self.device.rsa_modulus = int(match.group(1))
        return (f"The name for the keys will be: {self.device.hostname}.{self.device.domain_name}\n"
                f"% The key modulus size is {self.device.rsa_modulus} bits\n"
                "% Generating RSA keys ...[OK]\n%SSH-5-ENABLED: SSH 1.99 has been enabled")

    def cfg_username(self, args, negate):
        name, rest = args
        if negate:
            self.device.users.pop(name, None)
            return
        words = rest.split()
        user = {"privilege": 1}
        i = 0
        while i < len(words):
            word = words[i].lower()
            if word == "privilege" and i + 1 < len(words):
                user["privilege"] = int(words[i + 1])
                i += 2
            elif word in ("secret", "password") and i + 1 < len(words):
                value = words[i + 1:]
                if value and value[0] in ("0", "5", "7") and len(value) > 1:
                    value = value[1:]
                user[word] = " ".join(value)
                break
            else:
                raise CommandError(INVALID)
        if "secret" not in user and "password" not in user:
            raise CommandError(INCOMPLETE)
        self.device.users[name] = user

    def cfg_dhcp_pool(self, args, negate):
        name = args[0]
        if negate:
            self.device.dhcp_pools.pop(name, None)
            return
        self.device.dhcp_pools.setdefault(name, DhcpPool(name))
        self.dhcp_pool = name
        self.mode = "dhcp"

    def cfg_dhcp_excluded(self, args, negate):
        start, end = args[0], args[1].strip() or ""
        if not valid_ip(start) or (end and not valid_ip(end)):
            raise CommandError(INVALID)
        entry = (start, end)
        if negate:
            self.device.dhcp_excluded = [e for e in self.device.dhcp_excluded if e != entry]
        elif entry not in self.device.dhcp_excluded:
            self.device.dhcp_excluded.append(entry)

    def cfg_named_acl_std(self, args, negate):
        self._named_acl(args[0], negate, extended=False)

    def cfg_named_acl_ext(self, args, negate):
        self._named_acl(args[0], negate, extended=True)

    def _named_acl(self, name, negate, extended):
        if negate:
            self.device.acls.pop(name, None)
            return
        self.device.acls.setdefault(name, ["__ext__"] if extended else [])
        self.acl_name = name
        self.mode = "acl-ext" if extended else "acl-std"

    def cfg_access_list(self, args, negate):
        number, rest = args
        if not number.isdigit():
            raise CommandError(INVALID)
        n = int(number)
        if not (1 <= n <= 199 or 1300 <= n <= 2699):
            raise CommandError(INVALID)
        if negate:
            self.device.acls.pop(number, None)
            return
        words = rest.split()
        if not words or words[0].lower() not in ("permit", "deny", "remark"):
            raise CommandError(INVALID)
        entry = _normalize_acl_entry(words)
        self.device.acls.setdefault(number, []).append(entry)

    def cfg_nat(self, args, negate):
        rule = "ip nat " + args[0]
        if negate:
            self.device.nat_rules = [r for r in self.device.nat_rules if r != rule]
        elif rule not in self.device.nat_rules:
            self.device.nat_rules.append(rule)

    def cfg_vlan(self, args, negate):
        try:
            ids = sorted(parse_vlan_list(args[0]))
        except ValueError:
            raise CommandError(INVALID) from None
        if self.device.kind != "switch" or not ids or any(not 1 <= v <= 4094 for v in ids):
            raise CommandError(INVALID)
        if negate:
            for vid in ids:
                if vid != 1:
                    self.device.vlans.pop(vid, None)
            return
        for vid in ids:
            self.device.vlans.setdefault(vid, default_vlan_name(vid))
        self._exit_to_config()
        self.vlan_ids = ids
        self.mode = "vlan"

    def cfg_interface(self, args, negate):
        text = args[0] + args[1].replace(" ", "")
        if "-" in text or "," in text:
            return self.cfg_interface_range([args[0] + " " + args[1]], negate)
        canonical = normalize_iface(text)
        if canonical is None:
            raise CommandError(INVALID)
        if canonical not in self.device.interfaces:
            base = canonical.split(".")[0]
            if "." in canonical and base in self.device.interfaces and self.device.kind == "router":
                self.device.interfaces[canonical] = Interface(canonical, shutdown=False)
            elif canonical.startswith("Vlan") and self.device.kind == "switch":
                vid = int(canonical[4:])
                if not 1 <= vid <= 4094:
                    raise CommandError(INVALID)
                self.device.interfaces[canonical] = Interface(canonical, shutdown=False)
            elif canonical.startswith("Loopback"):
                self.device.interfaces[canonical] = Interface(canonical, shutdown=False)
            else:
                raise CommandError(INVALID)
        if negate:
            if "." in canonical or canonical.startswith(("Loopback", "Vlan")):
                self.device.interfaces.pop(canonical, None)
            return
        self._exit_to_config()
        self.ifaces = [canonical]
        self.mode = "if"

    def cfg_interface_range(self, args, negate):
        names = expand_range(args[0])
        if not names or any(n not in self.device.interfaces for n in names):
            raise CommandError(INVALID)
        self._exit_to_config()
        self.ifaces = names
        self.mode = "if-range"

    def cfg_line_con(self, args, negate):
        self._exit_to_config()
        self.line_kind = "console"
        self.mode = "line"

    def cfg_line_vty(self, args, negate):
        if not (args[0].isdigit() and args[1].isdigit()):
            raise CommandError(INVALID)
        self._exit_to_config()
        self.line_kind = "vty"
        self.mode = "line"

    def cfg_router_ospf(self, args, negate):
        if not args[0].isdigit():
            raise CommandError(INVALID)
        pid = int(args[0])
        if negate:
            self.device.ospf.pop(pid, None)
            return
        self.device.ospf.setdefault(pid, OspfProcess(pid))
        self._exit_to_config()
        self.ospf_pid = pid
        self.mode = "router"

    def cfg_stp_mode(self, args, negate):
        mode = args[0].lower()
        if mode not in ("pvst", "rapid-pvst", "mst"):
            raise CommandError(INVALID)
        self.device.stp_mode = "pvst" if negate else mode

    def cfg_stp_priority(self, args, negate):
        vid, prio = args
        if not (vid.isdigit() and prio.isdigit()) or int(prio) % 4096:
            raise CommandError("% Bridge Priority must be in increments of 4096.")
        if negate:
            self.device.stp_priority.pop(int(vid), None)
        else:
            self.device.stp_priority[int(vid)] = int(prio)

    def cfg_stp_root(self, args, negate):
        vid, kind = args
        prio = {"primary": 24576, "secondary": 28672}.get(kind.lower())
        if prio is None or not vid.isdigit():
            raise CommandError(INVALID)
        self.device.stp_priority[int(vid)] = prio

    def cfg_vtp_mode(self, args, negate):
        mode = args[0].lower()
        if mode not in ("server", "client", "transparent", "off"):
            raise CommandError(INVALID)
        self.device.vtp_mode = "server" if negate else mode
        return f"Setting device to VTP {mode.upper()} mode."

    def cfg_vtp_domain(self, args, negate):
        self.device.vtp_domain = None if negate else args[0]

    # -- sous-modes ----------------------------------------------------------

    def _each_iface(self):
        return [self.device.interfaces[n] for n in self.ifaces]

    def _require_switchport(self):
        for iface in self._each_iface():
            if not iface.is_switchport:
                raise CommandError(INVALID)

    def if_description(self, args, negate):
        for i in self._each_iface():
            i.description = "" if negate else args[0]

    def if_shutdown(self, args, negate):
        for i in self._each_iface():
            i.shutdown = not negate
        if negate:
            return "\n".join(f"%LINK-5-CHANGED: Interface {i.name}, changed state to up" for i in self._each_iface())

    def if_sw_mode(self, args, negate):
        self._require_switchport()
        mode = args[0].lower()
        if "access".startswith(mode):
            mode = "access"
        elif "trunk".startswith(mode):
            mode = "trunk"
        elif mode.startswith("dyn"):
            mode = None
        else:
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.mode = None if negate else mode

    def _vlan_id(self, text: str) -> int:
        if not text.isdigit() or not 1 <= int(text) <= 4094:
            raise CommandError(INVALID)
        return int(text)

    def if_access_vlan(self, args, negate):
        self._require_switchport()
        vid = 1 if negate else self._vlan_id(args[0])
        message = None
        if vid not in self.device.vlans:
            self.device.vlans[vid] = default_vlan_name(vid)
            message = f"% Access VLAN does not exist. Creating vlan {vid}"
        for i in self._each_iface():
            i.access_vlan = vid
        return message

    def if_voice_vlan(self, args, negate):
        self._require_switchport()
        for i in self._each_iface():
            i.voice_vlan = None if negate else self._vlan_id(args[0])

    def if_trunk_allowed(self, args, negate):
        self._require_switchport()
        text = args[0].strip().lower()
        for i in self._each_iface():
            if negate or text == "all":
                i.trunk_allowed = "all"
                continue
            words = text.split()
            try:
                if words[0] == "add":
                    current = i.allowed_vlans()
                    if current is not None:
                        i.trunk_allowed = format_vlan_list(current | parse_vlan_list(words[1]))
                elif words[0] == "remove":
                    current = i.allowed_vlans()
                    current = set(range(1, 4095)) if current is None else current
                    i.trunk_allowed = format_vlan_list(current - parse_vlan_list(words[1]))
                elif words[0] == "except":
                    i.trunk_allowed = format_vlan_list(set(range(1, 4095)) - parse_vlan_list(words[1]))
                elif words[0] == "none":
                    i.trunk_allowed = "none"
                else:
                    i.trunk_allowed = format_vlan_list(parse_vlan_list("".join(words)))
            except (ValueError, IndexError):
                raise CommandError(INVALID) from None

    def if_native(self, args, negate):
        self._require_switchport()
        for i in self._each_iface():
            i.native_vlan = 1 if negate else self._vlan_id(args[0])

    def if_port_security(self, args, negate):
        self._require_switchport()
        for i in self._each_iface():
            if not negate and i.mode != "access":
                raise CommandError("Command rejected: " + i.name + " is a dynamic port.")
            i.port_security = not negate

    def if_ps_max(self, args, negate):
        self._require_switchport()
        for i in self._each_iface():
            i.port_security_max = 1 if negate else int(args[0])

    def if_ps_violation(self, args, negate):
        self._require_switchport()
        mode = args[0].lower()
        choices = [c for c in ("protect", "restrict", "shutdown") if c.startswith(mode)]
        if len(choices) != 1:
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.port_security_violation = "shutdown" if negate else choices[0]

    def if_ps_sticky(self, args, negate):
        self._require_switchport()
        for i in self._each_iface():
            i.port_security_sticky = not negate

    def if_portfast(self, args, negate):
        for i in self._each_iface():
            i.portfast = not negate

    def if_bpduguard(self, args, negate):
        for i in self._each_iface():
            i.bpduguard = not negate

    def if_ip(self, args, negate):
        ip, mask, rest = args
        if not negate and not (valid_ip(ip) and valid_mask(mask)):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if i.is_switchport:
                raise CommandError(INVALID)
            if rest.strip().lower().startswith("sec"):
                if negate:
                    i.secondary = [s for s in i.secondary if s != (ip, mask)]
                else:
                    i.secondary.append((ip, mask))
            elif negate:
                i.ip = i.mask = None
            else:
                i.ip, i.mask = ip, mask

    def if_ip_dhcp(self, args, negate):
        for i in self._each_iface():
            i.ip = None if negate else "dhcp"
            i.mask = None

    def if_helper(self, args, negate):
        for i in self._each_iface():
            if negate:
                i.helper_addresses = [h for h in i.helper_addresses if h != args[0]]
            elif args[0] not in i.helper_addresses:
                i.helper_addresses.append(args[0])

    def if_access_group(self, args, negate):
        acl, direction = args
        if direction.lower() not in ("in", "out"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if negate:
                i.access_groups.pop(direction.lower(), None)
            else:
                i.access_groups[direction.lower()] = acl

    def if_nat(self, args, negate):
        direction = args[0].lower()
        if direction not in ("inside", "outside"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.nat = None if negate else direction

    def if_encapsulation(self, args, negate):
        for i in self._each_iface():
            if "." not in i.name:
                raise CommandError("% Configuring IEEE 802.1Q encapsulation on the main interface is not permitted.")
            i.encapsulation_vlan = None if negate else self._vlan_id(args[0])

    def if_clock_rate(self, args, negate):
        for i in self._each_iface():
            if not i.name.startswith("Serial"):
                raise CommandError(INVALID)
            i.clock_rate = None if negate else int(args[0])

    def if_channel_group(self, args, negate):
        for i in self._each_iface():
            i.channel_group = None if negate else int(args[0])

    def vlan_name_cmd(self, args, negate):
        for vid in self.vlan_ids:
            self.device.vlans[vid] = default_vlan_name(vid) if negate else args[0]

    def _line(self) -> Line:
        return self.device.lines[self.line_kind]

    def line_password(self, args, negate):
        self._line().password = None if negate else _strip_level(args[0])

    def line_login(self, args, negate):
        self._line().login = None if negate else "login"

    def line_login_local(self, args, negate):
        self._line().login = None if negate else "local"

    def line_transport(self, args, negate):
        value = args[0].strip().lower()
        if not negate and value not in ("ssh", "telnet", "telnet ssh", "ssh telnet", "all", "none"):
            raise CommandError(INVALID)
        self._line().transport_input = None if negate else value

    def line_exec_timeout(self, args, negate):
        self._line().exec_timeout = None if negate else args[0]

    def line_logging_sync(self, args, negate):
        self._line().logging_synchronous = not negate

    def _ospf(self) -> OspfProcess:
        return self.device.ospf[self.ospf_pid]

    def ospf_network(self, args, negate):
        net, wild, area = args
        if not (valid_ip(net) and valid_ip(wild)):
            raise CommandError(INVALID)
        entry = (net, wild, area)
        proc = self._ospf()
        if negate:
            proc.networks = [n for n in proc.networks if n != entry]
        elif entry not in proc.networks:
            proc.networks.append(entry)

    def ospf_router_id(self, args, negate):
        if not negate and not valid_ip(args[0]):
            raise CommandError(INVALID)
        self._ospf().router_id = None if negate else args[0]

    def ospf_passive(self, args, negate):
        canonical = normalize_iface(args[0]) if args[0].lower() != "default" else None
        if canonical is None or canonical not in self.device.interfaces:
            raise CommandError(INVALID)
        if negate:
            self._ospf().passive.discard(canonical)
        else:
            self._ospf().passive.add(canonical)

    def ospf_default(self, args, negate):
        self._ospf().default_originate = not negate

    def _pool(self) -> DhcpPool:
        return self.device.dhcp_pools[self.dhcp_pool]

    def dhcp_network(self, args, negate):
        if not negate and not (valid_ip(args[0]) and valid_mask(args[1])):
            raise CommandError(INVALID)
        pool = self._pool()
        pool.network, pool.mask = (None, None) if negate else (args[0], args[1])

    def dhcp_router(self, args, negate):
        self._pool().default_router = None if negate else args[0]

    def dhcp_dns(self, args, negate):
        self._pool().dns_server = None if negate else args[0]

    def dhcp_domain(self, args, negate):
        self._pool().domain_name = None if negate else args[0]

    def acl_entry(self, action, args, negate):
        entry = _normalize_acl_entry([action] + args[0].split())
        entries = self.device.acls[self.acl_name]
        if negate:
            if entry in entries:
                entries.remove(entry)
        else:
            entries.append(entry)


def _strip_level(text: str) -> str:
    words = text.split()
    if len(words) > 1 and words[0] in ("0", "5", "7"):
        words = words[1:]
    return " ".join(words)


def _normalize_acl_entry(words: list[str]) -> str:
    return " ".join(w.lower() if w.lower() in ("permit", "deny", "host", "any", "ip", "tcp", "udp", "icmp", "eq",
                                                 "remark", "log") else w for w in words)


def expand_range(text: str) -> list[str]:
    """``fa0/1 - 5, fa0/10`` -> [FastEthernet0/1, ..., FastEthernet0/5, FastEthernet0/10]."""
    names: list[str] = []
    for part in text.split(","):
        part = part.replace(" ", "")
        if not part:
            continue
        match = re.match(r"^([A-Za-z]+)([\d/]+/)(\d+)(?:-(\d+))?$", part)
        if not match:
            return []
        prefix, base, start, end = match.groups()
        canonical = normalize_iface(prefix + base + start)
        if canonical is None:
            return []
        kind = canonical[: len(canonical) - len(base + start)]
        for n in range(int(start), int(end or start) + 1):
            names.append(f"{kind}{base}{n}")
    return names


def apply_commands(device: Device, commands: str | list[str]) -> Session:
    """Applique une suite de commandes (depuis le mode privilégié) et renvoie la session."""
    session = Session(device)
    session.mode = "exec"
    lines = commands.splitlines() if isinstance(commands, str) else commands
    for line in lines:
        output = session.execute(line)
        if output.startswith("%") and "Creating vlan" not in output and "SSH" not in output:
            raise ValueError(f"commande refusée : {line!r} -> {output}")
    return session
