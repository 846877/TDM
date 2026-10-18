"""Simulateur simplifié de CLI Cisco IOS (switch et routeur).

L'objectif n'est pas d'émuler IOS à 100 %, mais de reproduire les commandes et les
modes qu'on pratique dans les TP réseaux (VLAN, trunks, EtherChannel, VTP, STP,
adressage IPv4/IPv6, routage statique et flottant, OSPF, EIGRP, RIP, HSRP, DHCP et
DHCP snooping, ACL, NAT, SSH/AAA, NTP, syslog, SNMP...) afin qu'une moulinette puisse
vérifier la configuration obtenue. Les abréviations IOS (``conf t``, ``int fa0/1``,
``sh vlan br``...) et les filtres ``| include`` / ``| section`` sont acceptés.
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
    "port-channel": "Port-channel",
}
IFACE_SHORT = {"FastEthernet": "Fa", "GigabitEthernet": "Gi", "Serial": "Se", "Vlan": "Vlan", "Loopback": "Lo",
               "Port-channel": "Po"}
IFACE_KIND = re.compile(r"[A-Za-z-]+")

CHANNEL_PROTOCOLS = {"active": "lacp", "passive": "lacp", "desirable": "pagp", "auto": "pagp", "on": None}
LOG_LEVELS = ["emergencies", "alerts", "critical", "errors", "warnings", "notifications", "informational",
              "debugging"]


@dataclass
class HsrpGroup:
    group: int
    ip: str | None = None
    priority: int = 100
    preempt: bool = False


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
    nonegotiate: bool = False
    ip: str | None = None
    mask: str | None = None
    secondary: list[tuple[str, str]] = field(default_factory=list)
    encapsulation_vlan: int | None = None
    access_groups: dict[str, str] = field(default_factory=dict)  # "in"/"out" -> acl
    portfast: bool = False
    bpduguard: bool = False
    stp_guard: str | None = None  # "root" / "loop"
    stp_cost: int | None = None
    stp_port_priority: int | None = None
    port_security: bool = False
    port_security_max: int = 1
    port_security_violation: str = "shutdown"
    port_security_sticky: bool = False
    nat: str | None = None  # "inside" / "outside"
    helper_addresses: list[str] = field(default_factory=list)
    clock_rate: int | None = None
    bandwidth: int | None = None
    speed: str = "auto"
    duplex: str = "auto"
    channel_group: int | None = None
    channel_mode: str | None = None  # active, passive, desirable, auto, on
    channel_protocol: str | None = None  # lacp / pagp
    ospf_cost: int | None = None
    ospf_priority: int | None = None
    ospf_area: tuple[int, str] | None = None  # (processus, zone) via « ip ospf 1 area 0 »
    standby: dict[int, HsrpGroup] = field(default_factory=dict)
    standby_version: int = 1
    ipv6_enabled: bool = False
    ipv6_addresses: list[str] = field(default_factory=list)  # « 2001:db8::1/64 », « 2001:db8::/64 eui-64 »
    ipv6_link_local: str | None = None
    dhcp_snooping_trust: bool = False
    dhcp_snooping_rate: int | None = None
    arp_inspection_trust: bool = False
    storm_control: dict[str, str] = field(default_factory=dict)  # "broadcast" -> "20.00", "action" -> "shutdown"
    cdp_enabled: bool = True
    lldp_transmit: bool = True
    lldp_receive: bool = True

    @property
    def short(self) -> str:
        kind = IFACE_KIND.match(self.name).group(0)
        return IFACE_SHORT.get(kind, kind) + self.name[len(kind):]

    @property
    def is_physical(self) -> bool:
        return not self.name.startswith(("Vlan", "Loopback", "Port-channel")) and "." not in self.name

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

    def has_ipv6(self, address: str) -> bool:
        """``has_ipv6("2001:DB8:ACAD:10::1/64")`` : comparaison insensible à l'écriture de l'adresse."""
        try:
            wanted = normalize_ipv6_address(address)
        except ValueError:
            return False
        return wanted in self.ipv6_addresses or wanted == self.ipv6_link_local


@dataclass
class Line:
    password: str | None = None
    login: str | None = None  # None, "login" ou "local"
    login_authentication: str | None = None  # liste AAA (« login authentication default »)
    transport_input: str | None = None
    exec_timeout: str | None = None
    logging_synchronous: bool = False
    access_class: dict[str, str] = field(default_factory=dict)  # "in"/"out" -> acl


@dataclass
class DhcpPool:
    name: str
    network: str | None = None
    mask: str | None = None
    default_router: str | None = None
    dns_server: str | None = None  # tel que tapé (une ou plusieurs adresses séparées par des espaces)
    domain_name: str | None = None
    lease: str | None = None

    @property
    def dns_servers(self) -> list[str]:
        return self.dns_server.split() if self.dns_server else []


@dataclass(kw_only=True)
class RoutingProcess:
    """Ce que partagent OSPF, EIGRP et RIP : interfaces passives, redistribution, route par défaut."""

    passive: set[str] = field(default_factory=set)
    passive_default: bool = False
    no_passive: set[str] = field(default_factory=set)  # « no passive-interface X » après « ... default »
    default_originate: bool = False
    redistribute: list[str] = field(default_factory=list)

    def is_passive(self, name: str) -> bool:
        canonical = normalize_iface(name) or name
        if self.passive_default:
            return canonical not in self.no_passive
        return canonical in self.passive

    def passive_lines(self) -> list[str]:
        if self.passive_default:
            return [" passive-interface default"] + [f" no passive-interface {n}" for n in sorted(self.no_passive)]
        return [f" passive-interface {n}" for n in sorted(self.passive)]


@dataclass
class OspfProcess(RoutingProcess):
    pid: int
    router_id: str | None = None
    networks: list[tuple[str, str, str]] = field(default_factory=list)  # (réseau, wildcard, zone)
    default_originate_always: bool = False
    reference_bandwidth: int | None = None
    area_types: dict[str, str] = field(default_factory=dict)  # zone -> "stub", "stub no-summary", "nssa"


@dataclass
class EigrpProcess(RoutingProcess):
    asn: int
    router_id: str | None = None
    networks: list[tuple[str, str | None]] = field(default_factory=list)  # (réseau, wildcard ou None)
    auto_summary: bool = True


@dataclass
class RipProcess(RoutingProcess):
    version: int = 1
    networks: list[str] = field(default_factory=list)  # réseaux par classe, comme IOS les enregistre
    auto_summary: bool = True


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
        self.route_distances: dict[tuple[str, str, str], int] = {}  # routes flottantes (distance ≠ 1)
        self.ospf: dict[int, OspfProcess] = {}
        self.eigrp: dict[int, EigrpProcess] = {}
        self.rip: RipProcess | None = None
        self.ipv6_routing = False
        self.ipv6_routes: list[tuple[str, str, int]] = []  # (préfixe, saut suivant, distance)
        self.dhcp_pools: dict[str, DhcpPool] = {}
        self.dhcp_excluded: list[tuple[str, str]] = []
        self.dhcp_snooping = False
        self.dhcp_snooping_vlans: set[int] = set()
        self.dhcp_snooping_option82 = True
        self.arp_inspection_vlans: set[int] = set()
        self.acls: dict[str, list[str]] = {}
        self.acl_sequences: dict[str, list[int]] = {}
        self.nat_rules: list[str] = []
        self.vtp_mode = "server"
        self.vtp_domain: str | None = None
        self.vtp_version = 1
        self.vtp_password: str | None = None
        self.stp_mode = "pvst"
        self.stp_priority: dict[int, int] = {}
        self.stp_portfast_default = False
        self.stp_bpduguard_default = False
        self.errdisable_recovery: set[str] = set()
        self.errdisable_interval: int | None = None
        self.name_servers: list[str] = []
        self.ntp_servers: list[str] = []
        self.ntp_master: int | None = None
        self.clock_timezone: tuple[str, int] | None = None
        self.logging_hosts: list[str] = []
        self.logging_trap: str | None = None
        self.logging_buffered: str | None = None
        self.snmp_communities: dict[str, tuple[str, str | None]] = {}  # nom -> ("RO"/"RW", acl)
        self.snmp_location: str | None = None
        self.snmp_contact: str | None = None
        self.snmp_hosts: list[str] = []
        self.aaa_new_model = False
        self.aaa_authentication: dict[str, str] = {}  # liste -> méthodes (« login default » -> « local »)
        self.min_password_length: int | None = None
        self.login_block: tuple[int, int, int] | None = None  # (durée, tentatives, fenêtre)
        self.ssh_timeout: int | None = None
        self.ssh_retries: int | None = None
        self.http_server = True
        self.https_server = True
        self.cdp_run = True
        self.lldp_run = False
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

    def has_route(self, network: str, mask: str, next_hop: str | None = None, distance: int | None = None) -> bool:
        return any(r[0] == network and r[1] == mask and (next_hop is None or r[2] == _canonical_hop(next_hop))
                   and (distance is None or self.route_distances.get(r, 1) == distance)
                   for r in self.static_routes)

    def has_route6(self, prefix: str, next_hop: str | None = None, distance: int | None = None) -> bool:
        try:
            wanted = normalize_ipv6_prefix(prefix)
        except ValueError:
            return False
        hop = _canonical_hop(next_hop) if next_hop else None
        return any(p == wanted and (hop is None or nh == hop) and (distance is None or dist == distance)
                   for p, nh, dist in self.ipv6_routes)

    def ospf_has_network(self, network: str, wildcard: str, area: str | int) -> bool:
        return any((network, wildcard, str(area)) in p.networks for p in self.ospf.values())

    def eigrp_has_network(self, asn: int, network: str, wildcard: str | None = None) -> bool:
        proc = self.eigrp.get(int(asn))
        return proc is not None and any(n == network and (wildcard is None or w == wildcard)
                                        for n, w in proc.networks)

    def rip_has_network(self, network: str) -> bool:
        return self.rip is not None and classful_network(network) in self.rip.networks

    def has_nat(self, rule: str) -> bool:
        """``has_nat("ip nat inside source list 1 interface g0/1 overload")`` (abréviations acceptées)."""
        return normalize_nat_rule(rule) in self.nat_rules

    def channel_members(self, group: int) -> list[str]:
        return [i.short for i in self.interfaces.values() if i.channel_group == group]

    @property
    def saved(self) -> bool:
        return self.startup_config is not None and self.startup_config == self.running_config()

    # -- génération de la configuration --------------------------------------

    def running_config(self) -> str:
        out = ["!", "version 15.2", "no service pad", "service timestamps debug datetime msec",
               "service timestamps log datetime msec"]
        out.append("service password-encryption" if self.password_encryption else "no service password-encryption")
        out += ["!", f"hostname {self.hostname}", "!"]
        if self.logging_buffered:
            out.append(f"logging buffered {self.logging_buffered}")
        if self.enable_secret:
            out.append(f"enable secret 5 {_fake_hash(self.enable_secret)}")
        if self.enable_password:
            pwd = _type7(self.enable_password) if self.password_encryption else self.enable_password
            out.append(f"enable password {'7 ' if self.password_encryption else ''}{pwd}")
        if self.aaa_new_model:
            out += ["!", "aaa new-model"]
            out += [f"aaa authentication {key} {methods}" for key, methods in self.aaa_authentication.items()]
        if self.clock_timezone:
            out.append(f"clock timezone {self.clock_timezone[0]} {self.clock_timezone[1]}")
        if self.min_password_length:
            out.append(f"security passwords min-length {self.min_password_length}")
        for name, user in self.users.items():
            if user.get("secret"):
                out.append(f"username {name} privilege {user.get('privilege', 1)} secret 5 {_fake_hash(user['secret'])}")
            else:
                out.append(f"username {name} privilege {user.get('privilege', 1)} password {user.get('password', '')}")
        out.append("!")
        if self.login_block:
            out.append("login block-for {} attempts {} within {}".format(*self.login_block))
        if not self.domain_lookup:
            out.append("no ip domain-lookup")
        if self.domain_name:
            out.append(f"ip domain-name {self.domain_name}")
        if self.name_servers:
            out.append("ip name-server " + " ".join(self.name_servers))
        if self.ssh_version:
            out.append(f"ip ssh version {self.ssh_version}")
        if self.ssh_timeout:
            out.append(f"ip ssh time-out {self.ssh_timeout}")
        if self.ssh_retries:
            out.append(f"ip ssh authentication-retries {self.ssh_retries}")
        if self.kind == "switch" and self.ip_routing:
            out.append("ip routing")
        if self.ipv6_routing:
            out.append("ipv6 unicast-routing")
        if self.dhcp_snooping_vlans:
            out.append(f"ip dhcp snooping vlan {format_vlan_list(self.dhcp_snooping_vlans)}")
        if not self.dhcp_snooping_option82:
            out.append("no ip dhcp snooping information option")
        if self.dhcp_snooping:
            out.append("ip dhcp snooping")
        if self.arp_inspection_vlans:
            out.append(f"ip arp inspection vlan {format_vlan_list(self.arp_inspection_vlans)}")
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
            if pool.lease:
                out.append(f" lease {pool.lease}")
        if self.errdisable_recovery or self.errdisable_interval:
            out.append("!")
            out += [f"errdisable recovery cause {cause}" for cause in sorted(self.errdisable_recovery)]
            if self.errdisable_interval:
                out.append(f"errdisable recovery interval {self.errdisable_interval}")
        if self.kind == "switch":
            out += ["!", f"spanning-tree mode {self.stp_mode}"]
            if self.stp_portfast_default:
                out.append("spanning-tree portfast default")
            if self.stp_bpduguard_default:
                out.append("spanning-tree portfast bpduguard default")
            for vlan, prio in sorted(self.stp_priority.items()):
                out.append(f"spanning-tree vlan {vlan} priority {prio}")
            if self.vtp_mode != "server":
                out.append(f"vtp mode {self.vtp_mode}")
            if self.vtp_domain:
                out.append(f"vtp domain {self.vtp_domain}")
            if self.vtp_version != 1:
                out.append(f"vtp version {self.vtp_version}")
            if self.vtp_password:
                out.append(f"vtp password {self.vtp_password}")
        out.append("!")
        for vid, name in sorted(self.vlans.items()):
            if vid == 1:
                continue
            out.append(f"vlan {vid}")
            if name != default_vlan_name(vid):
                out.append(f" name {name}")
            out.append("!")
        if not self.cdp_run:
            out += ["no cdp run", "!"]
        if self.lldp_run:
            out += ["lldp run", "!"]
        for iface in sorted(self.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            out.append(f"interface {iface.name}")
            out += [" " + line for line in self._iface_lines(iface)]
            out.append("!")
        if self.default_gateway:
            out.append(f"ip default-gateway {self.default_gateway}")
        out += self._routing_lines()
        out.append("ip http server" if self.http_server else "no ip http server")
        out.append("ip http secure-server" if self.https_server else "no ip http secure-server")
        out.append("!")
        for rule in self.nat_rules:
            out.append(rule)
        for route in self.static_routes:
            distance = self.route_distances.get(route)
            out.append("ip route {} {} {}".format(*route) + (f" {distance}" if distance else ""))
        for prefix, nh, distance in self.ipv6_routes:
            out.append(f"ipv6 route {prefix.upper()} {nh.upper() if ':' in nh else nh}"
                       + (f" {distance}" if distance != 1 else ""))
        out.append("!")
        for name, entries in self.acls.items():
            real = [e for e in entries if e != "__ext__"]
            if name.isdigit():
                out += [f"access-list {name} {entry}" for entry in real]
            else:
                kind = "extended" if entries and entries[0].startswith("__ext__") else "standard"
                out.append(f"ip access-list {kind} {name}")
                out += [f" {seq} {e}" for seq, e in zip(self.acl_seqs(name), real)]
        if self.logging_trap:
            out.append(f"logging trap {self.logging_trap}")
        out += [f"logging host {host}" for host in self.logging_hosts]
        if self.snmp_communities or self.snmp_location or self.snmp_contact or self.snmp_hosts:
            out.append("!")
            for name, (mode, acl) in self.snmp_communities.items():
                out.append(f"snmp-server community {name} {mode}{' ' + acl if acl else ''}")
            if self.snmp_location:
                out.append(f"snmp-server location {self.snmp_location}")
            if self.snmp_contact:
                out.append(f"snmp-server contact {self.snmp_contact}")
            out += [f"snmp-server host {host}" for host in self.snmp_hosts]
        if self.banner_motd:
            out += ["!", f"banner motd ^C{self.banner_motd}^C"]
        out.append("!")
        for kind, label in (("console", "line con 0"), ("vty", "line vty 0 4" if self.kind == "router" else "line vty 0 15")):
            out.append(label)
            out += self._line_lines(self.lines[kind])
        if self.ntp_master:
            out += ["!", f"ntp master {self.ntp_master}"]
        if self.ntp_servers:
            out += ["!"] + [f"ntp server {server}" for server in self.ntp_servers]
        out += ["!", "end"]
        return "\n".join(out)

    def _routing_lines(self) -> list[str]:
        out = []
        for asn, proc in sorted(self.eigrp.items()):
            out.append(f"router eigrp {asn}")
            if proc.router_id:
                out.append(f" eigrp router-id {proc.router_id}")
            out += proc.passive_lines()
            out += [f" network {net}{' ' + wild if wild else ''}" for net, wild in proc.networks]
            out += [f" redistribute {r}" for r in proc.redistribute]
            if not proc.auto_summary:
                out.append(" no auto-summary")
            out.append("!")
        for pid, proc in sorted(self.ospf.items()):
            out.append(f"router ospf {pid}")
            if proc.router_id:
                out.append(f" router-id {proc.router_id}")
            if proc.reference_bandwidth:
                out.append(f" auto-cost reference-bandwidth {proc.reference_bandwidth}")
            out += [f" area {area} {kind}" for area, kind in proc.area_types.items()]
            out += [f" redistribute {r}" for r in proc.redistribute]
            out += proc.passive_lines()
            out += [f" network {net} {wild} area {area}" for net, wild, area in proc.networks]
            if proc.default_originate:
                out.append(" default-information originate" + (" always" if proc.default_originate_always else ""))
            out.append("!")
        if self.rip:
            out.append("router rip")
            if self.rip.version != 1:
                out.append(f" version {self.rip.version}")
            out += self.rip.passive_lines()
            out += [f" network {net}" for net in self.rip.networks]
            out += [f" redistribute {r}" for r in self.rip.redistribute]
            if self.rip.default_originate:
                out.append(" default-information originate")
            if not self.rip.auto_summary:
                out.append(" no auto-summary")
            out.append("!")
        return out

    def _line_lines(self, line: Line) -> list[str]:
        out = [f" access-class {acl} {direction}" for direction, acl in sorted(line.access_class.items())]
        if line.exec_timeout:
            out.append(f" exec-timeout {line.exec_timeout}")
        if line.password:
            pwd = _type7(line.password) if self.password_encryption else line.password
            out.append(f" password {'7 ' if self.password_encryption else ''}{pwd}")
        if line.logging_synchronous:
            out.append(" logging synchronous")
        if line.login_authentication:
            out.append(f" login authentication {line.login_authentication}")
        if line.login == "local":
            out.append(" login local")
        elif line.login == "login":
            out.append(" login")
        if line.transport_input:
            out.append(f" transport input {line.transport_input}")
        return out

    def acl_seqs(self, name: str) -> list[int]:
        """Numéros de séquence des entrées d'une ACL (10, 20, 30... sauf insertion explicite)."""
        real = [e for e in self.acls.get(name, []) if e != "__ext__"]
        seqs = self.acl_sequences.get(name, [])
        if len(seqs) != len(real):
            seqs = [10 * (i + 1) for i in range(len(real))]
            self.acl_sequences[name] = seqs
        return seqs

    def _iface_lines(self, iface: Interface) -> list[str]:
        lines = []
        if iface.description:
            lines.append(f"description {iface.description}")
        if iface.bandwidth:
            lines.append(f"bandwidth {iface.bandwidth}")
        if iface.encapsulation_vlan is not None:
            lines.append(f"encapsulation dot1Q {iface.encapsulation_vlan}")
        if self.kind == "switch" and not iface.is_switchport and (
                iface.is_physical or iface.name.startswith("Port-channel")):
            lines.append("no switchport")
        if iface.is_switchport:
            lines += self._switchport_lines(iface)
        if iface.ip:
            lines.append(f"ip address {iface.ip} {iface.mask}" if iface.mask else f"ip address {iface.ip}")
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
        if iface.ospf_area:
            lines.append(f"ip ospf {iface.ospf_area[0]} area {iface.ospf_area[1]}")
        if iface.ospf_cost:
            lines.append(f"ip ospf cost {iface.ospf_cost}")
        if iface.ospf_priority is not None:
            lines.append(f"ip ospf priority {iface.ospf_priority}")
        if iface.dhcp_snooping_trust:
            lines.append("ip dhcp snooping trust")
        if iface.dhcp_snooping_rate:
            lines.append(f"ip dhcp snooping limit rate {iface.dhcp_snooping_rate}")
        if iface.arp_inspection_trust:
            lines.append("ip arp inspection trust")
        if iface.ipv6_link_local:
            lines.append(f"ipv6 address {iface.ipv6_link_local.upper()} link-local")
        for address in iface.ipv6_addresses:
            lines.append(f"ipv6 address {address.upper().replace(' EUI-64', ' eui-64')}")
        if iface.ipv6_enabled:
            lines.append("ipv6 enable")
        if iface.standby_version != 1:
            lines.append(f"standby version {iface.standby_version}")
        for group in sorted(iface.standby.values(), key=lambda g: g.group):
            if group.ip:
                lines.append(f"standby {group.group} ip {group.ip}")
            if group.priority != 100:
                lines.append(f"standby {group.group} priority {group.priority}")
            if group.preempt:
                lines.append(f"standby {group.group} preempt")
        for kind, value in sorted(iface.storm_control.items()):
            lines.append(f"storm-control {kind} {value}" if kind == "action" else f"storm-control {kind} level {value}")
        if iface.clock_rate:
            lines.append(f"clock rate {iface.clock_rate}")
        if iface.speed != "auto":
            lines.append(f"speed {iface.speed}")
        if iface.duplex != "auto":
            lines.append(f"duplex {iface.duplex}")
        if iface.channel_group:
            if iface.channel_protocol:
                lines.append(f"channel-protocol {iface.channel_protocol}")
            lines.append(f"channel-group {iface.channel_group} mode {iface.channel_mode or 'on'}")
        if not iface.cdp_enabled:
            lines.append("no cdp enable")
        if not iface.lldp_transmit:
            lines.append("no lldp transmit")
        if not iface.lldp_receive:
            lines.append("no lldp receive")
        if iface.portfast:
            lines.append("spanning-tree portfast")
        if iface.bpduguard:
            lines.append("spanning-tree bpduguard enable")
        if iface.stp_guard:
            lines.append(f"spanning-tree guard {iface.stp_guard}")
        if iface.stp_cost:
            lines.append(f"spanning-tree cost {iface.stp_cost}")
        if iface.stp_port_priority is not None:
            lines.append(f"spanning-tree port-priority {iface.stp_port_priority}")
        if iface.shutdown:
            lines.append("shutdown")
        return lines

    @staticmethod
    def _switchport_lines(iface: Interface) -> list[str]:
        lines = []
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
        if iface.nonegotiate:
            lines.append("switchport nonegotiate")
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
        return lines


def default_vlan_name(vid: int) -> str:
    return "default" if vid == 1 else f"VLAN{vid:04d}"


def _fake_hash(secret: str) -> str:
    import hashlib

    return "$1$" + hashlib.md5(secret.encode()).hexdigest()[:4] + "$" + hashlib.md5(secret[::-1].encode()).hexdigest()[:22]


def _type7(password: str) -> str:
    return "".join(f"{(ord(c) ^ 0x5A):02X}" for c in password)[:24].rjust(4, "0")


def iface_sort_key(name: str):
    order = ["FastEthernet", "GigabitEthernet", "Serial", "Port-channel", "Loopback", "Vlan"]
    kind = IFACE_KIND.match(name).group(0)
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
    """``fa0/1`` -> ``FastEthernet0/1``, ``g0/0.10`` -> ``GigabitEthernet0/0.10``, ``vlan 10`` -> ``Vlan10``,
    ``po1`` -> ``Port-channel1``."""
    text = text.replace(" ", "")
    match = re.match(r"^([A-Za-z-]+)([\d/.]+)$", text)
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


def classful_network(ip: str) -> str:
    """Réseau par classe, comme ``network`` de RIP l'enregistre : 10.1.2.0 -> 10.0.0.0."""
    octets = ip.split(".")
    first = int(octets[0])
    keep = 1 if first < 128 else 2 if first < 192 else 3
    return ".".join(octets[:keep] + ["0"] * (4 - keep))


def normalize_ipv6_address(text: str) -> str:
    """``2001:DB8:ACAD:10::1/64`` -> ``2001:db8:acad:10::1/64`` ; ``FE80::1`` -> ``fe80::1`` ;
    ``2001:db8::/64 eui-64`` -> ``2001:db8::/64 eui-64``. Lève ValueError si l'adresse est invalide."""
    words = text.split()
    if len(words) == 2 and words[1].lower() == "eui-64":
        return f"{ipaddress.IPv6Network(words[0], strict=False)} eui-64"
    if len(words) != 1:
        raise ValueError(text)
    if "/" in words[0]:
        return str(ipaddress.IPv6Interface(words[0]))
    return str(ipaddress.IPv6Address(words[0]))


def normalize_ipv6_prefix(text: str) -> str:
    return str(ipaddress.IPv6Network(text, strict=False))


def valid_ipv6(text: str) -> bool:
    try:
        ipaddress.IPv6Address(text)
    except ValueError:
        return False
    return True


def _canonical_hop(text: str) -> str:
    """Saut suivant d'une route : adresse IPv4/IPv6 normalisée ou nom d'interface complet
    (``g0/1 203.0.113.1`` -> ``GigabitEthernet0/1 203.0.113.1``)."""
    words = []
    for word in text.split():
        if valid_ipv6(word):
            words.append(str(ipaddress.IPv6Address(word)))
        elif valid_ip(word):
            words.append(word)
        else:
            words.append(normalize_iface(word) or word)
    return " ".join(words)


NAT_KEYWORDS = {"ip", "nat", "inside", "outside", "source", "destination", "list", "pool", "interface", "overload",
                "static", "tcp", "udp", "netmask", "prefix-length", "extendable"}


def normalize_nat_rule(text: str) -> str:
    """Forme canonique d'une règle NAT : mots-clés en minuscules, interface en toutes lettres."""
    words = text.split()
    out = []
    for i, word in enumerate(words):
        low = word.lower()
        if i > 0 and words[i - 1].lower() == "interface":
            out.append(normalize_iface(word) or word)
        elif low in NAT_KEYWORDS:
            out.append(low)
        else:
            out.append(word)
    if out[:2] != ["ip", "nat"]:
        out = ["ip", "nat"] + out
    return " ".join(out)


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
                            and r.pattern[position] != "<rest>"
                            and (r.pattern[position] != "<seq>" or token.isdigit())]
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
    "router-eigrp": "{h}(config-router)#",
    "router-rip": "{h}(config-router)#",
    "dhcp": "{h}(dhcp-config)#",
    "acl-std": "{h}(config-std-nacl)#",
    "acl-ext": "{h}(config-ext-nacl)#",
}

PIPE_FILTERS = ("include", "exclude", "begin", "section")


def filter_output(output: str, how: str, pattern: str) -> str:
    """Filtres ``| include``, ``| exclude``, ``| begin`` et ``| section`` des commandes show."""
    lines = output.splitlines()
    regex = re.compile(pattern, re.IGNORECASE)
    if how == "include":
        kept = [line for line in lines if regex.search(line)]
    elif how == "exclude":
        kept = [line for line in lines if not regex.search(line)]
    elif how == "begin":
        start = next((i for i, line in enumerate(lines) if regex.search(line)), len(lines))
        kept = lines[start:]
    else:  # section : la ligne trouvée et ses lignes indentées
        kept, inside = [], False
        for line in lines:
            if line and not line[0].isspace():
                inside = bool(regex.search(line))
            if inside or (line[:1].isspace() and regex.search(line)):
                kept.append(line)
    return "\n".join(kept)


class Session:
    def __init__(self, device: Device):
        self.device = device
        self.mode = "user"
        self.ifaces: list[str] = []
        self.vlan_ids: list[int] = []
        self.line_kind: str | None = None
        self.ospf_pid: int | None = None
        self.eigrp_asn: int | None = None
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
        pipe = None
        if "|" in raw:
            raw, _, pipe = raw.partition("|")
            if not raw.strip():
                return INVALID
        tokens = raw.split()
        try:
            output = self._dispatch(tokens) or ""
            if pipe is not None:
                output = self._apply_pipe(output, pipe)
            return output
        except CommandError as exc:
            return str(exc)

    @staticmethod
    def _apply_pipe(output: str, pipe: str) -> str:
        words = pipe.split(None, 1)
        if len(words) < 2:
            raise CommandError(INCOMPLETE)
        choices = [f for f in PIPE_FILTERS if f.startswith(words[0].lower())]
        if len(choices) != 1 or is_error(output):
            raise CommandError(INVALID)
        try:
            return filter_output(output, choices[0], words[1].strip())
        except re.error:
            raise CommandError(INVALID) from None

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
        self.eigrp_asn = None
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
            R(["show", "vtp", "status"], self.show_vtp, "État VTP"),
            R(["show", "ip", "interface", "brief"], self.show_ip_int_brief, "Résumé des interfaces"),
            R(["show", "interfaces", "trunk"], self.show_trunk, "Interfaces en trunk"),
            R(["show", "interfaces", "status"], self.show_int_status, "État des ports"),
            R(["show", "interfaces", "description"], self.show_int_description, "Descriptions des interfaces"),
            R(["show", "etherchannel", "summary"], self.show_etherchannel, "Résumé EtherChannel"),
            R(["show", "spanning-tree"], self.show_stp, "Spanning tree"),
            R(["show", "spanning-tree", "summary"], self.show_stp, "Résumé spanning tree"),
            R(["show", "ip", "route"], self.show_ip_route, "Table de routage"),
            R(["show", "ip", "protocols"], self.show_ip_protocols, "Protocoles de routage"),
            R(["show", "ip", "dhcp", "pool"], self.show_dhcp_pool, "Pools DHCP"),
            R(["show", "ip", "dhcp", "snooping"], self.show_dhcp_snooping, "DHCP snooping"),
            R(["show", "ip", "arp", "inspection"], self.show_arp_inspection, "Inspection ARP dynamique"),
            R(["show", "ip", "nat", "translations"], self.show_nat, "Traductions NAT"),
            R(["show", "ipv6", "interface", "brief"], self.show_ipv6_int_brief, "Résumé des interfaces IPv6"),
            R(["show", "ipv6", "route"], self.show_ipv6_route, "Table de routage IPv6"),
            R(["show", "standby", "brief"], self.show_standby, "Résumé HSRP"),
            R(["show", "standby"], self.show_standby, "État HSRP"),
            R(["show", "access-lists"], self.show_acls, "Listes de contrôle d'accès"),
            R(["show", "port-security"], self.show_port_security, "Sécurité des ports"),
            R(["show", "cdp"], self.show_cdp, "État CDP"),
            R(["show", "cdp", "neighbors"], self.show_cdp, "Voisins CDP"),
            R(["show", "lldp"], self.show_lldp, "État LLDP"),
            R(["show", "lldp", "neighbors"], self.show_lldp, "Voisins LLDP"),
            R(["show", "ntp", "associations"], self.show_ntp, "Serveurs NTP"),
            R(["show", "logging"], self.show_logging, "Journalisation"),
            R(["show", "snmp", "community"], self.show_snmp, "Communautés SNMP"),
            R(["show", "version"], self.show_version, "Version du système"),
            R(["show", "history"], lambda a, n: "\n".join("  " + h for h in self.history), "Historique"),
            R(["show", "ip", "ssh"], self.show_ssh, "État SSH"),
        ]
        exit_rule = R(["exit"], self.cmd_exit, "Quitter le mode courant", negatable=False)
        end_rule = R(["end"], self.cmd_end, "Revenir au mode privilégié", negatable=False)
        passive_rule = R(["passive-interface", "<rest>"], self.rtr_passive, "Interface passive")
        redistribute_rule = R(["redistribute", "<rest>"], self.rtr_redistribute, "Redistribuer des routes")
        auto_summary_rule = R(["auto-summary"], self.rtr_auto_summary, "Résumé automatique par classe")
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
            R(["service", "timestamps", "<rest>"], lambda a, n: None, "Horodatage des messages"),
            R(["security", "passwords", "min-length", "<n>"], self.cfg_min_length,
              "Longueur minimale des mots de passe"),
            R(["login", "block-for", "<s>", "attempts", "<n>", "within", "<t>"], self.cfg_login_block,
              "Bloquer les connexions après des échecs"),
            R(["aaa", "new-model"], self.cfg_aaa_new_model, "Activer AAA"),
            R(["aaa", "authentication", "login", "<list>", "<rest>"], self.cfg_aaa_login,
              "Méthodes d'authentification"),
            R(["banner", "motd", "<rest>"], self.cfg_banner, "Bannière"),
            R(["ip", "domain-name", "<name>"], self.cfg_domain_name, "Nom de domaine"),
            R(["ip", "domain", "name", "<name>"], self.cfg_domain_name, "Nom de domaine"),
            R(["ip", "domain-lookup"], self.cfg_domain_lookup, "Résolution DNS"),
            R(["ip", "name-server", "<rest>"], self.cfg_name_server, "Serveurs DNS"),
            R(["ip", "default-gateway", "<ip>"], self.cfg_default_gw, "Passerelle par défaut"),
            R(["ip", "routing"], self.cfg_ip_routing, "Activer le routage"),
            R(["ip", "route", "<net>", "<mask>", "<nh>", "<rest>"], self.cfg_ip_route,
              "Route statique (distance optionnelle)"),
            R(["ip", "ssh", "version", "<n>"], self.cfg_ssh_version, "Version SSH"),
            R(["ip", "ssh", "time-out", "<n>"], self.cfg_ssh_timeout, "Délai de négociation SSH"),
            R(["ip", "ssh", "authentication-retries", "<n>"], self.cfg_ssh_retries, "Tentatives SSH"),
            R(["ip", "http", "server"], self.cfg_http, "Serveur web d'administration"),
            R(["ip", "http", "secure-server"], self.cfg_https, "Serveur web HTTPS"),
            R(["ip", "dhcp", "pool", "<name>"], self.cfg_dhcp_pool, "Pool DHCP"),
            R(["ip", "dhcp", "excluded-address", "<ip>", "<rest>"], self.cfg_dhcp_excluded, "Adresses exclues"),
            R(["ip", "dhcp", "snooping"], self.cfg_dhcp_snooping, "Activer le DHCP snooping"),
            R(["ip", "dhcp", "snooping", "vlan", "<rest>"], self.cfg_dhcp_snooping_vlan, "VLAN surveillés"),
            R(["ip", "dhcp", "snooping", "information", "option"], self.cfg_dhcp_option82, "Option 82"),
            R(["ip", "arp", "inspection", "vlan", "<rest>"], self.cfg_arp_inspection, "Inspection ARP dynamique"),
            R(["ip", "access-list", "standard", "<name>"], self.cfg_named_acl_std, "ACL nommée standard"),
            R(["ip", "access-list", "extended", "<name>"], self.cfg_named_acl_ext, "ACL nommée étendue"),
            R(["ip", "nat", "<rest>"], self.cfg_nat, "Traduction d'adresses"),
            R(["ipv6", "unicast-routing"], self.cfg_ipv6_routing, "Activer le routage IPv6"),
            R(["ipv6", "route", "<prefix>", "<rest>"], self.cfg_ipv6_route, "Route statique IPv6"),
            R(["access-list", "<num>", "<rest>"], self.cfg_access_list, "Liste de contrôle d'accès"),
            R(["crypto", "key", "generate", "rsa", "<rest>"], self.cfg_crypto, "Générer les clés RSA"),
            R(["username", "<name>", "<rest>"], self.cfg_username, "Utilisateur local"),
            R(["vlan", "<id>"], self.cfg_vlan, "Créer/modifier un VLAN"),
            R(["interface", "range", "<rest>"], self.cfg_interface_range, "Plage d'interfaces"),
            R(["interface", "<if>", "<rest>"], self.cfg_interface, "Configurer une interface"),
            R(["line", "console", "<n>"], self.cfg_line_con, "Ligne console"),
            R(["line", "vty", "<a>", "<b>"], self.cfg_line_vty, "Lignes virtuelles (telnet/ssh)"),
            R(["router", "ospf", "<pid>"], self.cfg_router_ospf, "Routage OSPF"),
            R(["router", "eigrp", "<as>"], self.cfg_router_eigrp, "Routage EIGRP"),
            R(["router", "rip"], self.cfg_router_rip, "Routage RIP"),
            R(["spanning-tree", "mode", "<mode>"], self.cfg_stp_mode, "Mode spanning-tree"),
            R(["spanning-tree", "vlan", "<id>", "priority", "<n>"], self.cfg_stp_priority, "Priorité STP"),
            R(["spanning-tree", "vlan", "<id>", "root", "<kind>"], self.cfg_stp_root, "Pont racine STP"),
            R(["spanning-tree", "portfast", "default"], self.cfg_portfast_default,
              "PortFast sur tous les ports d'accès"),
            R(["spanning-tree", "portfast", "bpduguard", "default"], self.cfg_bpduguard_default,
              "BPDU Guard sur les ports PortFast"),
            R(["errdisable", "recovery", "cause", "<cause>"], self.cfg_errdisable_cause, "Réactivation automatique"),
            R(["errdisable", "recovery", "interval", "<n>"], self.cfg_errdisable_interval, "Délai de réactivation"),
            R(["vtp", "mode", "<mode>"], self.cfg_vtp_mode, "Mode VTP"),
            R(["vtp", "domain", "<name>"], self.cfg_vtp_domain, "Domaine VTP"),
            R(["vtp", "version", "<n>"], self.cfg_vtp_version, "Version VTP"),
            R(["vtp", "password", "<rest>"], self.cfg_vtp_password, "Mot de passe VTP"),
            R(["ntp", "server", "<ip>", "<rest>"], self.cfg_ntp_server, "Serveur de temps"),
            R(["ntp", "master", "<rest>"], self.cfg_ntp_master, "Source de temps de référence"),
            R(["clock", "timezone", "<name>", "<offset>", "<rest>"], self.cfg_timezone, "Fuseau horaire"),
            R(["logging", "host", "<ip>"], self.cfg_logging_host, "Serveur syslog"),
            R(["logging", "<ip>"], self.cfg_logging_host, "Serveur syslog"),
            R(["logging", "trap", "<level>"], self.cfg_logging_trap, "Niveau envoyé au serveur syslog"),
            R(["logging", "buffered", "<rest>"], self.cfg_logging_buffered, "Journal en mémoire"),
            R(["snmp-server", "community", "<name>", "<rest>"], self.cfg_snmp_community, "Communauté SNMP"),
            R(["snmp-server", "location", "<rest>"], self.cfg_snmp_location, "Emplacement"),
            R(["snmp-server", "contact", "<rest>"], self.cfg_snmp_contact, "Contact"),
            R(["snmp-server", "host", "<ip>", "<rest>"], self.cfg_snmp_host, "Destinataire des traps"),
            R(["cdp", "run"], self.cfg_cdp_run, "Activer CDP"),
            R(["lldp", "run"], self.cfg_lldp_run, "Activer LLDP"),
            exit_rule, end_rule,
        ]
        iface = [
            R(["description", "<rest>"], self.if_description, "Description"),
            R(["shutdown"], self.if_shutdown, "Désactiver l'interface"),
            R(["switchport"], self.if_switchport, "Port de niveau 2 (no switchport : port routé)"),
            R(["switchport", "mode", "<mode>"], self.if_sw_mode, "Mode access/trunk"),
            R(["switchport", "access", "vlan", "<id>"], self.if_access_vlan, "VLAN d'accès"),
            R(["switchport", "voice", "vlan", "<id>"], self.if_voice_vlan, "VLAN voix"),
            R(["switchport", "trunk", "allowed", "vlan", "<rest>"], self.if_trunk_allowed, "VLAN autorisés"),
            R(["switchport", "trunk", "native", "vlan", "<id>"], self.if_native, "VLAN natif"),
            R(["switchport", "trunk", "encapsulation", "dot1q"], lambda a, n: None, "Encapsulation 802.1Q"),
            R(["switchport", "nonegotiate"], self.if_nonegotiate, "Désactiver DTP"),
            R(["switchport", "port-security"], self.if_port_security, "Sécurité de port"),
            R(["switchport", "port-security", "maximum", "<n>"], self.if_ps_max, "Nombre max d'adresses MAC"),
            R(["switchport", "port-security", "violation", "<mode>"], self.if_ps_violation, "Action en cas de violation"),
            R(["switchport", "port-security", "mac-address", "sticky"], self.if_ps_sticky, "Apprentissage sticky"),
            R(["spanning-tree", "portfast"], self.if_portfast, "PortFast"),
            R(["spanning-tree", "portfast", "edge"], self.if_portfast, "PortFast"),
            R(["spanning-tree", "portfast", "trunk"], self.if_portfast, "PortFast sur un trunk"),
            R(["spanning-tree", "bpduguard", "enable"], self.if_bpduguard, "BPDU Guard"),
            R(["spanning-tree", "guard", "<kind>"], self.if_stp_guard, "Root Guard / Loop Guard"),
            R(["spanning-tree", "cost", "<n>"], self.if_stp_cost, "Coût STP du port"),
            R(["spanning-tree", "port-priority", "<n>"], self.if_stp_port_priority, "Priorité STP du port"),
            R(["ip", "address", "<ip>", "<mask>", "<rest>"], self.if_ip, "Adresse IP"),
            R(["ip", "address", "dhcp"], self.if_ip_dhcp, "Adresse par DHCP"),
            R(["ip", "helper-address", "<ip>"], self.if_helper, "Relais DHCP"),
            R(["ip", "access-group", "<acl>", "<dir>"], self.if_access_group, "Appliquer une ACL"),
            R(["ip", "nat", "<dir>"], self.if_nat, "Interface NAT inside/outside"),
            R(["ip", "ospf", "cost", "<n>"], self.if_ospf_cost, "Coût OSPF"),
            R(["ip", "ospf", "priority", "<n>"], self.if_ospf_priority, "Priorité OSPF (élection DR)"),
            R(["ip", "ospf", "<pid>", "area", "<area>"], self.if_ospf_area, "Activer OSPF sur l'interface"),
            R(["ip", "dhcp", "snooping", "trust"], self.if_snooping_trust, "Port de confiance DHCP"),
            R(["ip", "dhcp", "snooping", "limit", "rate", "<n>"], self.if_snooping_rate, "Débit DHCP maximal"),
            R(["ip", "arp", "inspection", "trust"], self.if_arp_trust, "Port de confiance ARP"),
            R(["ipv6", "address", "<addr>", "<rest>"], self.if_ipv6_address, "Adresse IPv6"),
            R(["ipv6", "enable"], self.if_ipv6_enable, "Activer IPv6 (lien local)"),
            R(["standby", "version", "<n>"], self.if_standby_version, "Version HSRP"),
            R(["standby", "<grp>", "ip", "<ip>"], self.if_standby_ip, "Adresse virtuelle HSRP"),
            R(["standby", "<grp>", "priority", "<n>"], self.if_standby_priority, "Priorité HSRP"),
            R(["standby", "<grp>", "preempt", "<rest>"], self.if_standby_preempt, "Préemption HSRP"),
            R(["storm-control", "broadcast", "level", "<rest>"], lambda a, n: self.if_storm("broadcast", a, n),
              "Seuil de broadcast"),
            R(["storm-control", "multicast", "level", "<rest>"], lambda a, n: self.if_storm("multicast", a, n),
              "Seuil de multicast"),
            R(["storm-control", "action", "<action>"], lambda a, n: self.if_storm("action", a, n),
              "Action en cas de tempête"),
            R(["encapsulation", "dot1q", "<id>"], self.if_encapsulation, "Sous-interface 802.1Q"),
            R(["clock", "rate", "<n>"], self.if_clock_rate, "Horloge (DCE)"),
            R(["bandwidth", "<n>"], self.if_bandwidth, "Bande passante (kbit/s)"),
            R(["channel-group", "<n>", "mode", "<mode>"], self.if_channel_group, "EtherChannel"),
            R(["channel-protocol", "<proto>"], self.if_channel_protocol, "Protocole EtherChannel"),
            R(["speed", "<speed>"], self.if_speed, "Vitesse"),
            R(["duplex", "<duplex>"], self.if_duplex, "Duplex"),
            R(["cdp", "enable"], self.if_cdp, "CDP sur l'interface"),
            R(["lldp", "transmit"], lambda a, n: self.if_lldp("transmit", n), "Émission LLDP"),
            R(["lldp", "receive"], lambda a, n: self.if_lldp("receive", n), "Réception LLDP"),
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
            R(["login", "authentication", "<list>"], self.line_login_auth, "Liste d'authentification AAA"),
            R(["transport", "input", "<rest>"], self.line_transport, "Protocoles autorisés"),
            R(["exec-timeout", "<rest>"], self.line_exec_timeout, "Délai d'inactivité"),
            R(["logging", "synchronous"], self.line_logging_sync, "Messages synchronisés"),
            R(["access-class", "<acl>", "<dir>"], self.line_access_class, "Filtrer les accès à la ligne"),
            exit_rule, end_rule,
        ]
        router = [
            R(["network", "<net>", "<wild>", "area", "<area>"], self.ospf_network, "Annoncer un réseau"),
            R(["router-id", "<ip>"], self.ospf_router_id, "Identifiant du routeur"),
            passive_rule, redistribute_rule,
            R(["default-information", "originate"], self.rtr_default, "Propager la route par défaut"),
            R(["default-information", "originate", "always"], self.ospf_default_always,
              "Propager une route par défaut même absente"),
            R(["auto-cost", "reference-bandwidth", "<n>"], self.ospf_reference_bw, "Bande passante de référence"),
            R(["area", "<area>", "stub"], lambda a, n: self.ospf_area_type(a, n, "stub"), "Zone stub"),
            R(["area", "<area>", "stub", "no-summary"], lambda a, n: self.ospf_area_type(a, n, "stub no-summary"),
              "Zone totalement stub"),
            R(["area", "<area>", "nssa"], lambda a, n: self.ospf_area_type(a, n, "nssa"), "Zone NSSA"),
            exit_rule, end_rule,
        ]
        router_eigrp = [
            R(["network", "<net>", "<rest>"], self.eigrp_network, "Annoncer un réseau (wildcard optionnel)"),
            R(["eigrp", "router-id", "<ip>"], self.eigrp_router_id, "Identifiant du routeur"),
            passive_rule, redistribute_rule, auto_summary_rule,
            exit_rule, end_rule,
        ]
        router_rip = [
            R(["version", "<n>"], self.rip_version, "Version de RIP"),
            R(["network", "<net>"], self.rip_network, "Annoncer un réseau (par classe)"),
            R(["default-information", "originate"], self.rtr_default, "Propager la route par défaut"),
            passive_rule, redistribute_rule, auto_summary_rule,
            exit_rule, end_rule,
        ]
        dhcp = [
            R(["network", "<net>", "<mask>"], self.dhcp_network, "Réseau du pool"),
            R(["default-router", "<ip>"], self.dhcp_router, "Passerelle distribuée"),
            R(["dns-server", "<rest>"], self.dhcp_dns, "Serveur(s) DNS distribué(s)"),
            R(["domain-name", "<name>"], self.dhcp_domain, "Domaine distribué"),
            R(["lease", "<rest>"], self.dhcp_lease, "Durée du bail (jours [heures [minutes]])"),
            exit_rule, end_rule,
        ]
        acl = [
            R(["permit", "<rest>"], lambda a, n: self.acl_entry("permit", a, n), "Autoriser"),
            R(["deny", "<rest>"], lambda a, n: self.acl_entry("deny", a, n), "Refuser"),
            R(["remark", "<rest>"], lambda a, n: self.acl_entry("remark", a, n), "Commentaire"),
            R(["<seq>", "<rest>"], self.acl_sequenced, "Entrée à un numéro de séquence donné"),
            exit_rule, end_rule,
        ]
        return {"user": user, "exec": exec_, "config": config, "if": iface, "vlan": vlan,
                "line": line, "router": router, "router-eigrp": router_eigrp, "router-rip": router_rip,
                "dhcp": dhcp, "acl-std": acl, "acl-ext": acl}

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
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            if not i.is_switchport:
                continue
            status = "disabled" if i.shutdown else "notconnect"
            vlan = "trunk" if i.mode == "trunk" else str(i.access_vlan)
            duplex = "auto" if i.duplex == "auto" else i.duplex
            speed = "auto" if i.speed == "auto" else i.speed
            kind = "10/100/1000BaseTX" if i.name.startswith("Gigabit") else "10/100BaseTX"
            lines.append(f"{i.short:<10}{i.description[:18]:<19}{status:<13}{vlan:<11}{duplex:<8}{speed:<6}{kind}")
        return "\n".join(lines)

    def show_int_description(self, args, negate):
        lines = ["Interface                      Status         Protocol Description"]
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            status = "admin down" if i.shutdown else "up"
            proto = "down" if i.shutdown else "up"
            lines.append(f"{i.short:<31}{status:<15}{proto:<9}{i.description}")
        return "\n".join(lines)

    def show_etherchannel(self, args, negate):
        groups = sorted({i.channel_group for i in self.device.interfaces.values() if i.channel_group})
        lines = ["Flags:  D - down        P - bundled in port-channel",
                 "        S - Layer2      R - Layer3      U - in use", "",
                 f"Number of channel-groups in use: {len(groups)}", "",
                 "Group  Port-channel  Protocol    Ports",
                 "------+-------------+-----------+-----------------------------------------------"]
        for group in groups:
            members = [i for i in self.device.interfaces.values() if i.channel_group == group]
            po = self.device.interfaces.get(f"Port-channel{group}")
            layer = "S" if po is None or po.is_switchport else "R"
            protocol = next((m.channel_protocol or CHANNEL_PROTOCOLS.get(m.channel_mode or "on") for m in members),
                            None) or "-"
            ports = " ".join(f"{m.short}({'D' if m.shutdown else 'P'})" for m in members)
            lines.append(f"{group:<7}Po{group}({layer}U){'':<5}{protocol.upper():<12}{ports}")
        return "\n".join(lines)

    def show_vtp(self, args, negate):
        d = self.device
        return "\n".join([
            "VTP Version capable             : 1 to 3",
            f"VTP version running             : {d.vtp_version}",
            f"VTP Domain Name                 : {d.vtp_domain or ''}",
            "VTP Pruning Mode                : Disabled",
            f"VTP Operating Mode              : {d.vtp_mode.capitalize()}",
            f"Number of existing VLANs        : {len(d.vlans) + 4}",
            f"MD5 digest                      : {'(mot de passe configuré)' if d.vtp_password else ''}",
        ])

    def show_stp(self, args, negate):
        d = self.device
        if d.kind != "switch":
            raise CommandError(INVALID)
        root_for = [str(v) for v, p in sorted(d.stp_priority.items()) if p <= 24576]
        lines = [f"Switch is in {d.stp_mode} mode",
                 f"Root bridge for: {', '.join('VLAN' + v.zfill(4) for v in root_for) or 'none'}",
                 f"PortFast Default            is {'enabled' if d.stp_portfast_default else 'disabled'}",
                 f"PortFast BPDU Guard Default is {'enabled' if d.stp_bpduguard_default else 'disabled'}", "",
                 "VLAN     Bridge priority"]
        for vid in sorted(d.vlans):
            lines.append(f"VLAN{vid:04d} {d.stp_priority.get(vid, 32768) + vid}")
        guarded = [i for i in d.interfaces.values() if i.portfast or i.bpduguard or i.stp_guard]
        if guarded:
            lines += ["", "Port      PortFast  BPDU Guard  Guard"]
            for i in guarded:
                lines.append(f"{i.short:<10}{'yes' if i.portfast else 'no':<10}{'yes' if i.bpduguard else 'no':<12}"
                             f"{i.stp_guard or '-'}")
        return "\n".join(lines)

    def _best_static_routes(self) -> list[tuple[str, str, str, int]]:
        """Routes statiques installées : pour chaque préfixe, celle(s) de plus petite distance."""
        best: dict[tuple[str, str], int] = {}
        for route in self.device.static_routes:
            distance = self.device.route_distances.get(route, 1)
            key = (route[0], route[1])
            best[key] = min(best.get(key, 256), distance)
        return [(*r, self.device.route_distances.get(r, 1)) for r in self.device.static_routes
                if self.device.route_distances.get(r, 1) == best[(r[0], r[1])]]

    def show_ip_route(self, args, negate):
        routes = self._best_static_routes()
        default = next((r[2] for r in routes if r[0] == "0.0.0.0"), None)
        lines = ["Codes: L - local, C - connected, S - static, O - OSPF, D - EIGRP, R - RIP", "",
                 "Gateway of last resort is " + (default or "not set"), ""]
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            if i.ip and i.mask and not i.shutdown:
                net = ipaddress.IPv4Network(f"{i.ip}/{i.mask}", strict=False)
                lines.append(f"C        {net} is directly connected, {i.name}")
                lines.append(f"L        {i.ip}/32 is directly connected, {i.name}")
        for net, mask, nh, distance in routes:
            prefix = mask_to_prefix(mask)
            star = "*" if net == "0.0.0.0" else " "
            lines.append(f"S{star}       {net}/{prefix} [{distance}/0] via {nh}")
        return "\n".join(lines)

    def show_ip_protocols(self, args, negate):
        d = self.device
        lines = []
        for asn, proc in d.eigrp.items():
            lines.append(f'Routing Protocol is "eigrp {asn}"')
            lines.append(f"  EIGRP-IPv4 Protocol for AS({asn})")
            lines.append(f"    Router-ID: {proc.router_id or self._auto_router_id()}")
            lines.append(f"  Automatic Summarization: {'enabled' if proc.auto_summary else 'disabled'}")
            lines.append("  Routing for Networks:")
            lines += [f"    {n}{' ' + w if w else ''}" for n, w in proc.networks]
            lines += self._passive_summary(proc)
        for pid, proc in d.ospf.items():
            lines.append(f'Routing Protocol is "ospf {pid}"')
            lines.append(f"  Router ID {proc.router_id or self._auto_router_id()}")
            lines.append("  Routing for Networks:")
            lines += [f"    {n} {w} area {a}" for n, w, a in proc.networks]
            lines += [f"    {i.name} area {i.ospf_area[1]}" for i in d.interfaces.values()
                      if i.ospf_area and i.ospf_area[0] == pid]
            lines += self._passive_summary(proc)
        if d.rip:
            lines.append('Routing Protocol is "rip"')
            lines.append(f"  Default version control: send version {d.rip.version}, receive version "
                         f"{d.rip.version if d.rip.version == 2 else '1 2'}")
            summary = "in effect" if d.rip.auto_summary else "not in effect"
            lines.append(f"  Automatic network summarization is {summary}")
            lines.append("  Routing for Networks:")
            lines += [f"    {n}" for n in d.rip.networks]
            lines += self._passive_summary(d.rip)
        return "\n".join(lines)

    def _passive_summary(self, proc: RoutingProcess) -> list[str]:
        names = sorted(n for n in self.device.interfaces if proc.is_passive(n))
        return ["  Passive Interface(s):"] + [f"    {n}" for n in names] if names else []

    def _auto_router_id(self) -> str:
        addressed = [i for i in self.device.interfaces.values() if valid_ip(i.ip or "")]
        ips = [i.ip for i in addressed if i.name.startswith("Loopback")] or [i.ip for i in addressed]
        return max(ips, key=lambda ip: ipaddress.IPv4Address(ip)) if ips else "0.0.0.0"

    def show_dhcp_pool(self, args, negate):
        lines = []
        for pool in self.device.dhcp_pools.values():
            lines += [f"Pool {pool.name} :", f" Network {pool.network} {pool.mask}",
                      f" Default router {pool.default_router}", f" DNS server {pool.dns_server}"]
            if pool.lease:
                lines.append(f" Lease {pool.lease}")
        return "\n".join(lines)

    def show_dhcp_snooping(self, args, negate):
        d = self.device
        lines = [f"Switch DHCP snooping is {'enabled' if d.dhcp_snooping else 'disabled'}",
                 "DHCP snooping is configured on following VLANs:",
                 format_vlan_list(d.dhcp_snooping_vlans) or "none",
                 f"Insertion of option 82 is {'enabled' if d.dhcp_snooping_option82 else 'disabled'}", "",
                 "Interface                  Trusted    Rate limit (pps)",
                 "-----------------------    -------    ----------------"]
        for i in sorted(d.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            if i.dhcp_snooping_trust or i.dhcp_snooping_rate:
                lines.append(f"{i.name:<27}{'yes' if i.dhcp_snooping_trust else 'no':<11}"
                             f"{i.dhcp_snooping_rate or 'unlimited'}")
        return "\n".join(lines)

    def show_arp_inspection(self, args, negate):
        d = self.device
        lines = ["Source Mac Validation      : Disabled",
                 f"Vlans enabled              : {format_vlan_list(d.arp_inspection_vlans) or 'none'}", "",
                 "Interface        Trust State"]
        lines += [f"{i.short:<17}Trusted" for i in d.interfaces.values() if i.arp_inspection_trust]
        return "\n".join(lines)

    def show_nat(self, args, negate):
        lines = ["Pro Inside global      Inside local       Outside local      Outside global"]
        for rule in self.device.nat_rules:
            words = rule.split()
            if words[2:5] == ["inside", "source", "static"]:
                if words[5] in ("tcp", "udp"):
                    proto, local, lport, glob, gport = words[5:10]
                    lines.append(f"{proto:<4}{glob + ':' + gport:<19}{local + ':' + lport:<19}---                ---")
                else:
                    lines.append(f"--- {words[6]:<19}{words[5]:<19}---                ---")
        return "\n".join(lines)

    def show_ipv6_int_brief(self, args, negate):
        lines = []
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            status = "[administratively down/down]" if i.shutdown else "[up/up]"
            lines.append(f"{i.name:<23}{status}")
            addresses = []
            if i.ipv6_link_local:
                addresses.append(i.ipv6_link_local)
            elif i.ipv6_addresses or i.ipv6_enabled:
                addresses.append("FE80::(automatique, EUI-64)")
            addresses += [a.split("/")[0] for a in i.ipv6_addresses]
            lines += [f"    {a.upper()}" for a in addresses] or ["    unassigned"]
        return "\n".join(lines)

    def show_ipv6_route(self, args, negate):
        lines = ["IPv6 Routing Table - default", "Codes: C - Connected, L - Local, S - Static", ""]
        if not self.device.ipv6_routing:
            lines.insert(0, "% IPv6 routing not enabled (ipv6 unicast-routing)")
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            if i.shutdown:
                continue
            for address in i.ipv6_addresses:
                net = ipaddress.IPv6Network(address.split()[0], strict=False)
                lines += [f"C   {str(net).upper()} [0/0]", f"     via {i.name}, directly connected"]
                if " " not in address:
                    lines += [f"L   {address.split('/')[0].upper()}/128 [0/0]", f"     via {i.name}, receive"]
        best: dict[str, int] = {}
        for prefix, _, distance in self.device.ipv6_routes:
            best[prefix] = min(best.get(prefix, 256), distance)
        for prefix, nh, distance in self.device.ipv6_routes:
            if distance == best[prefix]:
                lines += [f"S   {prefix.upper()} [{distance}/0]", f"     via {nh.upper() if ':' in nh else nh}"]
        return "\n".join(lines)

    def show_standby(self, args, negate):
        lines = ["                     P indicates configured to preempt.",
                 "Interface   Grp  Pri P State   Active          Standby         Virtual IP"]
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            for g in sorted(i.standby.values(), key=lambda g: g.group):
                state = "Init" if i.shutdown or not g.ip else "Active"
                lines.append(f"{i.short:<12}{g.group:<5}{g.priority:<4}{'P' if g.preempt else ' '} {state:<8}"
                             f"{'local' if state == 'Active' else 'unknown':<16}{'unknown':<16}{g.ip or 'unknown'}")
        return "\n".join(lines)

    def show_acls(self, args, negate):
        lines = []
        for name, entries in self.device.acls.items():
            kind = "Extended" if (not name.isdigit() and entries and entries[0] == "__ext__") or (
                name.isdigit() and (100 <= int(name) <= 199 or 2000 <= int(name) <= 2699)) else "Standard"
            lines.append(f"{kind} IP access list {name}")
            real = [e for e in entries if e != "__ext__"]
            lines += [f"    {seq} {entry}" for seq, entry in zip(self.device.acl_seqs(name), real)]
        return "\n".join(lines)

    def show_port_security(self, args, negate):
        lines = ["Secure Port  MaxSecureAddr  CurrentAddr  SecurityViolation  Security Action"]
        for i in self.device.interfaces.values():
            if i.port_security:
                lines.append(f"{i.short:>11}{i.port_security_max:>15}{0:>13}{0:>19}  {i.port_security_violation.capitalize()}")
        return "\n".join(lines)

    def show_cdp(self, args, negate):
        if not self.device.cdp_run:
            return "% CDP is not enabled"
        disabled = [i.short for i in self.device.interfaces.values() if not i.cdp_enabled]
        return ("Global CDP information:\n\tSending CDP packets every 60 seconds\n"
                "\tSending a holdtime value of 180 seconds"
                + (f"\n\tCDP désactivé sur : {', '.join(disabled)}" if disabled else "")
                + "\n(simulateur : aucun voisin n'est raccordé)")

    def show_lldp(self, args, negate):
        if not self.device.lldp_run:
            return "% LLDP is not enabled"
        off = [i.short for i in self.device.interfaces.values() if not (i.lldp_transmit and i.lldp_receive)]
        return ("Global LLDP Information:\n\tStatus: ACTIVE\n\tLLDP advertisements are sent every 30 seconds"
                + (f"\n\tLLDP restreint sur : {', '.join(off)}" if off else "")
                + "\n(simulateur : aucun voisin n'est raccordé)")

    def show_ntp(self, args, negate):
        lines = ["  address         ref clock       st   when   poll reach  delay  offset   disp"]
        lines += [f"~{server:<16}.INIT.          16      -     64     0  0.000   0.000 15937." for server in
                  self.device.ntp_servers]
        if self.device.ntp_master:
            lines.append(f"*~127.127.1.1     .LOCL.          {self.device.ntp_master:<5}  -     16   377  0.000   "
                         "0.000  0.240")
        return "\n".join(lines)

    def show_logging(self, args, negate):
        d = self.device
        buffered = f"level debugging, {d.logging_buffered}" if d.logging_buffered else "disabled"
        lines = ["Syslog logging: enabled", "    Console logging: level debugging",
                 f"    Buffer logging:  {buffered}",
                 f"    Trap logging: level {d.logging_trap or 'informational'}"]
        lines += [f"        Logging to {host}  (udp port 514)" for host in d.logging_hosts]
        return "\n".join(lines)

    def show_snmp(self, args, negate):
        lines = []
        for name, (mode, acl) in self.device.snmp_communities.items():
            lines += [f"Community name: {name}", f"Community Index: {name}",
                      f"Access: {'read-only' if mode == 'RO' else 'read-write'}"
                      + (f"  (ACL {acl})" if acl else ""), ""]
        return "\n".join(lines)

    def show_ssh(self, args, negate):
        if not self.device.rsa_modulus:
            return "SSH Disabled - version 1.99\n%Please create RSA keys to enable SSH."
        return (f"SSH Enabled - version {self.device.ssh_version or '1.99'}\n"
                f"Authentication timeout: {self.device.ssh_timeout or 120} secs; "
                f"Authentication retries: {self.device.ssh_retries or 3}")

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
        if negate:
            self.device.enable_secret = None
            return
        words = args[0].split()
        if len(words) > 2 and words[0].lower() == "algorithm-type":  # enable algorithm-type scrypt secret X
            raise CommandError(INVALID)
        secret = _strip_level(args[0])
        self._check_length(secret)
        self.device.enable_secret = secret

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
        net, mask, nh, rest = args
        if not (valid_ip(net) and valid_mask(mask)):
            raise CommandError(INVALID)
        if not valid_ip(nh):
            canonical = normalize_iface(nh)
            if not canonical or canonical not in self.device.interfaces:
                raise CommandError(INVALID)
            nh = canonical
        distance = None
        words = rest.split()
        if words and valid_ip(words[0]) and not valid_ip(nh):
            nh = f"{nh} {words.pop(0)}"  # ip route ... g0/1 203.0.113.1
        while words:
            word = words.pop(0)
            if word.isdigit() and 1 <= int(word) <= 255 and distance is None:
                distance = int(word)
            elif word.lower() == "permanent":
                continue
            elif word.lower() == "name" and words:
                words.pop(0)
            else:
                raise CommandError(INVALID)
        route = (net, mask, nh)
        if negate:
            self.device.static_routes = [r for r in self.device.static_routes if r != route]
            self.device.route_distances.pop(route, None)
            return
        if route not in self.device.static_routes:
            self.device.static_routes.append(route)
        if distance and distance != 1:
            self.device.route_distances[route] = distance
        else:
            self.device.route_distances.pop(route, None)

    def cfg_ipv6_routing(self, args, negate):
        self.device.ipv6_routing = not negate

    def cfg_ipv6_route(self, args, negate):
        prefix, rest = args
        try:
            prefix = normalize_ipv6_prefix(prefix)
        except ValueError:
            raise CommandError(INVALID) from None
        if "/" not in args[0]:
            raise CommandError(INVALID)
        words = rest.split()
        if not words:
            raise CommandError(INCOMPLETE)
        hop_words = []
        first = words.pop(0)
        if valid_ipv6(first):
            hop_words.append(first)
        else:
            canonical = normalize_iface(first)
            if not canonical or canonical not in self.device.interfaces:
                raise CommandError(INVALID)
            hop_words.append(canonical)
            if words and valid_ipv6(words[0]):
                hop_words.append(words.pop(0))
        distance = 1
        if words:
            if len(words) != 1 or not words[0].isdigit() or not 1 <= int(words[0]) <= 255:
                raise CommandError(INVALID)
            distance = int(words[0])
        hop = _canonical_hop(" ".join(hop_words))
        routes = [r for r in self.device.ipv6_routes if (r[0], r[1]) != (prefix, hop)]
        if not negate:
            routes.append((prefix, hop, distance))
        self.device.ipv6_routes = routes

    def cfg_name_server(self, args, negate):
        servers = args[0].split()
        if not servers or not all(valid_ip(s) or valid_ipv6(s) for s in servers):
            raise CommandError(INVALID)
        for server in servers:
            if negate:
                if server in self.device.name_servers:
                    self.device.name_servers.remove(server)
            elif server not in self.device.name_servers:
                self.device.name_servers.append(server)

    def cfg_ssh_version(self, args, negate):
        if args[0] not in ("1", "2"):
            raise CommandError(INVALID)
        self.device.ssh_version = None if negate else int(args[0])

    def cfg_ssh_timeout(self, args, negate):
        self.device.ssh_timeout = None if negate else self._number(args[0], 1, 120)

    def cfg_ssh_retries(self, args, negate):
        self.device.ssh_retries = None if negate else self._number(args[0], 0, 5)

    def cfg_http(self, args, negate):
        self.device.http_server = not negate

    def cfg_https(self, args, negate):
        self.device.https_server = not negate

    @staticmethod
    def _number(text: str, low: int, high: int) -> int:
        if not text.isdigit() or not low <= int(text) <= high:
            raise CommandError(INVALID)
        return int(text)

    def _check_length(self, password: str) -> None:
        minimum = self.device.min_password_length
        if minimum and len(password) < minimum:
            raise CommandError(f"% Password too short - must be at least {minimum} characters. "
                               "Password configuration failed")

    def cfg_min_length(self, args, negate):
        self.device.min_password_length = None if negate else self._number(args[0], 1, 16)

    def cfg_login_block(self, args, negate):
        if negate:
            self.device.login_block = None
            return
        seconds, attempts, within = (self._number(a, 1, 65535) for a in args)
        self.device.login_block = (seconds, attempts, within)

    def cfg_aaa_new_model(self, args, negate):
        self.device.aaa_new_model = not negate
        if negate:
            self.device.aaa_authentication.clear()

    def cfg_aaa_login(self, args, negate):
        if not self.device.aaa_new_model:
            raise CommandError(INVALID)
        key = f"login {args[0]}"
        if negate:
            self.device.aaa_authentication.pop(key, None)
            return
        methods = args[1].lower().split()
        if not methods or any(m not in ("local", "enable", "none", "line", "group", "radius", "tacacs+",
                                        "local-case") for m in methods):
            raise CommandError(INVALID)
        self.device.aaa_authentication[key] = " ".join(methods)

    def cfg_dhcp_snooping(self, args, negate):
        if self.device.kind != "switch":
            raise CommandError(INVALID)
        self.device.dhcp_snooping = not negate

    def _vlan_set(self, text: str) -> set[int]:
        try:
            vlans = parse_vlan_list(text)
        except ValueError:
            raise CommandError(INVALID) from None
        if not vlans or any(not 1 <= v <= 4094 for v in vlans):
            raise CommandError(INVALID)
        return vlans

    def cfg_dhcp_snooping_vlan(self, args, negate):
        vlans = self._vlan_set(args[0])
        if negate:
            self.device.dhcp_snooping_vlans -= vlans
        else:
            self.device.dhcp_snooping_vlans |= vlans

    def cfg_dhcp_option82(self, args, negate):
        self.device.dhcp_snooping_option82 = not negate

    def cfg_arp_inspection(self, args, negate):
        vlans = self._vlan_set(args[0])
        if negate:
            self.device.arp_inspection_vlans -= vlans
        else:
            self.device.arp_inspection_vlans |= vlans

    def cfg_portfast_default(self, args, negate):
        self.device.stp_portfast_default = not negate

    def cfg_bpduguard_default(self, args, negate):
        self.device.stp_bpduguard_default = not negate

    def cfg_errdisable_cause(self, args, negate):
        cause = args[0].lower()
        if cause not in ("all", "psecure-violation", "bpduguard", "dhcp-rate-limit", "arp-inspection",
                         "storm-control", "link-flap", "udld", "loopback"):
            raise CommandError(INVALID)
        if negate:
            self.device.errdisable_recovery.discard(cause)
        else:
            self.device.errdisable_recovery.add(cause)

    def cfg_errdisable_interval(self, args, negate):
        self.device.errdisable_interval = None if negate else self._number(args[0], 30, 86400)

    def cfg_vtp_version(self, args, negate):
        self.device.vtp_version = 1 if negate else self._number(args[0], 1, 3)

    def cfg_vtp_password(self, args, negate):
        self.device.vtp_password = None if negate else args[0].strip()

    def cfg_ntp_server(self, args, negate):
        server = args[0]
        if not (valid_ip(server) or valid_ipv6(server)):
            raise CommandError(INVALID)
        if negate:
            if server in self.device.ntp_servers:
                self.device.ntp_servers.remove(server)
        elif server not in self.device.ntp_servers:
            self.device.ntp_servers.append(server)

    def cfg_ntp_master(self, args, negate):
        stratum = args[0].strip() or "8"
        self.device.ntp_master = None if negate else self._number(stratum, 1, 15)

    def cfg_timezone(self, args, negate):
        if negate:
            self.device.clock_timezone = None
            return
        name, offset = args[0], args[1]
        if not re.match(r"^-?\d{1,2}$", offset) or not -23 <= int(offset) <= 23:
            raise CommandError(INVALID)
        self.device.clock_timezone = (name, int(offset))

    def cfg_logging_host(self, args, negate):
        host = args[0]
        if not valid_ip(host):
            raise CommandError(INVALID)
        if negate:
            if host in self.device.logging_hosts:
                self.device.logging_hosts.remove(host)
        elif host not in self.device.logging_hosts:
            self.device.logging_hosts.append(host)

    def cfg_logging_trap(self, args, negate):
        level = args[0].lower()
        if level.isdigit() and int(level) < len(LOG_LEVELS):
            level = LOG_LEVELS[int(level)]
        choices = [name for name in LOG_LEVELS if name.startswith(level)]
        if len(choices) != 1:
            raise CommandError(INVALID)
        self.device.logging_trap = None if negate else choices[0]

    def cfg_logging_buffered(self, args, negate):
        self.device.logging_buffered = None if negate else (args[0].strip() or "4096")

    def cfg_snmp_community(self, args, negate):
        name, rest = args
        if negate:
            self.device.snmp_communities.pop(name, None)
            return
        words = rest.split()
        mode = words[0].upper() if words else "RO"
        if mode not in ("RO", "RW") or len(words) > 2:
            raise CommandError(INVALID)
        self.device.snmp_communities[name] = (mode, words[1] if len(words) == 2 else None)

    def cfg_snmp_location(self, args, negate):
        self.device.snmp_location = None if negate else args[0].strip()

    def cfg_snmp_contact(self, args, negate):
        self.device.snmp_contact = None if negate else args[0].strip()

    def cfg_snmp_host(self, args, negate):
        if not valid_ip(args[0]):
            raise CommandError(INVALID)
        entry = " ".join([args[0], *args[1].split()])
        hosts = [h for h in self.device.snmp_hosts if h.split()[0] != args[0]]
        if not negate:
            hosts.append(entry)
        self.device.snmp_hosts = hosts

    def cfg_cdp_run(self, args, negate):
        self.device.cdp_run = not negate

    def cfg_lldp_run(self, args, negate):
        self.device.lldp_run = not negate

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
            elif word == "algorithm-type" and i + 1 < len(words):
                i += 2  # username X algorithm-type scrypt secret Y : le type de hachage n'est pas simulé
            elif word in ("secret", "password") and i + 1 < len(words):
                value = words[i + 1:]
                if value and value[0] in ("0", "5", "7", "8", "9") and len(value) > 1:
                    value = value[1:]
                user[word] = " ".join(value)
                self._check_length(user[word])
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
            self.device.acl_sequences.pop(name, None)
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
            self.device.acl_sequences.pop(number, None)
            return
        words = rest.split()
        if not words or words[0].lower() not in ("permit", "deny", "remark"):
            raise CommandError(INVALID)
        entry = _normalize_acl_entry(words)
        seqs = self.device.acl_seqs(number)
        self.device.acls.setdefault(number, []).append(entry)
        seqs.append((seqs[-1] if seqs else 0) + 10)

    def cfg_nat(self, args, negate):
        words = args[0].split()
        if not words or words[0].lower() not in ("inside", "outside", "pool", "translation"):
            raise CommandError(INVALID)
        if words[0].lower() == "inside" and len(words) < 4:
            raise CommandError(INCOMPLETE)
        rule = normalize_nat_rule("ip nat " + args[0])
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
        if self.device.vtp_mode == "client":
            raise CommandError("% VTP VLAN configuration not allowed when device is in CLIENT mode.")
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
        number = text[len(IFACE_KIND.match(text).group(0)):] if IFACE_KIND.match(text) else text
        if "-" in number or "," in number:
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
            elif canonical.startswith("Port-channel") and canonical[12:].isdigit() and 1 <= int(canonical[12:]) <= 48:
                self._create_port_channel(int(canonical[12:]))
            else:
                raise CommandError(INVALID)
        if negate:
            if "." in canonical or canonical.startswith(("Loopback", "Vlan", "Port-channel")):
                self.device.interfaces.pop(canonical, None)
            if canonical.startswith("Port-channel"):
                for member in self.device.interfaces.values():
                    if member.channel_group == int(canonical[12:]):
                        member.channel_group = member.channel_mode = None
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

    def cfg_router_eigrp(self, args, negate):
        if not args[0].isdigit() or not 1 <= int(args[0]) <= 65535:
            raise CommandError(INVALID)
        asn = int(args[0])
        if negate:
            self.device.eigrp.pop(asn, None)
            return
        self.device.eigrp.setdefault(asn, EigrpProcess(asn))
        self._exit_to_config()
        self.eigrp_asn = asn
        self.mode = "router-eigrp"

    def cfg_router_rip(self, args, negate):
        if negate:
            self.device.rip = None
            return
        if self.device.rip is None:
            self.device.rip = RipProcess()
        self._exit_to_config()
        self.mode = "router-rip"

    def cfg_stp_mode(self, args, negate):
        mode = args[0].lower()
        if mode not in ("pvst", "rapid-pvst", "mst"):
            raise CommandError(INVALID)
        self.device.stp_mode = "pvst" if negate else mode

    def cfg_stp_priority(self, args, negate):
        vlans, prio = self._vlan_set(args[0]), args[1]
        if not prio.isdigit() or int(prio) % 4096 or int(prio) > 61440:
            raise CommandError("% Bridge Priority must be in increments of 4096.")
        for vid in vlans:
            if negate:
                self.device.stp_priority.pop(vid, None)
            else:
                self.device.stp_priority[vid] = int(prio)

    def cfg_stp_root(self, args, negate):
        vlans, kind = self._vlan_set(args[0]), args[1]
        prio = {"primary": 24576, "secondary": 28672}.get(kind.lower())
        if prio is None:
            raise CommandError(INVALID)
        for vid in vlans:
            if negate:
                self.device.stp_priority.pop(vid, None)
            else:
                self.device.stp_priority[vid] = prio

    def _create_port_channel(self, group: int) -> Interface:
        name = f"Port-channel{group}"
        if name not in self.device.interfaces:
            iface = Interface(name, shutdown=False)
            iface._switch_owned = self.device.kind == "switch"
            self.device.interfaces[name] = iface
        return self.device.interfaces[name]

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
        if negate:
            for i in self._each_iface():
                i.channel_group = i.channel_mode = None
            return
        if not args[0].isdigit() or not 1 <= int(args[0]) <= 48:
            raise CommandError(INVALID)
        mode = args[1].lower()
        if mode not in CHANNEL_PROTOCOLS:
            raise CommandError(INVALID)
        protocol = CHANNEL_PROTOCOLS[mode]
        for i in self._each_iface():
            if not i.is_physical:
                raise CommandError(INVALID)
            if i.channel_protocol and protocol and i.channel_protocol != protocol:
                raise CommandError(f"Command rejected (Channel protocol mismatch for interface {i.name} "
                                   f"in group {args[0]})")
        group = int(args[0])
        created = f"Port-channel{group}" not in self.device.interfaces
        po = self._create_port_channel(group)
        for i in self._each_iface():
            i.channel_group, i.channel_mode = group, mode
            if protocol:
                i.channel_protocol = protocol
            if created and i.is_switchport:  # le port-channel hérite de la configuration du premier membre
                po.mode, po.access_vlan, po.native_vlan, po.trunk_allowed = (i.mode, i.access_vlan, i.native_vlan,
                                                                             i.trunk_allowed)
        if created:
            return f"Creating a port-channel interface Port-channel {group}"

    def if_channel_protocol(self, args, negate):
        proto = args[0].lower()
        if proto not in ("lacp", "pagp"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.channel_protocol = None if negate else proto

    def if_switchport(self, args, negate):
        if self.device.kind != "switch":
            raise CommandError(INVALID)
        for i in self._each_iface():
            if not (i.is_physical or i.name.startswith("Port-channel")):
                raise CommandError(INVALID)
            if negate == (not i.is_switchport):
                continue
            i._switch_owned = not negate
            if negate:
                i.mode, i.access_vlan, i.voice_vlan, i.port_security = None, 1, None, False
            else:
                i.ip = i.mask = None

    def if_nonegotiate(self, args, negate):
        self._require_switchport()
        for i in self._each_iface():
            if not negate and i.mode != "trunk" and i.mode != "access":
                raise CommandError("Command rejected: Conflict between 'nonegotiate' and 'dynamic' status.")
            i.nonegotiate = not negate

    def if_speed(self, args, negate):
        speed = args[0].lower()
        if speed not in ("10", "100", "1000", "auto"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if speed == "1000" and i.name.startswith("FastEthernet"):
                raise CommandError(INVALID)
            i.speed = "auto" if negate else speed

    def if_duplex(self, args, negate):
        choices = [d for d in ("auto", "full", "half") if d.startswith(args[0].lower())]
        if len(choices) != 1:
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.duplex = "auto" if negate else choices[0]

    def if_bandwidth(self, args, negate):
        for i in self._each_iface():
            i.bandwidth = None if negate else self._number(args[0], 1, 10000000)

    def if_stp_guard(self, args, negate):
        kind = args[0].lower()
        if kind not in ("root", "loop", "none"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.stp_guard = None if negate or kind == "none" else kind

    def if_stp_cost(self, args, negate):
        for i in self._each_iface():
            i.stp_cost = None if negate else self._number(args[0], 1, 200000000)

    def if_stp_port_priority(self, args, negate):
        value = self._number(args[0], 0, 240)
        if value % 16:
            raise CommandError("% Port Priority in increments of 16 is required")
        for i in self._each_iface():
            i.stp_port_priority = None if negate else value

    def if_ospf_cost(self, args, negate):
        for i in self._each_iface():
            i.ospf_cost = None if negate else self._number(args[0], 1, 65535)

    def if_ospf_priority(self, args, negate):
        for i in self._each_iface():
            i.ospf_priority = None if negate else self._number(args[0], 0, 255)

    def if_ospf_area(self, args, negate):
        pid, area = self._number(args[0], 1, 65535), args[1]
        if not (area.isdigit() or valid_ip(area)):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.ospf_area = None if negate else (pid, area)
        if not negate:
            self.device.ospf.setdefault(pid, OspfProcess(pid))

    def if_snooping_trust(self, args, negate):
        for i in self._each_iface():
            i.dhcp_snooping_trust = not negate

    def if_snooping_rate(self, args, negate):
        for i in self._each_iface():
            i.dhcp_snooping_rate = None if negate else self._number(args[0], 1, 2048)

    def if_arp_trust(self, args, negate):
        for i in self._each_iface():
            i.arp_inspection_trust = not negate

    def if_ipv6_address(self, args, negate):
        address, option = args[0], args[1].strip().lower()
        try:
            if option == "link-local":
                value = str(ipaddress.IPv6Address(address))
                if not ipaddress.IPv6Address(address).is_link_local:
                    raise ValueError(address)
            elif option in ("", "eui-64"):
                if "/" not in address:
                    raise ValueError(address)
                value = normalize_ipv6_address(f"{address} {option}".strip())
            else:
                raise ValueError(option)
        except ValueError:
            raise CommandError(INVALID) from None
        for i in self._each_iface():
            if i.is_switchport:
                raise CommandError(INVALID)
            if option == "link-local":
                i.ipv6_link_local = None if negate else value
            elif negate:
                i.ipv6_addresses = [a for a in i.ipv6_addresses if a != value]
            elif value not in i.ipv6_addresses:
                i.ipv6_addresses.append(value)

    def if_ipv6_enable(self, args, negate):
        for i in self._each_iface():
            i.ipv6_enabled = not negate

    def _standby_group(self, iface: Interface, text: str) -> HsrpGroup:
        group = self._number(text, 0, 4095)
        if group > 255 and iface.standby_version == 1:
            raise CommandError(INVALID)
        return iface.standby.setdefault(group, HsrpGroup(group))

    def if_standby_version(self, args, negate):
        version = self._number(args[0], 1, 2)
        for i in self._each_iface():
            i.standby_version = 1 if negate else version

    def if_standby_ip(self, args, negate):
        if not valid_ip(args[1]):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if negate:
                i.standby.pop(self._number(args[0], 0, 4095), None)
                continue
            if not i.ip:
                raise CommandError(f"% Address {args[1]} in group {args[0]} requires an interface IP address")
            self._standby_group(i, args[0]).ip = args[1]

    def if_standby_priority(self, args, negate):
        priority = self._number(args[1], 0, 255)
        for i in self._each_iface():
            self._standby_group(i, args[0]).priority = 100 if negate else priority

    def if_standby_preempt(self, args, negate):
        for i in self._each_iface():
            self._standby_group(i, args[0]).preempt = not negate

    def if_storm(self, kind, args, negate):
        value = args[0].strip().lower()
        for i in self._each_iface():
            if negate:
                i.storm_control.pop(kind, None)
                continue
            if kind == "action":
                if value not in ("shutdown", "trap"):
                    raise CommandError(INVALID)
                i.storm_control[kind] = value
            else:
                try:
                    level = float(value.split()[0])
                except (ValueError, IndexError):
                    raise CommandError(INVALID) from None
                if not 0 <= level <= 100:
                    raise CommandError(INVALID)
                i.storm_control[kind] = f"{level:.2f}"

    def if_cdp(self, args, negate):
        for i in self._each_iface():
            i.cdp_enabled = not negate

    def if_lldp(self, direction, negate):
        for i in self._each_iface():
            setattr(i, f"lldp_{direction}", not negate)

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

    def line_login_auth(self, args, negate):
        if not self.device.aaa_new_model:
            raise CommandError(INVALID)
        self._line().login_authentication = None if negate else args[0]

    def line_transport(self, args, negate):
        value = args[0].strip().lower()
        if not negate and value not in ("ssh", "telnet", "telnet ssh", "ssh telnet", "all", "none"):
            raise CommandError(INVALID)
        self._line().transport_input = None if negate else value

    def line_exec_timeout(self, args, negate):
        words = args[0].split()
        if not negate and (not words or len(words) > 2 or not all(w.isdigit() for w in words)):
            raise CommandError(INVALID)
        self._line().exec_timeout = None if negate else " ".join(words)

    def line_logging_sync(self, args, negate):
        self._line().logging_synchronous = not negate

    def line_access_class(self, args, negate):
        acl, direction = args[0], args[1].lower()
        if direction not in ("in", "out"):
            raise CommandError(INVALID)
        if negate:
            self._line().access_class.pop(direction, None)
        else:
            self._line().access_class[direction] = acl

    # -- routage dynamique ---------------------------------------------------

    def _ospf(self) -> OspfProcess:
        return self.device.ospf[self.ospf_pid]

    def _process(self) -> RoutingProcess:
        if self.mode == "router-eigrp":
            return self.device.eigrp[self.eigrp_asn]
        if self.mode == "router-rip":
            return self.device.rip
        return self._ospf()

    def ospf_network(self, args, negate):
        net, wild, area = args
        if not (valid_ip(net) and valid_ip(wild)) or not (area.isdigit() or valid_ip(area)):
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

    def ospf_default_always(self, args, negate):
        proc = self._ospf()
        proc.default_originate = proc.default_originate_always = not negate

    def ospf_reference_bw(self, args, negate):
        self._ospf().reference_bandwidth = None if negate else self._number(args[0], 1, 4294967)

    def ospf_area_type(self, args, negate, kind):
        area = args[0]
        if not (area.isdigit() or valid_ip(area)) or area in ("0", "0.0.0.0"):
            raise CommandError("% OSPF: Backbone can not be configured as stub/NSSA area" if area in ("0", "0.0.0.0")
                               else INVALID)
        if negate:
            self._ospf().area_types.pop(area, None)
        else:
            self._ospf().area_types[area] = kind

    def rtr_passive(self, args, negate):
        proc = self._process()
        if args[0].strip().lower() == "default":
            proc.passive_default = not negate
            if negate:
                proc.no_passive.clear()
            return
        canonical = normalize_iface(args[0])
        if canonical is None or canonical not in self.device.interfaces:
            raise CommandError(INVALID)
        if negate:
            proc.passive.discard(canonical)
            if proc.passive_default:
                proc.no_passive.add(canonical)
        else:
            proc.passive.add(canonical)
            proc.no_passive.discard(canonical)

    def rtr_redistribute(self, args, negate):
        words = args[0].split()
        if not words or words[0].lower() not in ("static", "connected", "ospf", "eigrp", "rip"):
            raise CommandError(INVALID)
        text = " ".join([words[0].lower(), *words[1:]])
        proc = self._process()
        proc.redistribute = [r for r in proc.redistribute if r.split()[0] != words[0].lower()]
        if not negate:
            proc.redistribute.append(text)

    def rtr_auto_summary(self, args, negate):
        self._process().auto_summary = not negate

    def rtr_default(self, args, negate):
        proc = self._process()
        proc.default_originate = not negate
        if isinstance(proc, OspfProcess) and negate:
            proc.default_originate_always = False

    def eigrp_network(self, args, negate):
        net, wild = args[0], args[1].strip() or None
        if not valid_ip(net) or (wild is not None and not valid_ip(wild)):
            raise CommandError(INVALID)
        proc = self.device.eigrp[self.eigrp_asn]
        entry = (net, wild)
        if negate:
            proc.networks = [n for n in proc.networks if n != entry and not (wild is None and n[0] == net)]
        elif entry not in proc.networks:
            proc.networks.append(entry)

    def eigrp_router_id(self, args, negate):
        if not negate and not valid_ip(args[0]):
            raise CommandError(INVALID)
        self.device.eigrp[self.eigrp_asn].router_id = None if negate else args[0]

    def rip_version(self, args, negate):
        self.device.rip.version = 1 if negate else self._number(args[0], 1, 2)

    def rip_network(self, args, negate):
        if not valid_ip(args[0]):
            raise CommandError(INVALID)
        net = classful_network(args[0])
        nets = self.device.rip.networks
        if negate:
            if net in nets:
                nets.remove(net)
        elif net not in nets:
            nets.append(net)

    # -- DHCP ----------------------------------------------------------------

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
        servers = args[0].split()
        if not negate and (not servers or not all(valid_ip(s) for s in servers)):
            raise CommandError(INVALID)
        self._pool().dns_server = None if negate else " ".join(servers)

    def dhcp_domain(self, args, negate):
        self._pool().domain_name = None if negate else args[0]

    def dhcp_lease(self, args, negate):
        words = args[0].split()
        if not negate and not (words == ["infinite"] or (1 <= len(words) <= 3 and all(w.isdigit() for w in words))):
            raise CommandError(INVALID)
        self._pool().lease = None if negate else " ".join(words)

    # -- ACL -----------------------------------------------------------------

    def acl_entry(self, action, args, negate, seq: int | None = None):
        entry = _normalize_acl_entry([action] + args[0].split())
        name = self.acl_name
        entries = self.device.acls[name]
        seqs = self.device.acl_seqs(name)
        offset = 1 if entries and entries[0] == "__ext__" else 0
        real = entries[offset:]
        if negate:
            if entry in real:
                index = real.index(entry)
                del entries[offset + index]
                del seqs[index]
            return
        if seq is None:
            seq = (seqs[-1] if seqs else 0) + 10
        elif seq in seqs:
            raise CommandError("% Duplicate sequence number")
        index = sum(1 for s in seqs if s < seq)
        entries.insert(offset + index, entry)
        seqs.insert(index, seq)

    def acl_sequenced(self, args, negate):
        """``15 permit host 10.0.0.1`` (insertion) ou ``no 20`` (suppression par numéro)."""
        seq, rest = int(args[0]), args[1].split()
        if negate and not rest:
            name = self.acl_name
            seqs = self.device.acl_seqs(name)
            if seq in seqs:
                index = seqs.index(seq)
                entries = self.device.acls[name]
                del entries[index + (1 if entries and entries[0] == "__ext__" else 0)]
                del seqs[index]
            return
        if not rest or rest[0].lower() not in ("permit", "deny", "remark") or not 1 <= seq <= 2147483647:
            raise CommandError(INVALID)
        self.acl_entry(rest[0].lower(), [" ".join(rest[1:])], negate, seq)


def _strip_level(text: str) -> str:
    words = text.split()
    if len(words) > 1 and words[0] in ("0", "5", "7", "8", "9"):
        words = words[1:]
    return " ".join(words)


ACL_KEYWORDS = {"permit", "deny", "host", "any", "ip", "tcp", "udp", "icmp", "eq", "neq", "gt", "lt", "range",
                "remark", "log", "established", "echo", "echo-reply", "ospf", "eigrp", "esp", "gre"}


def _normalize_acl_entry(words: list[str]) -> str:
    return " ".join(w.lower() if w.lower() in ACL_KEYWORDS else w for w in words)


def expand_range(text: str) -> list[str]:
    """``fa0/1 - 5, fa0/10`` -> [FastEthernet0/1, ..., FastEthernet0/5, FastEthernet0/10]."""
    names: list[str] = []
    for part in text.split(","):
        part = part.replace(" ", "")
        if not part:
            continue
        match = re.match(r"^([A-Za-z-]+)([\d/]+/)(\d+)(?:-(\d+))?$", part)
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


ERROR_MARKERS = ("% Invalid", "% Incomplete", "% Ambiguous", "% Unrecognized", "% Please", "Command rejected",
                 "% Bridge Priority", "% Hostname", "% Configuring", "% Password too short", "% Duplicate",
                 "% Address", "% OSPF", "% Port Priority", "% VTP")


def is_error(output: str) -> bool:
    return output.startswith(ERROR_MARKERS)


def apply_commands(device: Device, commands: str | list[str]) -> Session:
    """Applique une suite de commandes (depuis le mode privilégié) et renvoie la session."""
    session = Session(device)
    session.mode = "exec"
    lines = commands.splitlines() if isinstance(commands, str) else commands
    for line in lines:
        output = session.execute(line)
        if is_error(output):
            raise ValueError(f"commande refusée : {line!r} -> {output}")
    return session
