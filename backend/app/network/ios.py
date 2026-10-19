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
    "tunnel": "Tunnel",
    "null": "Null",
}
IFACE_SHORT = {"FastEthernet": "Fa", "GigabitEthernet": "Gi", "Serial": "Se", "Vlan": "Vlan", "Loopback": "Lo",
               "Port-channel": "Po", "Tunnel": "Tu", "Null": "Nu"}
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
    # OSPF : type de réseau, timers et authentification par interface
    ospf_network: str | None = None  # "point-to-point", "broadcast", "non-broadcast"...
    ospf_hello: int | None = None
    ospf_dead: int | None = None
    ospf_auth: str | None = None  # "message-digest", "" (texte clair) ou "null"
    ospf_auth_key: str | None = None
    ospf_md5_keys: dict[int, str] = field(default_factory=dict)
    ospfv3_area: tuple[int, str] | None = None  # « ipv6 ospf 1 area 0 »
    ospfv3_cost: int | None = None
    eigrp_summaries: list[tuple[int, str, str]] = field(default_factory=list)  # (AS, réseau, masque)
    # IPv6 : annonces de routeur et DHCPv6
    ipv6_nd_managed: bool = False
    ipv6_nd_other: bool = False
    ipv6_ra_suppress: bool = False
    ipv6_dhcp_server: str | None = None
    ipv6_autoconfig: bool = False
    ipv6_traffic_filter: dict[str, str] = field(default_factory=dict)  # "in"/"out" -> ACL IPv6
    # sécurité des ports (compléments)
    port_security_aging_time: int | None = None
    port_security_aging_type: str | None = None  # None = absolute
    port_security_macs: list[str] = field(default_factory=list)
    ip_verify_source: str | None = None  # "" (IP seule) ou "port-security" (IP + MAC)
    # services de niveau 3
    policy_route_map: str | None = None  # PBR
    vrf: str | None = None
    crypto_map: str | None = None
    service_policies: dict[str, str] = field(default_factory=dict)  # "input"/"output" -> policy-map
    tunnel_source: str | None = None
    tunnel_destination: str | None = None
    tunnel_mode: str | None = None  # None = « gre ip »
    tunnel_protection: str | None = None
    ip_mtu: int | None = None
    tcp_mss: int | None = None
    keepalive: str | None = None

    @property
    def short(self) -> str:
        kind = IFACE_KIND.match(self.name).group(0)
        return IFACE_SHORT.get(kind, kind) + self.name[len(kind):]

    @property
    def is_physical(self) -> bool:
        return not self.name.startswith(("Vlan", "Loopback", "Port-channel", "Tunnel", "Null")) and "." not in self.name

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
    ipv6_access_class: dict[str, str] = field(default_factory=dict)
    authorization_exec: str | None = None
    accounting_exec: str | None = None


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

    def redist(self, source: str) -> str | None:
        """Ligne de redistribution d'une source (« static », « eigrp »...) ou None."""
        return next((r for r in self.redistribute if r.split()[0] == source.lower()), None)


@dataclass
class OspfProcess(RoutingProcess):
    pid: int
    router_id: str | None = None
    networks: list[tuple[str, str, str]] = field(default_factory=list)  # (réseau, wildcard, zone)
    default_originate_always: bool = False
    reference_bandwidth: int | None = None
    area_types: dict[str, str] = field(default_factory=dict)  # zone -> "stub", "stub no-summary", "nssa"
    area_auth: dict[str, str] = field(default_factory=dict)  # zone -> "message-digest" ou "" (texte clair)


@dataclass
class Ospfv3Process(RoutingProcess):
    pid: int
    router_id: str | None = None
    area_types: dict[str, str] = field(default_factory=dict)
    reference_bandwidth: int | None = None


@dataclass
class EigrpProcess(RoutingProcess):
    asn: int
    router_id: str | None = None
    networks: list[tuple[str, str | None]] = field(default_factory=list)  # (réseau, wildcard ou None)
    auto_summary: bool = True
    stub: str | None = None  # « connected summary » pour « eigrp stub » sans option
    variance: int | None = None
    maximum_paths: int | None = None


@dataclass
class RipProcess(RoutingProcess):
    version: int = 1
    networks: list[str] = field(default_factory=list)  # réseaux par classe, comme IOS les enregistre
    auto_summary: bool = True


@dataclass
class BgpNeighbor:
    address: str
    remote_as: int
    description: str | None = None
    password: str | None = None
    update_source: str | None = None
    ebgp_multihop: int | None = None
    next_hop_self: bool = False
    shutdown: bool = False
    route_maps: dict[str, str] = field(default_factory=dict)  # "in"/"out" -> route-map
    prefix_lists: dict[str, str] = field(default_factory=dict)  # "in"/"out" -> prefix-list


@dataclass(kw_only=True)
class BgpProcess(RoutingProcess):
    asn: int
    router_id: str | None = None
    log_neighbor_changes: bool = False
    neighbors: dict[str, BgpNeighbor] = field(default_factory=dict)
    networks: list[tuple[str, str]] = field(default_factory=list)  # (réseau, masque)

    def has_network(self, network: str, mask: str) -> bool:
        return (network, mask) in self.networks


@dataclass
class RouteMapEntry:
    action: str = "permit"
    matches: list[str] = field(default_factory=list)
    sets: list[str] = field(default_factory=list)
    description: str | None = None


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
        # -- gestion et services de base --
        self.banner_login: str | None = None
        self.banner_exec: str | None = None
        self.service_timestamps = {"debug": "datetime msec", "log": "datetime msec"}
        self.clock_summer_time: str | None = None
        self.ip_hosts: dict[str, str] = {}
        self.mac_static: list[tuple[str, int, str]] = []  # (mac, vlan, interface)
        self.mac_aging: int | None = None
        self.archive: dict[str, object] = {}  # path, write_memory, time_period, maximum
        self.archive_copies: list[str] = []
        self.backups: list[str] = []  # destinations des « copy running-config tftp:... »
        self.source_route = True
        self.tcp_keepalives_in = False
        self.tcp_keepalives_out = False
        self.privileges: list[tuple[str, int, str]] = []  # (mode, niveau, commande)
        self.logging_console: str | None = "debugging"
        self.logging_source: str | None = None
        # -- NTP authentifié --
        self.ntp_authenticate = False
        self.ntp_keys: dict[int, str] = {}
        self.ntp_trusted: set[int] = set()
        self.ntp_server_options: dict[str, str] = {}
        self.ntp_source: str | None = None
        self.ssh_source: str | None = None
        # -- commutation --
        self.mst_name: str | None = None
        self.mst_revision = 0
        self.mst_instances: dict[int, set[int]] = {}
        self.mst_priority: dict[int, int] = {}
        self.monitor_sessions: dict[int, dict] = {}  # n -> {"sources": [(if, sens)], "vlans": [...], "dest": if}
        self.ip_source_bindings: list[tuple[str, int, str, str]] = []  # (mac, vlan, ip, interface)
        # -- routage avancé --
        self.ospfv3: dict[int, Ospfv3Process] = {}
        self.bgp: BgpProcess | None = None
        self.prefix_lists: dict[str, list[tuple[int, str, str, int | None, int | None]]] = {}
        self.route_maps: dict[str, dict[int, RouteMapEntry]] = {}
        self.local_policy: str | None = None
        self.vrfs: dict[str, dict] = {}  # nom -> {"rd": ..., "style": "ip vrf"/"definition", "ipv4": bool}
        self.vrf_routes: list[tuple[str, str, str, str]] = []  # (vrf, réseau, masque, saut suivant)
        self.dhcpv6_pools: dict[str, dict] = {}
        self.ipv6_acls: dict[str, list[str]] = {}
        # -- AAA et supervision --
        self.aaa_authorization: dict[str, str] = {}
        self.aaa_accounting: dict[str, str] = {}
        self.radius_servers: dict[str, dict] = {}
        self.tacacs_servers: dict[str, dict] = {}
        self.aaa_groups: dict[str, dict] = {}  # nom -> {"type": "radius"/"tacacs+", "servers": [...]}
        self.radius_source: str | None = None
        self.tacacs_source: str | None = None
        self.snmp_views: dict[str, list[tuple[str, str]]] = {}
        self.snmp_groups: dict[str, dict] = {}
        self.snmp_users: dict[str, dict] = {}
        self.snmp_traps: list[str] = []
        self.snmp_trap_source: str | None = None
        # -- VPN et QoS --
        self.isakmp_policies: dict[int, dict] = {}
        self.isakmp_keys: dict[str, str] = {}  # pair -> clé
        self.transform_sets: dict[str, dict] = {}
        self.crypto_maps: dict[str, dict[int, dict]] = {}
        self.ipsec_profiles: dict[str, dict] = {}
        self.class_maps: dict[str, dict] = {}  # nom -> {"type": "match-all"/"match-any", "matches": [...]}
        self.policy_maps: dict[str, dict[str, list[str]]] = {}  # nom -> classe -> actions
        self.control_plane_policy: str | None = None
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

    def rmap(self, name: str, seq: int | None = None) -> RouteMapEntry:
        """Entrée d'une route-map (la première si ``seq`` est omis)."""
        entries = self.route_maps[name]
        return entries[seq] if seq is not None else entries[min(entries)]

    def plist(self, name: str) -> list[str]:
        """Entrées d'une prefix-list sans leur numéro : ``["permit 10.0.0.0/8 le 24"]``."""
        return [_plist_text(e) for e in self.prefix_lists.get(name, [])]

    def has_vrf_route(self, vrf: str, network: str, mask: str, next_hop: str | None = None) -> bool:
        return any(r[:3] == (vrf, network, mask) and (next_hop is None or r[3] == _canonical_hop(next_hop))
                   for r in self.vrf_routes)

    @property
    def saved(self) -> bool:
        return self.startup_config is not None and self.startup_config == self.running_config()

    # -- génération de la configuration --------------------------------------

    def running_config(self) -> str:
        out = ["!", "version 15.2", "no service pad",
               f"service timestamps debug {self.service_timestamps['debug']}",
               f"service timestamps log {self.service_timestamps['log']}"]
        out.append("service password-encryption" if self.password_encryption else "no service password-encryption")
        if self.tcp_keepalives_in:
            out.append("service tcp-keepalives-in")
        if self.tcp_keepalives_out:
            out.append("service tcp-keepalives-out")
        out += ["!", f"hostname {self.hostname}", "!"]
        if self.logging_buffered:
            out.append(f"logging buffered {self.logging_buffered}")
        if self.logging_console is None:
            out.append("no logging console")
        elif self.logging_console != "debugging":
            out.append(f"logging console {self.logging_console}")
        if self.enable_secret:
            out.append(f"enable secret 5 {_fake_hash(self.enable_secret)}")
        if self.enable_password:
            pwd = _type7(self.enable_password) if self.password_encryption else self.enable_password
            out.append(f"enable password {'7 ' if self.password_encryption else ''}{pwd}")
        if self.aaa_new_model:
            out += ["!", "aaa new-model"]
            for name, group in self.aaa_groups.items():
                out.append(f"aaa group server {group['type']} {name}")
                out += [f" server name {server}" for server in group["servers"]]
            out += [f"aaa authentication {key} {methods}" for key, methods in self.aaa_authentication.items()]
            out += [f"aaa authorization {key} {methods}" for key, methods in self.aaa_authorization.items()]
            out += [f"aaa accounting {key} {methods}" for key, methods in self.aaa_accounting.items()]
        if self.clock_timezone:
            out.append(f"clock timezone {self.clock_timezone[0]} {self.clock_timezone[1]}")
        if self.clock_summer_time:
            out.append(f"clock summer-time {self.clock_summer_time}")
        if self.min_password_length:
            out.append(f"security passwords min-length {self.min_password_length}")
        for name, user in self.users.items():
            if user.get("secret"):
                out.append(f"username {name} privilege {user.get('privilege', 1)} secret 5 {_fake_hash(user['secret'])}")
            else:
                out.append(f"username {name} privilege {user.get('privilege', 1)} password {user.get('password', '')}")
        if self.archive:
            out += ["!", "archive"]
            if self.archive.get("path"):
                out.append(f" path {self.archive['path']}")
            if self.archive.get("maximum"):
                out.append(f" maximum {self.archive['maximum']}")
            if self.archive.get("write_memory"):
                out.append(" write-memory")
            if self.archive.get("time_period"):
                out.append(f" time-period {self.archive['time_period']}")
        out.append("!")
        if self.login_block:
            out.append("login block-for {} attempts {} within {}".format(*self.login_block))
        if not self.domain_lookup:
            out.append("no ip domain-lookup")
        if self.domain_name:
            out.append(f"ip domain-name {self.domain_name}")
        if self.name_servers:
            out.append("ip name-server " + " ".join(self.name_servers))
        out += [f"ip host {name} {ip}" for name, ip in self.ip_hosts.items()]
        if not self.source_route:
            out.append("no ip source-route")
        for name, vrf in self.vrfs.items():
            out.append(f"ip vrf {name}" if vrf["style"] == "ip vrf" else f"vrf definition {name}")
            if vrf.get("description"):
                out.append(f" description {vrf['description']}")
            if vrf.get("rd"):
                out.append(f" rd {vrf['rd']}")
            out += [f" route-target {rt}" for rt in vrf.get("route_targets", [])]
            for family in ("ipv4", "ipv6"):
                if vrf.get(family):
                    out += [" !", f" address-family {family}", " exit-address-family"]
            out.append("!")
        if self.ssh_version:
            out.append(f"ip ssh version {self.ssh_version}")
        if self.ssh_timeout:
            out.append(f"ip ssh time-out {self.ssh_timeout}")
        if self.ssh_retries:
            out.append(f"ip ssh authentication-retries {self.ssh_retries}")
        if self.ssh_source:
            out.append(f"ip ssh source-interface {self.ssh_source}")
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
        for name, pool6 in self.dhcpv6_pools.items():
            out.append(f"ipv6 dhcp pool {name}")
            if pool6.get("address_prefix"):
                out.append(f" address prefix {pool6['address_prefix'].upper()}")
            out += [f" dns-server {server.upper()}" for server in pool6.get("dns", [])]
            if pool6.get("domain"):
                out.append(f" domain-name {pool6['domain']}")
        for mac, vlan, ip, iface in self.ip_source_bindings:
            out.append(f"ip source binding {mac} vlan {vlan} {ip} interface {iface}")
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
            if self.mst_name or self.mst_revision or self.mst_instances:
                out += ["!", "spanning-tree mst configuration"]
                if self.mst_name:
                    out.append(f" name {self.mst_name}")
                if self.mst_revision:
                    out.append(f" revision {self.mst_revision}")
                out += [f" instance {inst} vlan {format_vlan_list(vlans)}"
                        for inst, vlans in sorted(self.mst_instances.items())]
                out.append("!")
            for inst, prio in sorted(self.mst_priority.items()):
                out.append(f"spanning-tree mst {inst} priority {prio}")
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
        if self.mac_aging is not None:
            out.append(f"mac address-table aging-time {self.mac_aging}")
        for mac, vlan, iface in self.mac_static:
            out.append(f"mac address-table static {mac} vlan {vlan} interface {iface}")
        out += self._crypto_lines()
        out += self._qos_lines()
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
        if self.local_policy:
            out.append(f"ip local policy route-map {self.local_policy}")
        out.append("ip http server" if self.http_server else "no ip http server")
        out.append("ip http secure-server" if self.https_server else "no ip http secure-server")
        out.append("!")
        for rule in self.nat_rules:
            out.append(rule)
        for route in self.static_routes:
            distance = self.route_distances.get(route)
            out.append("ip route {} {} {}".format(*route) + (f" {distance}" if distance else ""))
        for vrf, net, mask, nh in self.vrf_routes:
            out.append(f"ip route vrf {vrf} {net} {mask} {nh}")
        for prefix, nh, distance in self.ipv6_routes:
            out.append(f"ipv6 route {prefix.upper()} {nh.upper() if ':' in nh else nh}"
                       + (f" {distance}" if distance != 1 else ""))
        out.append("!")
        for name, entries in self.prefix_lists.items():
            out += [f"ip prefix-list {name} seq {e[0]} {_plist_text(e)}" for e in entries]
        for name, entries in self.acls.items():
            real = [e for e in entries if e != "__ext__"]
            if name.isdigit():
                out += [f"access-list {name} {entry}" for entry in real]
            else:
                kind = "extended" if entries and entries[0].startswith("__ext__") else "standard"
                out.append(f"ip access-list {kind} {name}")
                out += [f" {seq} {e}" for seq, e in zip(self.acl_seqs(name), real)]
        for name, entries in self.ipv6_acls.items():
            out.append(f"ipv6 access-list {name}")
            out += [f" {e}" for e in entries]
        for name, entries in self.route_maps.items():
            for seq, entry in sorted(entries.items()):
                out.append(f"route-map {name} {entry.action} {seq}")
                if entry.description:
                    out.append(f" description {entry.description}")
                out += [f" match {m}" for m in entry.matches]
                out += [f" set {x}" for x in entry.sets]
                out.append("!")
        if self.logging_trap:
            out.append(f"logging trap {self.logging_trap}")
        if self.logging_source:
            out.append(f"logging source-interface {self.logging_source}")
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
        if self.snmp_views or self.snmp_groups or self.snmp_traps or self.snmp_trap_source:
            out.append("!")
            for name, entries in self.snmp_views.items():
                out += [f"snmp-server view {name} {oid} {kind}" for oid, kind in entries]
            for name, group in self.snmp_groups.items():
                out.append(f"snmp-server group {name} v3 {group['level']}"
                           + "".join(f" {k} {group[k]}" for k in ("read", "write", "notify", "access") if group.get(k)))
            if self.snmp_trap_source:
                out.append(f"snmp-server trap-source {self.snmp_trap_source}")
            out += [f"snmp-server enable traps{' ' + t if t else ''}" for t in self.snmp_traps]
        for name, server in self.radius_servers.items():
            out += ["!", f"radius server {name}"]
            if server.get("address"):
                out.append(f" address ipv4 {server['address']} auth-port {server['auth_port']} "
                           f"acct-port {server['acct_port']}")
            if server.get("key"):
                out.append(f" key {server['key']}")
        for name, server in self.tacacs_servers.items():
            out += ["!", f"tacacs server {name}"]
            if server.get("address"):
                out.append(f" address ipv4 {server['address']}")
            if server.get("key"):
                out.append(f" key {server['key']}")
        if self.radius_source:
            out.append(f"ip radius source-interface {self.radius_source}")
        if self.tacacs_source:
            out.append(f"ip tacacs source-interface {self.tacacs_source}")
        if self.control_plane_policy:
            out += ["!", "control-plane", f" service-policy input {self.control_plane_policy}"]
        for banner in ("motd", "login", "exec"):
            text = getattr(self, f"banner_{banner}")
            if text:
                out += ["!", f"banner {banner} ^C{text}^C"]
        out.append("!")
        for kind, label in (("console", "line con 0"), ("vty", "line vty 0 4" if self.kind == "router" else "line vty 0 15")):
            out.append(label)
            out += self._line_lines(self.lines[kind])
        for privilege in self.privileges:
            out.append("privilege {} level {} {}".format(*privilege))
        for n, mon in sorted(self.monitor_sessions.items()):
            out += [f"monitor session {n} source interface {src}{' ' + way if way != 'both' else ''}"
                    for src, way in mon.get("sources", [])]
            out += [f"monitor session {n} source vlan {vlans}" for vlans in mon.get("vlans", [])]
            if mon.get("dest"):
                out.append(f"monitor session {n} destination interface {mon['dest']}")
        if self.ntp_authenticate:
            out += ["!", "ntp authenticate"]
        out += [f"ntp authentication-key {k} md5 {v}" for k, v in sorted(self.ntp_keys.items())]
        out += [f"ntp trusted-key {k}" for k in sorted(self.ntp_trusted)]
        if self.ntp_source:
            out.append(f"ntp source {self.ntp_source}")
        if self.ntp_master:
            out += ["!", f"ntp master {self.ntp_master}"]
        if self.ntp_servers:
            out += ["!"] + [f"ntp server {server}" + (f" {self.ntp_server_options[server]}"
                                                      if self.ntp_server_options.get(server) else "")
                            for server in self.ntp_servers]
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
            if proc.variance:
                out.append(f" variance {proc.variance}")
            if proc.maximum_paths:
                out.append(f" maximum-paths {proc.maximum_paths}")
            if not proc.auto_summary:
                out.append(" no auto-summary")
            if proc.stub:
                out.append(f" eigrp stub {proc.stub}")
            out.append("!")
        for pid, proc in sorted(self.ospf.items()):
            out.append(f"router ospf {pid}")
            if proc.router_id:
                out.append(f" router-id {proc.router_id}")
            if proc.reference_bandwidth:
                out.append(f" auto-cost reference-bandwidth {proc.reference_bandwidth}")
            out += [f" area {area} authentication{' ' + kind if kind else ''}" for area, kind in proc.area_auth.items()]
            out += [f" area {area} {kind}" for area, kind in proc.area_types.items()]
            out += [f" redistribute {r}" for r in proc.redistribute]
            out += proc.passive_lines()
            out += [f" network {net} {wild} area {area}" for net, wild, area in proc.networks]
            if proc.default_originate:
                out.append(" default-information originate" + (" always" if proc.default_originate_always else ""))
            out.append("!")
        for pid, proc in sorted(self.ospfv3.items()):
            out.append(f"ipv6 router ospf {pid}")
            if proc.router_id:
                out.append(f" router-id {proc.router_id}")
            if proc.reference_bandwidth:
                out.append(f" auto-cost reference-bandwidth {proc.reference_bandwidth}")
            out += [f" area {area} {kind}" for area, kind in proc.area_types.items()]
            out += proc.passive_lines()
            out += [f" redistribute {r}" for r in proc.redistribute]
            if proc.default_originate:
                out.append(" default-information originate")
            out.append("!")
        if self.bgp:
            bgp = self.bgp
            out.append(f"router bgp {bgp.asn}")
            if bgp.router_id:
                out.append(f" bgp router-id {bgp.router_id}")
            if bgp.log_neighbor_changes:
                out.append(" bgp log-neighbor-changes")
            for net, mask in bgp.networks:
                out.append(f" network {net} mask {mask}")
            out += [f" redistribute {r}" for r in bgp.redistribute]
            for nb in bgp.neighbors.values():
                out.append(f" neighbor {nb.address} remote-as {nb.remote_as}")
                if nb.description:
                    out.append(f" neighbor {nb.address} description {nb.description}")
                if nb.password:
                    out.append(f" neighbor {nb.address} password {nb.password}")
                if nb.ebgp_multihop:
                    out.append(f" neighbor {nb.address} ebgp-multihop {nb.ebgp_multihop}")
                if nb.update_source:
                    out.append(f" neighbor {nb.address} update-source {nb.update_source}")
                if nb.next_hop_self:
                    out.append(f" neighbor {nb.address} next-hop-self")
                if nb.shutdown:
                    out.append(f" neighbor {nb.address} shutdown")
                out += [f" neighbor {nb.address} prefix-list {n} {d}" for d, n in sorted(nb.prefix_lists.items())]
                out += [f" neighbor {nb.address} route-map {n} {d}" for d, n in sorted(nb.route_maps.items())]
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

    def _crypto_lines(self) -> list[str]:
        out = []
        for prio, pol in sorted(self.isakmp_policies.items()):
            out.append(f"crypto isakmp policy {prio}")
            for key in ("encryption", "hash", "authentication", "group", "lifetime"):
                if pol.get(key):
                    out.append(f" {'encr' if key == 'encryption' else key} {pol[key]}")
            out.append("!")
        out += [f"crypto isakmp key {key} address {peer}" for peer, key in self.isakmp_keys.items()]
        for name, ts in self.transform_sets.items():
            out.append(f"crypto ipsec transform-set {name} {' '.join(ts['transforms'])}")
            out.append(f" mode {ts.get('mode', 'tunnel')}")
        for name, prof in self.ipsec_profiles.items():
            out.append(f"crypto ipsec profile {name}")
            if prof.get("transform_set"):
                out.append(f" set transform-set {prof['transform_set']}")
            if prof.get("pfs"):
                out.append(f" set pfs {prof['pfs']}")
        for name, entries in self.crypto_maps.items():
            for seq, entry in sorted(entries.items()):
                out.append(f"crypto map {name} {seq} ipsec-isakmp")
                out += [f" set peer {peer}" for peer in entry.get("peers", [])]
                if entry.get("transform_set"):
                    out.append(f" set transform-set {entry['transform_set']}")
                if entry.get("pfs"):
                    out.append(f" set pfs {entry['pfs']}")
                if entry.get("lifetime"):
                    out.append(f" set security-association lifetime seconds {entry['lifetime']}")
                if entry.get("acl"):
                    out.append(f" match address {entry['acl']}")
        return out + (["!"] if out else [])

    def _qos_lines(self) -> list[str]:
        out = []
        for name, cmap in self.class_maps.items():
            out.append(f"class-map {cmap['type']} {name}")
            out += [f" match {m}" for m in cmap["matches"]]
            out.append("!")
        for name, classes in self.policy_maps.items():
            out.append(f"policy-map {name}")
            for cls, actions in classes.items():
                out.append(f" class {cls}")
                out += [f"  {a}" for a in actions]
            out.append("!")
        return out

    def _line_lines(self, line: Line) -> list[str]:
        out = [f" access-class {acl} {direction}" for direction, acl in sorted(line.access_class.items())]
        out += [f" ipv6 access-class {acl} {direction}" for direction, acl in sorted(line.ipv6_access_class.items())]
        if line.authorization_exec:
            out.append(f" authorization exec {line.authorization_exec}")
        if line.accounting_exec:
            out.append(f" accounting exec {line.accounting_exec}")
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
        if iface.vrf:
            vrf = self.vrfs.get(iface.vrf, {})
            lines.append(f"{'ip ' if vrf.get('style') == 'ip vrf' else ''}vrf forwarding {iface.vrf}")
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
        if iface.policy_route_map:
            lines.append(f"ip policy route-map {iface.policy_route_map}")
        if iface.ip_mtu:
            lines.append(f"ip mtu {iface.ip_mtu}")
        if iface.tcp_mss:
            lines.append(f"ip tcp adjust-mss {iface.tcp_mss}")
        if iface.ip_verify_source is not None:
            lines.append("ip verify source" + (f" {iface.ip_verify_source}" if iface.ip_verify_source else ""))
        if iface.ospf_network:
            lines.append(f"ip ospf network {iface.ospf_network}")
        if iface.ospf_hello:
            lines.append(f"ip ospf hello-interval {iface.ospf_hello}")
        if iface.ospf_dead:
            lines.append(f"ip ospf dead-interval {iface.ospf_dead}")
        if iface.ospf_auth is not None:
            lines.append("ip ospf authentication" + (f" {iface.ospf_auth}" if iface.ospf_auth else ""))
        if iface.ospf_auth_key:
            lines.append(f"ip ospf authentication-key {iface.ospf_auth_key}")
        for key_id, key in sorted(iface.ospf_md5_keys.items()):
            lines.append(f"ip ospf message-digest-key {key_id} md5 {key}")
        for asn, net, mask in iface.eigrp_summaries:
            lines.append(f"ip summary-address eigrp {asn} {net} {mask}")
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
        if iface.ipv6_autoconfig:
            lines.append("ipv6 address autoconfig")
        if iface.ipv6_nd_managed:
            lines.append("ipv6 nd managed-config-flag")
        if iface.ipv6_nd_other:
            lines.append("ipv6 nd other-config-flag")
        if iface.ipv6_ra_suppress:
            lines.append("ipv6 nd ra suppress all")
        if iface.ipv6_dhcp_server:
            lines.append(f"ipv6 dhcp server {iface.ipv6_dhcp_server}")
        for direction, name in sorted(iface.ipv6_traffic_filter.items()):
            lines.append(f"ipv6 traffic-filter {name} {direction}")
        if iface.ospfv3_area:
            lines.append(f"ipv6 ospf {iface.ospfv3_area[0]} area {iface.ospfv3_area[1]}")
        if iface.ospfv3_cost:
            lines.append(f"ipv6 ospf cost {iface.ospfv3_cost}")
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
        if iface.keepalive:
            lines.append(f"keepalive {iface.keepalive}")
        if iface.tunnel_source:
            lines.append(f"tunnel source {iface.tunnel_source}")
        if iface.tunnel_destination:
            lines.append(f"tunnel destination {iface.tunnel_destination}")
        if iface.tunnel_mode:
            lines.append(f"tunnel mode {iface.tunnel_mode}")
        if iface.tunnel_protection:
            lines.append(f"tunnel protection ipsec profile {iface.tunnel_protection}")
        if iface.crypto_map:
            lines.append(f"crypto map {iface.crypto_map}")
        for direction, name in sorted(iface.service_policies.items()):
            lines.append(f"service-policy {direction} {name}")
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
            lines += [f"switchport port-security mac-address {mac}" for mac in iface.port_security_macs]
            if iface.port_security_aging_time:
                lines.append(f"switchport port-security aging time {iface.port_security_aging_time}")
            if iface.port_security_aging_type:
                lines.append(f"switchport port-security aging type {iface.port_security_aging_type}")
        return lines


def default_vlan_name(vid: int) -> str:
    return "default" if vid == 1 else f"VLAN{vid:04d}"


def _fake_hash(secret: str) -> str:
    import hashlib

    return "$1$" + hashlib.md5(secret.encode()).hexdigest()[:4] + "$" + hashlib.md5(secret[::-1].encode()).hexdigest()[:22]


def _type7(password: str) -> str:
    return "".join(f"{(ord(c) ^ 0x5A):02X}" for c in password)[:24].rjust(4, "0")


def iface_sort_key(name: str):
    order = ["FastEthernet", "GigabitEthernet", "Serial", "Port-channel", "Loopback", "Tunnel", "Vlan"]
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


def _plist_text(entry: tuple[int, str, str, int | None, int | None]) -> str:
    _, action, prefix, ge, le = entry
    return f"{action} {prefix}" + (f" ge {ge}" if ge else "") + (f" le {le}" if le else "")


MAC_RE = re.compile(r"^[0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}$")


def valid_mac(text: str) -> bool:
    """Adresse MAC au format Cisco ``0011.2233.4455``."""
    return bool(MAC_RE.match(text.lower()))


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
    "acl6": "{h}(config-ipv6-acl)#",
    "archive": "{h}(config-archive)#",
    "mst": "{h}(config-mst)#",
    "dhcpv6": "{h}(config-dhcpv6)#",
    "ospfv3": "{h}(config-rtr)#",
    "bgp": "{h}(config-router)#",
    "route-map": "{h}(config-route-map)#",
    "vrf": "{h}(config-vrf)#",
    "vrf-def": "{h}(config-vrf)#",
    "vrf-af": "{h}(config-vrf-af)#",
    "radius": "{h}(config-radius-server)#",
    "tacacs": "{h}(config-server-tacacs)#",
    "aaa-group": "{h}(config-sg-radius)#",
    "isakmp": "{h}(config-isakmp)#",
    "crypto-trans": "{h}(cfg-crypto-trans)#",
    "crypto-map": "{h}(config-crypto-map)#",
    "ipsec-profile": "{h}(ipsec-profile)#",
    "cmap": "{h}(config-cmap)#",
    "pmap": "{h}(config-pmap)#",
    "pmap-c": "{h}(config-pmap-c)#",
    "cp": "{h}(config-cp)#",
}

# Sous-modes imbriqués : « exit » y ramène au mode parent, et une commande inconnue y est
# d'abord cherchée dans le mode parent (comme « class » dans un policy-map).
PARENT_MODES = {"pmap-c": "pmap", "vrf-af": "vrf-def"}

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
        self.ctx: dict = {}  # contexte des sous-modes ajoutés (route-map, policy-map, crypto map...)
        self.history: list[str] = []
        self.rules = self._build_rules()

    @property
    def prompt(self) -> str:
        mode = self.mode
        if mode == "if" and self.ifaces and "." in self.ifaces[0]:
            mode = "subif"
        if mode == "aaa-group" and self.ctx.get("group_type") == "tacacs+":
            return f"{self.device.hostname}(config-sg-tacacs+)#"
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
                found = None
                parent = PARENT_MODES.get(mode)
                if parent:
                    try:
                        found = match_rules(self.rules[parent], tokens)
                        self.mode = parent
                    except CommandError:
                        found = None
                if found is None:
                    try:
                        found = match_rules(self.rules["config"], tokens)
                    except CommandError:
                        raise first_error from None
                    self._exit_to_config()
                rule, args = found
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
        self.ctx = {}

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
            R(["show", "mac", "address-table"], self.show_mac, "Table des adresses MAC"),
            R(["show", "mac", "address-table", "static"], self.show_mac, "Adresses MAC statiques"),
            R(["show", "hosts"], self.show_hosts, "Noms d'hôtes connus"),
            R(["show", "clock"], self.show_clock, "Horloge"),
            R(["show", "archive"], self.show_archive, "Archives de configuration"),
            R(["show", "monitor"], self.show_monitor, "Sessions SPAN"),
            R(["show", "monitor", "session", "<rest>"], self.show_monitor, "Sessions SPAN"),
            R(["show", "spanning-tree", "mst", "configuration"], self.show_mst, "Configuration MST"),
            R(["show", "spanning-tree", "mst"], self.show_mst, "Instances MST"),
            R(["show", "ipv6", "dhcp", "pool"], self.show_dhcpv6_pool, "Pools DHCPv6"),
            R(["show", "ip", "ospf", "interface", "<rest>"], self.show_ospf_interface, "Interfaces OSPF"),
            R(["show", "ip", "ospf", "neighbor"], self.show_ospf_neighbor, "Voisins OSPF"),
            R(["show", "ipv6", "protocols"], self.show_ipv6_protocols, "Protocoles de routage IPv6"),
            R(["show", "ipv6", "ospf", "interface", "<rest>"], self.show_ospfv3_interface, "Interfaces OSPFv3"),
            R(["show", "ip", "bgp"], self.show_bgp, "Table BGP"),
            R(["show", "ip", "bgp", "summary"], self.show_bgp_summary, "Résumé BGP"),
            R(["show", "ip", "prefix-list"], self.show_prefix_lists, "Listes de préfixes"),
            R(["show", "route-map"], self.show_route_maps, "Route-maps"),
            R(["show", "ip", "policy"], self.show_ip_policy, "Routage par politique (PBR)"),
            R(["show", "aaa", "servers"], self.show_aaa_servers, "Serveurs AAA"),
            R(["show", "snmp", "user"], self.show_snmp_user, "Utilisateurs SNMPv3"),
            R(["show", "snmp", "group"], self.show_snmp_group, "Groupes SNMPv3"),
            R(["show", "ip", "verify", "source"], self.show_verify_source, "IP Source Guard"),
            R(["show", "ip", "source", "binding"], self.show_source_binding, "Liaisons IP Source Guard"),
            R(["show", "crypto", "isakmp", "policy"], self.show_isakmp, "Politiques ISAKMP (IKE phase 1)"),
            R(["show", "crypto", "map"], self.show_crypto_map, "Crypto maps"),
            R(["show", "crypto", "ipsec", "transform-set"], self.show_transform_sets, "Transform-sets IPsec"),
            R(["show", "class-map"], self.show_class_maps, "Classes de trafic"),
            R(["show", "policy-map"], self.show_policy_maps, "Politiques QoS"),
            R(["show", "policy-map", "interface", "<rest>"], self.show_policy_maps, "Politique appliquée"),
            R(["show", "ip", "vrf"], self.show_vrf, "VRF"),
            R(["show", "ip", "route", "vrf", "<name>"], self.show_ip_route_vrf, "Table de routage d'une VRF"),
            R(["show", "ipv6", "access-list"], self.show_ipv6_acls, "ACL IPv6"),
            R(["show", "interfaces", "<if>", "<rest>"], self.show_interface, "Détail d'une interface"),
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
            R(["copy", "running-config", "<dest>"], self.cmd_copy_remote, "Copier la configuration (tftp:, flash:...)"),
            R(["archive", "config"], self.cmd_archive_config, "Archiver la configuration courante"),
            R(["ping", "vrf", "<name>", "<ip>"], self.cmd_ping_vrf, "Tester la connectivité dans une VRF"),
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
            R(["service", "timestamps", "<rest>"], self.cfg_timestamps, "Horodatage des messages"),
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
            R(["banner", "login", "<rest>"], lambda a, n: self.cfg_banner(a, n, "login"), "Bannière avant l'authentification"),
            R(["banner", "exec", "<rest>"], lambda a, n: self.cfg_banner(a, n, "exec"), "Bannière après l'authentification"),
            R(["service", "tcp-keepalives-in"], lambda a, n: setattr(self.device, "tcp_keepalives_in", not n),
              "Détecter les sessions entrantes mortes"),
            R(["service", "tcp-keepalives-out"], lambda a, n: setattr(self.device, "tcp_keepalives_out", not n),
              "Détecter les sessions sortantes mortes"),
            R(["clock", "summer-time", "<name>", "<rest>"], self.cfg_summer_time, "Heure d'été"),
            R(["ip", "host", "<name>", "<rest>"], self.cfg_ip_host, "Table d'hôtes locale"),
            R(["ip", "source-route"], lambda a, n: setattr(self.device, "source_route", not n),
              "Routage par la source (à désactiver)"),
            R(["ip", "ssh", "source-interface", "<if>"], lambda a, n: self._set_source("ssh_source", a, n),
              "Interface source SSH"),
            R(["mac", "address-table", "static", "<mac>", "vlan", "<id>", "<rest>"], self.cfg_mac_static,
              "Adresse MAC statique"),
            R(["mac", "address-table", "aging-time", "<n>"], self.cfg_mac_aging, "Durée de vie des adresses MAC"),
            R(["archive"], self.cfg_archive, "Archivage de la configuration"),
            R(["privilege", "<mode>", "level", "<n>", "<rest>"], self.cfg_privilege, "Niveau de privilège d'une commande"),
            R(["logging", "console", "<rest>"], self.cfg_logging_console, "Messages sur la console"),
            R(["logging", "source-interface", "<if>"], lambda a, n: self._set_source("logging_source", a, n),
              "Interface source syslog"),
            R(["ntp", "authenticate"], lambda a, n: setattr(self.device, "ntp_authenticate", not n),
              "Exiger l'authentification NTP"),
            R(["ntp", "authentication-key", "<n>", "md5", "<rest>"], self.cfg_ntp_key, "Clé NTP"),
            R(["ntp", "trusted-key", "<n>"], self.cfg_ntp_trusted, "Clé NTP de confiance"),
            R(["ntp", "source", "<if>"], lambda a, n: self._set_source("ntp_source", a, n), "Interface source NTP"),
            R(["spanning-tree", "mst", "configuration"], self.cfg_mst_configuration, "Région MST"),
            R(["spanning-tree", "mst", "<inst>", "priority", "<n>"], self.cfg_mst_priority, "Priorité d'une instance MST"),
            R(["spanning-tree", "mst", "<inst>", "root", "<kind>"], self.cfg_mst_root, "Racine d'une instance MST"),
            R(["monitor", "session", "<n>", "<rest>"], self.cfg_monitor, "Session SPAN (recopie de ports)"),
            R(["ip", "source", "binding", "<mac>", "vlan", "<id>", "<ip>", "interface", "<if>"],
              self.cfg_source_binding, "Liaison statique IP Source Guard"),
            R(["ipv6", "dhcp", "pool", "<name>"], self.cfg_dhcpv6_pool, "Pool DHCPv6"),
            R(["ipv6", "router", "ospf", "<pid>"], self.cfg_ipv6_ospf, "Routage OSPFv3"),
            R(["ipv6", "access-list", "<name>"], self.cfg_ipv6_acl, "ACL IPv6"),
            R(["router", "bgp", "<as>"], self.cfg_router_bgp, "Routage BGP"),
            R(["ip", "prefix-list", "<name>", "<rest>"], self.cfg_prefix_list, "Liste de préfixes"),
            R(["route-map", "<name>", "<rest>"], self.cfg_route_map, "Route-map"),
            R(["ip", "local", "policy", "route-map", "<name>"], self.cfg_local_policy, "PBR du trafic du routeur"),
            R(["ip", "vrf", "<name>"], lambda a, n: self.cfg_vrf(a, n, "ip vrf"), "VRF (syntaxe ip vrf)"),
            R(["vrf", "definition", "<name>"], lambda a, n: self.cfg_vrf(a, n, "definition"), "VRF multi-protocole"),
            R(["ip", "route", "vrf", "<name>", "<net>", "<mask>", "<nh>", "<rest>"], self.cfg_vrf_route,
              "Route statique dans une VRF"),
            R(["aaa", "authentication", "enable", "default", "<rest>"], self.cfg_aaa_enable,
              "Authentification du mode privilégié"),
            R(["aaa", "authorization", "<rest>"], lambda a, n: self.cfg_aaa_other(a, n, "authorization"),
              "Autorisation AAA"),
            R(["aaa", "accounting", "<rest>"], lambda a, n: self.cfg_aaa_other(a, n, "accounting"), "Traçabilité AAA"),
            R(["aaa", "group", "server", "<type>", "<name>"], self.cfg_aaa_group, "Groupe de serveurs AAA"),
            R(["radius", "server", "<name>"], lambda a, n: self.cfg_aaa_server(a, n, "radius"), "Serveur RADIUS"),
            R(["tacacs", "server", "<name>"], lambda a, n: self.cfg_aaa_server(a, n, "tacacs"), "Serveur TACACS+"),
            R(["ip", "radius", "source-interface", "<if>"], lambda a, n: self._set_source("radius_source", a, n),
              "Interface source RADIUS"),
            R(["ip", "tacacs", "source-interface", "<if>"], lambda a, n: self._set_source("tacacs_source", a, n),
              "Interface source TACACS+"),
            R(["snmp-server", "view", "<name>", "<oid>", "<kind>"], self.cfg_snmp_view, "Vue SNMP"),
            R(["snmp-server", "group", "<name>", "<version>", "<rest>"], self.cfg_snmp_group, "Groupe SNMPv3"),
            R(["snmp-server", "user", "<name>", "<group>", "<version>", "<rest>"], self.cfg_snmp_user,
              "Utilisateur SNMPv3"),
            R(["snmp-server", "enable", "traps", "<rest>"], self.cfg_snmp_traps, "Activer les traps"),
            R(["snmp-server", "trap-source", "<if>"], lambda a, n: self._set_source("snmp_trap_source", a, n),
              "Interface source des traps"),
            R(["crypto", "isakmp", "policy", "<n>"], self.cfg_isakmp_policy, "Politique IKE phase 1"),
            R(["crypto", "isakmp", "key", "<rest>"], self.cfg_isakmp_key, "Clé pré-partagée IKE"),
            R(["crypto", "ipsec", "transform-set", "<name>", "<rest>"], self.cfg_transform_set,
              "Transform-set IPsec (phase 2)"),
            R(["crypto", "ipsec", "profile", "<name>"], self.cfg_ipsec_profile, "Profil IPsec (tunnel protégé)"),
            R(["crypto", "map", "<name>", "<seq>", "<rest>"], self.cfg_crypto_map, "Crypto map"),
            R(["class-map", "<rest>"], self.cfg_class_map, "Classe de trafic (QoS)"),
            R(["policy-map", "<name>"], self.cfg_policy_map, "Politique QoS"),
            R(["control-plane"], self.cfg_control_plane, "Plan de contrôle (CoPP)", negatable=False),
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
            R(["ip", "ospf", "network", "<type>"], self.if_ospf_network, "Type de réseau OSPF"),
            R(["ip", "ospf", "hello-interval", "<n>"], lambda a, n: self._if_num("ospf_hello", a, n, 1, 65535),
              "Intervalle hello OSPF"),
            R(["ip", "ospf", "dead-interval", "<n>"], lambda a, n: self._if_num("ospf_dead", a, n, 1, 65535),
              "Intervalle dead OSPF"),
            R(["ip", "ospf", "authentication", "<rest>"], self.if_ospf_auth, "Authentification OSPF"),
            R(["ip", "ospf", "authentication-key", "<rest>"], self.if_ospf_auth_key, "Clé OSPF en clair"),
            R(["ip", "ospf", "message-digest-key", "<n>", "md5", "<rest>"], self.if_ospf_md5, "Clé OSPF MD5"),
            R(["ip", "summary-address", "eigrp", "<as>", "<net>", "<mask>", "<rest>"], self.if_eigrp_summary,
              "Résumé EIGRP manuel"),
            R(["ip", "verify", "source", "<rest>"], self.if_verify_source, "IP Source Guard"),
            R(["ip", "policy", "route-map", "<name>"], self.if_policy, "Routage par politique (PBR)"),
            R(["ip", "vrf", "forwarding", "<name>"], self.if_vrf, "Placer l'interface dans une VRF"),
            R(["vrf", "forwarding", "<name>"], self.if_vrf, "Placer l'interface dans une VRF"),
            R(["ip", "mtu", "<n>"], lambda a, n: self._if_num("ip_mtu", a, n, 68, 9216), "MTU IP"),
            R(["ip", "tcp", "adjust-mss", "<n>"], lambda a, n: self._if_num("tcp_mss", a, n, 500, 1460),
              "Ajuster le MSS TCP"),
            R(["ipv6", "nd", "managed-config-flag"], lambda a, n: self._if_flag("ipv6_nd_managed", n),
              "Drapeau M : adresses par DHCPv6"),
            R(["ipv6", "nd", "other-config-flag"], lambda a, n: self._if_flag("ipv6_nd_other", n),
              "Drapeau O : autres informations par DHCPv6"),
            R(["ipv6", "nd", "ra", "suppress", "<rest>"], lambda a, n: self._if_flag("ipv6_ra_suppress", n),
              "Ne plus envoyer d'annonces de routeur"),
            R(["ipv6", "dhcp", "server", "<name>", "<rest>"], self.if_dhcpv6_server, "Serveur DHCPv6 sur l'interface"),
            R(["ipv6", "address", "autoconfig", "<rest>"], lambda a, n: self._if_flag("ipv6_autoconfig", n),
              "Adresse IPv6 par SLAAC"),
            R(["ipv6", "traffic-filter", "<name>", "<dir>"], self.if_traffic_filter, "Appliquer une ACL IPv6"),
            R(["ipv6", "ospf", "<pid>", "area", "<area>"], self.if_ospfv3_area, "Activer OSPFv3 sur l'interface"),
            R(["ipv6", "ospf", "cost", "<n>"], lambda a, n: self._if_num("ospfv3_cost", a, n, 1, 65535),
              "Coût OSPFv3"),
            R(["switchport", "port-security", "aging", "time", "<n>"], self.if_ps_aging_time,
              "Durée de vie des adresses sécurisées (minutes)"),
            R(["switchport", "port-security", "aging", "type", "<type>"], self.if_ps_aging_type, "Type de vieillissement"),
            R(["switchport", "port-security", "mac-address", "<mac>"], self.if_ps_mac, "Adresse MAC autorisée"),
            R(["tunnel", "source", "<rest>"], self.if_tunnel_source, "Source du tunnel"),
            R(["tunnel", "destination", "<ip>"], self.if_tunnel_destination, "Destination du tunnel"),
            R(["tunnel", "mode", "<rest>"], self.if_tunnel_mode, "Mode du tunnel"),
            R(["tunnel", "protection", "ipsec", "profile", "<name>"], self.if_tunnel_protection,
              "Chiffrer le tunnel avec IPsec"),
            R(["keepalive", "<rest>"], self.if_keepalive, "Keepalive"),
            R(["crypto", "map", "<name>"], self.if_crypto_map, "Appliquer une crypto map"),
            R(["service-policy", "<dir>", "<name>"], self.if_service_policy, "Appliquer une politique QoS"),
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
            R(["ipv6", "access-class", "<acl>", "<dir>"], self.line_ipv6_access_class, "Filtrer les accès IPv6"),
            R(["authorization", "exec", "<list>"], lambda a, n: self._line_aaa("authorization_exec", a, n),
              "Liste d'autorisation AAA"),
            R(["accounting", "exec", "<list>"], lambda a, n: self._line_aaa("accounting_exec", a, n),
              "Liste de traçabilité AAA"),
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
            R(["area", "<area>", "authentication", "<rest>"], self.ospf_area_auth, "Authentification de la zone"),
            exit_rule, end_rule,
        ]
        router_eigrp = [
            R(["network", "<net>", "<rest>"], self.eigrp_network, "Annoncer un réseau (wildcard optionnel)"),
            R(["eigrp", "router-id", "<ip>"], self.eigrp_router_id, "Identifiant du routeur"),
            R(["eigrp", "stub", "<rest>"], self.eigrp_stub, "Routeur stub"),
            R(["variance", "<n>"], lambda a, n: self._eigrp_num("variance", a, n, 1, 128),
              "Partage de charge à coûts inégaux"),
            R(["maximum-paths", "<n>"], lambda a, n: self._eigrp_num("maximum_paths", a, n, 1, 32),
              "Nombre de chemins installés"),
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
        archive = [
            R(["path", "<rest>"], self.archive_path, "Emplacement des archives ($h = nom d'hôte, $t = date)"),
            R(["write-memory"], lambda a, n: self._archive_set("write_memory", None if n else True),
              "Archiver à chaque sauvegarde"),
            R(["time-period", "<n>"], lambda a, n: self._archive_set("time_period", None if n else self._number(
                a[0], 1, 525600)), "Archiver périodiquement (minutes)"),
            R(["maximum", "<n>"], lambda a, n: self._archive_set("maximum", None if n else self._number(a[0], 1, 14)),
              "Nombre d'archives conservées"),
            exit_rule, end_rule,
        ]
        mst = [
            R(["name", "<name>"], self.mst_name_cmd, "Nom de la région"),
            R(["revision", "<n>"], self.mst_revision_cmd, "Numéro de révision"),
            R(["instance", "<n>", "vlan", "<rest>"], self.mst_instance_cmd, "Associer des VLAN à une instance"),
            R(["show", "current"], lambda a, n: self.show_mst([], False), "Configuration en cours d'édition"),
            exit_rule, end_rule,
        ]
        dhcpv6 = [
            R(["dns-server", "<ip>"], self.dhcpv6_dns, "Serveur DNS distribué"),
            R(["domain-name", "<name>"], self.dhcpv6_domain, "Domaine distribué"),
            R(["address", "prefix", "<prefix>", "<rest>"], self.dhcpv6_prefix, "Préfixe distribué (DHCPv6 avec état)"),
            exit_rule, end_rule,
        ]
        ospfv3 = [
            R(["router-id", "<ip>"], self.ospfv3_router_id, "Identifiant du routeur (format IPv4)"),
            passive_rule, redistribute_rule,
            R(["default-information", "originate", "<rest>"], self.rtr_default, "Propager la route par défaut"),
            R(["auto-cost", "reference-bandwidth", "<n>"], self.ospf_reference_bw, "Bande passante de référence"),
            R(["area", "<area>", "stub"], lambda a, n: self.ospf_area_type(a, n, "stub"), "Zone stub"),
            R(["area", "<area>", "stub", "no-summary"], lambda a, n: self.ospf_area_type(a, n, "stub no-summary"),
              "Zone totalement stub"),
            exit_rule, end_rule,
        ]
        bgp = [
            R(["bgp", "router-id", "<ip>"], self.bgp_router_id, "Identifiant BGP"),
            R(["bgp", "log-neighbor-changes"], self.bgp_log, "Journaliser les changements de voisins"),
            R(["neighbor", "<ip>", "remote-as", "<as>"], self.bgp_remote_as, "Déclarer un voisin"),
            R(["neighbor", "<ip>", "description", "<rest>"], lambda a, n: self.bgp_nb_attr(a, n, "description"),
              "Description du voisin"),
            R(["neighbor", "<ip>", "password", "<rest>"], lambda a, n: self.bgp_nb_attr(a, n, "password"),
              "Authentification MD5 de la session"),
            R(["neighbor", "<ip>", "update-source", "<if>"], lambda a, n: self.bgp_nb_attr(a, n, "update_source"),
              "Interface source de la session"),
            R(["neighbor", "<ip>", "ebgp-multihop", "<rest>"], lambda a, n: self.bgp_nb_attr(a, n, "ebgp_multihop"),
              "Voisin eBGP à plusieurs sauts"),
            R(["neighbor", "<ip>", "next-hop-self"], lambda a, n: self.bgp_nb_attr(a, n, "next_hop_self"),
              "Se donner comme saut suivant"),
            R(["neighbor", "<ip>", "shutdown"], lambda a, n: self.bgp_nb_attr(a, n, "shutdown"),
              "Suspendre la session"),
            R(["neighbor", "<ip>", "route-map", "<name>", "<dir>"], lambda a, n: self.bgp_nb_filter(a, n, "route_maps"),
              "Route-map sur le voisin"),
            R(["neighbor", "<ip>", "prefix-list", "<name>", "<dir>"],
              lambda a, n: self.bgp_nb_filter(a, n, "prefix_lists"), "Prefix-list sur le voisin"),
            R(["network", "<net>", "mask", "<mask>"], self.bgp_network, "Annoncer un préfixe"),
            R(["network", "<net>"], self.bgp_network, "Annoncer un réseau par classe"),
            redistribute_rule,
            exit_rule, end_rule,
        ]
        route_map = [
            R(["match", "<rest>"], self.rmap_match, "Condition"),
            R(["set", "<rest>"], self.rmap_set, "Action"),
            R(["description", "<rest>"], self.rmap_description, "Description"),
            exit_rule, end_rule,
        ]
        vrf_common = [
            R(["rd", "<rd>"], self.vrf_rd, "Route distinguisher (ASN:nn)"),
            R(["description", "<rest>"], self.vrf_description, "Description"),
            R(["route-target", "<rest>"], self.vrf_route_target, "Route-target (MPLS VPN)"),
            exit_rule, end_rule,
        ]
        vrf_def = vrf_common[:3] + [
            R(["address-family", "<family>"], self.vrf_address_family, "Activer une famille d'adresses"),
            exit_rule, end_rule,
        ]
        vrf_af = [
            R(["exit-address-family"], lambda a, n: setattr(self, "mode", "vrf-def"), "Quitter la famille d'adresses",
              negatable=False),
            R(["route-target", "<rest>"], self.vrf_route_target, "Route-target (MPLS VPN)"),
            exit_rule, end_rule,
        ]
        radius = [
            R(["address", "ipv4", "<ip>", "<rest>"], self.aaa_server_address, "Adresse du serveur"),
            R(["key", "<rest>"], self.aaa_server_key, "Secret partagé"),
            R(["timeout", "<n>"], lambda a, n: self._aaa_server_set("timeout", None if n else self._number(a[0], 1, 1000)),
              "Délai d'attente"),
            R(["retransmit", "<n>"], lambda a, n: self._aaa_server_set("retransmit", None if n else self._number(
                a[0], 0, 100)), "Nombre de retransmissions"),
            exit_rule, end_rule,
        ]
        tacacs = [
            R(["address", "ipv4", "<ip>"], lambda a, n: self.aaa_server_address(a + [""], n), "Adresse du serveur"),
            R(["key", "<rest>"], self.aaa_server_key, "Secret partagé"),
            R(["port", "<n>"], lambda a, n: self._aaa_server_set("port", None if n else self._number(a[0], 1, 65535)),
              "Port TCP"),
            R(["timeout", "<n>"], lambda a, n: self._aaa_server_set("timeout", None if n else self._number(a[0], 1, 1000)),
              "Délai d'attente"),
            exit_rule, end_rule,
        ]
        aaa_group = [
            R(["server", "name", "<name>"], self.aaa_group_server, "Ajouter un serveur au groupe"),
            exit_rule, end_rule,
        ]
        isakmp = [
            R(["encryption", "<rest>"], lambda a, n: self.isakmp_set("encryption", a, n), "Chiffrement"),
            R(["encr", "<rest>"], lambda a, n: self.isakmp_set("encryption", a, n), "Chiffrement"),
            R(["hash", "<alg>"], lambda a, n: self.isakmp_set("hash", a, n), "Intégrité"),
            R(["authentication", "<method>"], lambda a, n: self.isakmp_set("authentication", a, n), "Authentification"),
            R(["group", "<n>"], lambda a, n: self.isakmp_set("group", a, n), "Groupe Diffie-Hellman"),
            R(["lifetime", "<n>"], lambda a, n: self.isakmp_set("lifetime", a, n), "Durée de vie (secondes)"),
            exit_rule, end_rule,
        ]
        crypto_trans = [
            R(["mode", "<mode>"], self.transform_mode, "Mode tunnel ou transport"),
            exit_rule, end_rule,
        ]
        crypto_map = [
            R(["set", "peer", "<ip>"], self.cmap_peer, "Pair IPsec"),
            R(["set", "transform-set", "<name>"], lambda a, n: self.crypto_entry_set("transform_set", a, n),
              "Transform-set"),
            R(["set", "pfs", "<group>"], lambda a, n: self.crypto_entry_set("pfs", a, n), "Perfect Forward Secrecy"),
            R(["set", "security-association", "lifetime", "seconds", "<n>"],
              lambda a, n: self.crypto_entry_set("lifetime", a, n), "Durée de vie des SA"),
            R(["match", "address", "<acl>"], lambda a, n: self.crypto_entry_set("acl", a, n), "Trafic à chiffrer"),
            R(["description", "<rest>"], lambda a, n: self.crypto_entry_set("description", a, n), "Description"),
            exit_rule, end_rule,
        ]
        ipsec_profile = [
            R(["set", "transform-set", "<name>"], lambda a, n: self.crypto_entry_set("transform_set", a, n),
              "Transform-set"),
            R(["set", "pfs", "<group>"], lambda a, n: self.crypto_entry_set("pfs", a, n), "Perfect Forward Secrecy"),
            exit_rule, end_rule,
        ]
        cmap = [
            R(["match", "<rest>"], self.cmap_match, "Critère de classification"),
            R(["description", "<rest>"], lambda a, n: None, "Description"),
            exit_rule, end_rule,
        ]
        pmap_class = R(["class", "<name>"], self.pmap_class, "Classe à traiter")
        pmap = [
            pmap_class,
            R(["description", "<rest>"], lambda a, n: None, "Description"),
            exit_rule, end_rule,
        ]
        pmap_c = [
            pmap_class,
            R(["priority", "<rest>"], lambda a, n: self.pmap_action("priority", a, n), "File prioritaire (LLQ)"),
            R(["bandwidth", "<rest>"], lambda a, n: self.pmap_action("bandwidth", a, n), "Bande passante garantie"),
            R(["set", "<rest>"], lambda a, n: self.pmap_action("set", a, n), "Marquer le trafic"),
            R(["police", "<rest>"], lambda a, n: self.pmap_action("police", a, n), "Limiter le débit (policing)"),
            R(["shape", "<rest>"], lambda a, n: self.pmap_action("shape", a, n), "Lisser le débit (shaping)"),
            R(["fair-queue"], lambda a, n: self.pmap_action("fair-queue", [""], n), "File équitable (WFQ)"),
            R(["random-detect", "<rest>"], lambda a, n: self.pmap_action("random-detect", a, n), "WRED"),
            R(["queue-limit", "<rest>"], lambda a, n: self.pmap_action("queue-limit", a, n), "Taille de la file"),
            R(["service-policy", "<name>"], lambda a, n: self.pmap_action("service-policy", a, n),
              "Politique enfant (hiérarchique)"),
            exit_rule, end_rule,
        ]
        cp = [
            R(["service-policy", "input", "<name>"], self.cp_service_policy, "Politique CoPP"),
            exit_rule, end_rule,
        ]
        acl6 = [
            R(["permit", "<rest>"], lambda a, n: self.acl6_entry("permit", a, n), "Autoriser"),
            R(["deny", "<rest>"], lambda a, n: self.acl6_entry("deny", a, n), "Refuser"),
            R(["remark", "<rest>"], lambda a, n: self.acl6_entry("remark", a, n), "Commentaire"),
            R(["sequence", "<seq>", "<rest>"], self.acl6_sequence, "Entrée numérotée"),
            exit_rule, end_rule,
        ]
        return {"user": user, "exec": exec_, "config": config, "if": iface, "vlan": vlan,
                "line": line, "router": router, "router-eigrp": router_eigrp, "router-rip": router_rip,
                "dhcp": dhcp, "acl-std": acl, "acl-ext": acl, "archive": archive, "mst": mst, "dhcpv6": dhcpv6,
                "ospfv3": ospfv3, "bgp": bgp, "route-map": route_map, "vrf": vrf_common, "vrf-def": vrf_def,
                "vrf-af": vrf_af, "radius": radius, "tacacs": tacacs, "aaa-group": aaa_group, "isakmp": isakmp,
                "crypto-trans": crypto_trans, "crypto-map": crypto_map, "ipsec-profile": ipsec_profile,
                "cmap": cmap, "pmap": pmap, "pmap-c": pmap_c, "cp": cp, "acl6": acl6}

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
        elif self.mode in PARENT_MODES:
            self.mode = PARENT_MODES[self.mode]
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
            if i.ip and i.mask and not i.shutdown and not i.vrf and valid_ip(i.ip):
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

    def cfg_banner(self, args, negate, kind="motd"):
        attr = f"banner_{kind}"
        if negate:
            setattr(self.device, attr, None)
            return
        text = args[0]
        if len(text) >= 2 and text[0] == text[-1]:
            text = text[1:-1]
        elif text[:1] in "#^$%&":
            text = text[1:].rstrip(text[0])
        setattr(self.device, attr, text)

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
            if not canonical or (canonical not in self.device.interfaces and canonical != "Null0"):
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
        self.device.aaa_authentication[key] = self._aaa_methods(args[1], ("local", "enable", "none", "line",
                                                                          "local-case"))

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
        options = " ".join(args[1].split())
        words = options.split()
        i = 0
        while i < len(words):
            word = words[i].lower()
            if word == "prefer":
                i += 1
            elif word in ("key", "version") and i + 1 < len(words) and words[i + 1].isdigit():
                i += 2
            elif word == "source" and i + 1 < len(words) and normalize_iface(words[i + 1]):
                words[i + 1] = normalize_iface(words[i + 1])
                i += 2
            else:
                raise CommandError(INVALID)
        if negate:
            if server in self.device.ntp_servers:
                self.device.ntp_servers.remove(server)
            self.device.ntp_server_options.pop(server, None)
            return
        if server not in self.device.ntp_servers:
            self.device.ntp_servers.append(server)
        if words:
            self.device.ntp_server_options[server] = " ".join(w.lower() if w.lower() in ("prefer", "key", "version",
                                                                                          "source") else w
                                                               for w in words)
        else:
            self.device.ntp_server_options.pop(server, None)

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
            elif canonical.startswith("Tunnel") and canonical[6:].isdigit() and self.device.kind == "router":
                self.device.interfaces[canonical] = Interface(canonical, shutdown=False)
            elif canonical.startswith("Port-channel") and canonical[12:].isdigit() and 1 <= int(canonical[12:]) <= 48:
                self._create_port_channel(int(canonical[12:]))
            else:
                raise CommandError(INVALID)
        if negate:
            if "." in canonical or canonical.startswith(("Loopback", "Vlan", "Port-channel", "Tunnel")):
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
            vrf = self.device.vrfs.get(i.vrf or "")
            if not negate and vrf and vrf["style"] == "definition" and not vrf.get("ipv4"):
                raise CommandError(f"% VRF {i.vrf} is not configured for IPv4 (address-family ipv4)")
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
        if self.mode == "ospfv3":
            return self.device.ospfv3[self.ctx["ospfv3"]]
        return self.device.ospf[self.ospf_pid]

    def _process(self) -> RoutingProcess:
        if self.mode == "bgp":
            return self.device.bgp
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
        if not words or words[0].lower() not in ("static", "connected", "ospf", "eigrp", "rip", "bgp"):
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


    # ======================================================================
    # Fonctions ajoutées : gestion, commutation avancée, routage avancé, VPN, QoS
    # ======================================================================

    # -- aides génériques ----------------------------------------------------

    def _iface_arg(self, text: str) -> str:
        canonical = normalize_iface(text)
        if canonical is None or canonical not in self.device.interfaces:
            raise CommandError(INVALID)
        return canonical

    def _set_source(self, attr, args, negate):
        setattr(self.device, attr, None if negate else self._iface_arg(args[0]))

    def _if_num(self, attr, args, negate, low, high):
        value = None if negate else self._number(args[0], low, high)
        for i in self._each_iface():
            setattr(i, attr, value)

    def _if_flag(self, attr, negate):
        for i in self._each_iface():
            setattr(i, attr, not negate)

    @staticmethod
    def _secret(text: str) -> str:
        """Retire l'indicateur de type (0, 6, 7) devant un secret : « key 0 S3cret » -> « S3cret »."""
        return _strip_level(text.strip())

    def _aaa_methods(self, text: str, allowed: tuple[str, ...]) -> str:
        words = text.split()
        out, i = [], 0
        while i < len(words):
            word = words[i].lower()
            if word == "group" and i + 1 < len(words):
                name = words[i + 1]
                out += ["group", name.lower() if name.lower() in ("radius", "tacacs+") else name]
                i += 2
            elif word in ("radius", "tacacs+") or word in allowed:
                out.append(word)
                i += 1
            else:
                raise CommandError(INVALID)
        if not out:
            raise CommandError(INCOMPLETE)
        return " ".join(out)

    # -- exec ----------------------------------------------------------------

    def cmd_copy_remote(self, args, negate):
        dest = args[0]
        low = dest.lower()
        if low in ("tftp:", "ftp:", "scp:", "flash:"):
            return ("% Simulateur : indique la destination complète en une ligne, par exemple\n"
                    "  copy running-config tftp://192.168.1.50/SW1-confg")
        match = re.match(r"^(tftp|ftp|scp)://([^/]+)/(.+)$", dest, re.IGNORECASE)
        if match:
            host = match.group(2).split("@")[-1]
            if not valid_ip(host):
                raise CommandError(INVALID)
        elif not re.match(r"^(flash|nvram|usbflash0):[\w./$-]+$", dest, re.IGNORECASE):
            raise CommandError(INVALID)
        self.device.backups.append(dest)
        size = len(self.device.running_config())
        return f"Destination filename [{dest.rsplit('/', 1)[-1].split(':')[-1]}]?\n!!\n{size} bytes copied in 0.412 secs"

    def cmd_archive_config(self, args, negate):
        path = self.device.archive.get("path")
        if not path:
            return "% Archive path not specified (archive / path ...)"
        name = str(path).replace("$h", self.device.hostname).replace("$t", "Oct-19-2026-10-00-00")
        name = f"{name}-{len(self.device.archive_copies) + 1}"
        self.device.archive_copies.append(name)
        return f"!\nArchive : {name}"

    def cmd_ping_vrf(self, args, negate):
        vrf, target = args
        if vrf not in self.device.vrfs:
            raise CommandError(f"% VRF {vrf} does not have a valid routing table")
        if not valid_ip(target):
            raise CommandError("% Unrecognized host or address.")
        ok = any(i.vrf == vrf and i.ip and i.mask and valid_ip(i.ip) and not i.shutdown
                 and ipaddress.IPv4Address(target) in ipaddress.IPv4Network(f"{i.ip}/{i.mask}", strict=False)
                 for i in self.device.interfaces.values())
        return (f"Sending 5, 100-byte ICMP Echos to {target}, timeout is 2 seconds:\n"
                + ("!!!!!\nSuccess rate is 100 percent (5/5)" if ok else "....." + "\nSuccess rate is 0 percent (0/5)"))

    # -- configuration globale : gestion -------------------------------------

    def cfg_timestamps(self, args, negate):
        words = [w.lower() for w in args[0].split()]
        kind = "debug"
        if words and words[0] in ("debug", "log"):
            kind = words.pop(0)
        if negate:
            self.device.service_timestamps[kind] = "uptime"
            return
        if not words or words == ["uptime"]:
            value = "uptime"
        elif words[0] == "datetime":
            flags = set(words[1:])
            known = ["msec", "localtime", "show-timezone", "year"]
            if not flags <= set(known):
                raise CommandError(INVALID)
            value = " ".join(["datetime"] + [f for f in known if f in flags])
        else:
            raise CommandError(INVALID)
        self.device.service_timestamps[kind] = value

    def cfg_summer_time(self, args, negate):
        if negate:
            self.device.clock_summer_time = None
            return
        words = args[1].split()
        if not words or words[0].lower() not in ("recurring", "date"):
            raise CommandError(INVALID)
        words[0] = words[0].lower()
        self.device.clock_summer_time = " ".join([args[0]] + words)

    def cfg_ip_host(self, args, negate):
        name, addresses = args[0], args[1].split()
        if negate:
            self.device.ip_hosts.pop(name, None)
            return
        if not addresses or not all(valid_ip(a) for a in addresses):
            raise CommandError(INVALID)
        self.device.ip_hosts[name] = " ".join(addresses)

    def cfg_mac_static(self, args, negate):
        mac, vid, rest = args[0].lower(), self._vlan_id(args[1]), args[2].split()
        if not valid_mac(mac) or len(rest) < 2 or rest[0].lower() not in ("interface", "drop"):
            if rest[:1] == ["drop"]:
                pass
            else:
                raise CommandError(INVALID)
        target = "drop" if rest[0].lower() == "drop" else self._iface_arg("".join(rest[1:]))
        entries = [e for e in self.device.mac_static if (e[0], e[1]) != (mac, vid)]
        if not negate:
            entries.append((mac, vid, target))
        self.device.mac_static = entries

    def cfg_mac_aging(self, args, negate):
        if negate:
            self.device.mac_aging = None
            return
        value = self._number(args[0], 0, 1000000)
        if 0 < value < 10:
            raise CommandError(INVALID)
        self.device.mac_aging = value

    def cfg_archive(self, args, negate):
        if negate:
            self.device.archive = {}
            return
        self._exit_to_config()
        self.mode = "archive"

    def archive_path(self, args, negate):
        path = args[0].strip()
        if not negate and not re.match(r"^(flash|tftp|ftp|scp|nvram|usbflash0|disk0):", path, re.IGNORECASE):
            raise CommandError(INVALID)
        self._archive_set("path", None if negate else path)

    def _archive_set(self, key, value):
        if value is None:
            self.device.archive.pop(key, None)
        else:
            self.device.archive[key] = value

    def cfg_privilege(self, args, negate):
        mode, level, command = args[0].lower(), self._number(args[1], 0, 15), " ".join(args[2].split())
        if mode not in ("exec", "configure", "interface", "line", "router") or not command:
            raise CommandError(INVALID)
        entry = (mode, level, command.lower())
        self.device.privileges = [p for p in self.device.privileges if (p[0], p[2]) != (mode, command.lower())]
        if not negate:
            self.device.privileges.append(entry)

    def cfg_logging_console(self, args, negate):
        if negate:
            self.device.logging_console = None
            return
        level = args[0].strip().lower() or "debugging"
        if level.isdigit() and int(level) < len(LOG_LEVELS):
            level = LOG_LEVELS[int(level)]
        choices = [name for name in LOG_LEVELS if name.startswith(level)]
        if len(choices) != 1:
            raise CommandError(INVALID)
        self.device.logging_console = choices[0]

    def cfg_ntp_key(self, args, negate):
        key_id = self._number(args[0], 1, 65535)
        if negate:
            self.device.ntp_keys.pop(key_id, None)
            return
        key = self._secret(args[1])
        if not key:
            raise CommandError(INCOMPLETE)
        self.device.ntp_keys[key_id] = key

    def cfg_ntp_trusted(self, args, negate):
        key_id = self._number(args[0], 1, 65535)
        if negate:
            self.device.ntp_trusted.discard(key_id)
        else:
            self.device.ntp_trusted.add(key_id)

    # -- commutation ---------------------------------------------------------

    def cfg_mst_configuration(self, args, negate):
        if self.device.kind != "switch":
            raise CommandError(INVALID)
        if negate:
            self.device.mst_name, self.device.mst_revision, self.device.mst_instances = None, 0, {}
            return
        self._exit_to_config()
        self.mode = "mst"

    def mst_name_cmd(self, args, negate):
        self.device.mst_name = None if negate else args[0]

    def mst_revision_cmd(self, args, negate):
        self.device.mst_revision = 0 if negate else self._number(args[0], 0, 65535)

    def mst_instance_cmd(self, args, negate):
        inst = self._number(args[0], 1, 4094)
        vlans = self._vlan_set(args[1])
        current = self.device.mst_instances.get(inst, set())
        if negate:
            current = current - vlans
        else:
            for other, others in self.device.mst_instances.items():  # un VLAN n'appartient qu'à une instance
                if other != inst:
                    others -= vlans
            current = current | vlans
        if current:
            self.device.mst_instances[inst] = current
        else:
            self.device.mst_instances.pop(inst, None)
        self.device.mst_instances = {k: v for k, v in self.device.mst_instances.items() if v}

    def _mst_instances(self, text: str) -> set[int]:
        try:
            insts = parse_vlan_list(text)
        except ValueError:
            raise CommandError(INVALID) from None
        if not insts or any(not 0 <= i <= 4094 for i in insts):
            raise CommandError(INVALID)
        return insts

    def cfg_mst_priority(self, args, negate):
        insts, prio = self._mst_instances(args[0]), args[1]
        if not prio.isdigit() or int(prio) % 4096 or int(prio) > 61440:
            raise CommandError("% Bridge Priority must be in increments of 4096.")
        for inst in insts:
            if negate:
                self.device.mst_priority.pop(inst, None)
            else:
                self.device.mst_priority[inst] = int(prio)

    def cfg_mst_root(self, args, negate):
        insts = self._mst_instances(args[0])
        prio = {"primary": 24576, "secondary": 28672}.get(args[1].lower())
        if prio is None:
            raise CommandError(INVALID)
        for inst in insts:
            if negate:
                self.device.mst_priority.pop(inst, None)
            else:
                self.device.mst_priority[inst] = prio

    def cfg_monitor(self, args, negate):
        n = self._number(args[0], 1, 66)
        words = args[1].split()
        sessions = self.device.monitor_sessions
        if not words:
            if negate:
                sessions.pop(n, None)
                return
            raise CommandError(INCOMPLETE)
        session = sessions.setdefault(n, {"sources": [], "vlans": [], "dest": None})
        kind = words[0].lower()
        if kind in ("source", "destination") and len(words) >= 3 and words[1].lower() in ("interface", "vlan"):
            target = words[2:]
            way = "both"
            if kind == "source" and target[-1].lower() in ("rx", "tx", "both"):
                way = target.pop().lower()
            if kind == "destination" and len(target) >= 2 and target[-2].lower() == "encapsulation":
                target = target[:-2]
            text = " ".join(target)
            if words[1].lower() == "vlan":
                if kind != "source":
                    raise CommandError(INVALID)
                vlans = format_vlan_list(self._vlan_set(text))
                session["vlans"] = [v for v in session["vlans"] if v != vlans] + ([] if negate else [vlans])
            else:
                names = expand_range(text) if ("-" in text or "," in text) else [self._iface_arg(text)]
                if not names or any(nm not in self.device.interfaces for nm in names):
                    raise CommandError(INVALID)
                if kind == "source":
                    if not negate and session["dest"] in names:
                        raise CommandError("% Interface already configured as a destination")
                    session["sources"] = [s for s in session["sources"] if s[0] not in names]
                    if not negate:
                        session["sources"] += [(nm, way) for nm in names]
                else:
                    if len(names) != 1:
                        raise CommandError(INVALID)
                    if not negate and any(s[0] == names[0] for s in session["sources"]):
                        raise CommandError("% Interface already configured as a source")
                    session["dest"] = None if negate else names[0]
        else:
            raise CommandError(INVALID)
        if not (session["sources"] or session["vlans"] or session["dest"]):
            sessions.pop(n, None)

    def cfg_source_binding(self, args, negate):
        mac, vid, ip, iface = args[0].lower(), self._vlan_id(args[1]), args[2], self._iface_arg(args[3])
        if not valid_mac(mac) or not valid_ip(ip):
            raise CommandError(INVALID)
        entries = [b for b in self.device.ip_source_bindings if b[0] != mac]
        if not negate:
            entries.append((mac, vid, ip, iface))
        self.device.ip_source_bindings = entries

    # -- IPv6 : DHCPv6, OSPFv3, ACL --------------------------------------------

    def cfg_dhcpv6_pool(self, args, negate):
        if negate:
            self.device.dhcpv6_pools.pop(args[0], None)
            return
        self.device.dhcpv6_pools.setdefault(args[0], {"dns": [], "domain": None, "address_prefix": None})
        self._exit_to_config()
        self.ctx["pool6"] = args[0]
        self.mode = "dhcpv6"

    def _pool6(self) -> dict:
        return self.device.dhcpv6_pools[self.ctx["pool6"]]

    def dhcpv6_dns(self, args, negate):
        if not valid_ipv6(args[0]):
            raise CommandError(INVALID)
        server = str(ipaddress.IPv6Address(args[0]))
        dns = [d for d in self._pool6()["dns"] if d != server]
        if not negate:
            dns.append(server)
        self._pool6()["dns"] = dns

    def dhcpv6_domain(self, args, negate):
        self._pool6()["domain"] = None if negate else args[0]

    def dhcpv6_prefix(self, args, negate):
        try:
            prefix = normalize_ipv6_prefix(args[0])
        except ValueError:
            raise CommandError(INVALID) from None
        self._pool6()["address_prefix"] = None if negate else prefix

    def if_dhcpv6_server(self, args, negate):
        for i in self._each_iface():
            i.ipv6_dhcp_server = None if negate else args[0]

    def if_traffic_filter(self, args, negate):
        name, direction = args[0], args[1].lower()
        if direction not in ("in", "out"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if negate:
                i.ipv6_traffic_filter.pop(direction, None)
            else:
                i.ipv6_traffic_filter[direction] = name

    def line_ipv6_access_class(self, args, negate):
        direction = args[1].lower()
        if direction not in ("in", "out"):
            raise CommandError(INVALID)
        if negate:
            self._line().ipv6_access_class.pop(direction, None)
        else:
            self._line().ipv6_access_class[direction] = args[0]

    def _need_ipv6_routing(self):
        if not self.device.ipv6_routing:
            raise CommandError("% IPv6 routing not enabled (ipv6 unicast-routing)")

    def cfg_ipv6_ospf(self, args, negate):
        pid = self._number(args[0], 1, 65535)
        if negate:
            self.device.ospfv3.pop(pid, None)
            return
        self._need_ipv6_routing()
        created = pid not in self.device.ospfv3
        self.device.ospfv3.setdefault(pid, Ospfv3Process(pid))
        self._exit_to_config()
        self.ctx["ospfv3"] = pid
        self.mode = "ospfv3"
        if created and not any(valid_ip(i.ip or "") for i in self.device.interfaces.values()):
            return (f"%OSPFv3-4-NORTRID: Process OSPFv3-{pid}-IPv6 could not pick a router-id,\n"
                    "please configure manually")

    def ospfv3_router_id(self, args, negate):
        if not negate and not valid_ip(args[0]):
            raise CommandError(INVALID)
        self.device.ospfv3[self.ctx["ospfv3"]].router_id = None if negate else args[0]

    def if_ospfv3_area(self, args, negate):
        pid, area = self._number(args[0], 1, 65535), args[1]
        if not (area.isdigit() or valid_ip(area)):
            raise CommandError(INVALID)
        if not negate:
            self._need_ipv6_routing()
        for i in self._each_iface():
            i.ospfv3_area = None if negate else (pid, area)
        if not negate:
            self.device.ospfv3.setdefault(pid, Ospfv3Process(pid))

    def cfg_ipv6_acl(self, args, negate):
        if negate:
            self.device.ipv6_acls.pop(args[0], None)
            return
        self.device.ipv6_acls.setdefault(args[0], [])
        self._exit_to_config()
        self.ctx["acl6"] = args[0]
        self.mode = "acl6"

    def acl6_entry(self, action, args, negate):
        words = [action] + args[0].split()
        if action != "remark" and len(words) < 3:
            raise CommandError(INCOMPLETE)
        entry = _normalize_acl6_entry(words)
        entries = self.device.ipv6_acls[self.ctx["acl6"]]
        if negate:
            if entry in entries:
                entries.remove(entry)
        elif entry not in entries:
            entries.append(entry)

    def acl6_sequence(self, args, negate):
        rest = args[1].split()
        if not rest or rest[0].lower() not in ("permit", "deny", "remark"):
            raise CommandError(INVALID)
        self.acl6_entry(rest[0].lower(), [" ".join(rest[1:])], negate)

    # -- OSPF / EIGRP : compléments ------------------------------------------

    def if_ospf_network(self, args, negate):
        kind = args[0].lower()
        choices = [k for k in ("point-to-point", "broadcast", "non-broadcast", "point-to-multipoint")
                   if k.startswith(kind)]
        if len(choices) != 1 and kind not in ("point-to-point", "point-to-multipoint"):
            raise CommandError(INVALID)
        value = kind if kind in ("point-to-point", "point-to-multipoint") else choices[0]
        for i in self._each_iface():
            i.ospf_network = None if negate else value

    def if_ospf_auth(self, args, negate):
        kind = args[0].strip().lower()
        if kind not in ("", "message-digest", "null"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.ospf_auth = None if negate else kind

    def if_ospf_auth_key(self, args, negate):
        key = self._secret(args[0])
        if not negate and not key:
            raise CommandError(INCOMPLETE)
        for i in self._each_iface():
            i.ospf_auth_key = None if negate else key[:8]

    def if_ospf_md5(self, args, negate):
        key_id = self._number(args[0], 1, 255)
        key = self._secret(args[1])
        for i in self._each_iface():
            if negate:
                i.ospf_md5_keys.pop(key_id, None)
            elif not key:
                raise CommandError(INCOMPLETE)
            else:
                i.ospf_md5_keys[key_id] = key[:16]

    def ospf_area_auth(self, args, negate):
        area, kind = args[0], args[1].strip().lower()
        if not (area.isdigit() or valid_ip(area)) or kind not in ("", "message-digest"):
            raise CommandError(INVALID)
        if negate:
            self._ospf().area_auth.pop(area, None)
        else:
            self._ospf().area_auth[area] = kind

    def eigrp_stub(self, args, negate):
        words = [w.lower() for w in args[0].split()] or ["connected", "summary"]
        if not set(words) <= {"connected", "summary", "static", "redistributed", "receive-only"}:
            raise CommandError(INVALID)
        if "receive-only" in words and len(words) > 1:
            raise CommandError(INVALID)
        order = ["receive-only", "connected", "static", "summary", "redistributed"]
        self.device.eigrp[self.eigrp_asn].stub = None if negate else " ".join(w for w in order if w in words)

    def _eigrp_num(self, attr, args, negate, low, high):
        setattr(self.device.eigrp[self.eigrp_asn], attr, None if negate else self._number(args[0], low, high))

    def if_eigrp_summary(self, args, negate):
        asn, net, mask = self._number(args[0], 1, 65535), args[1], args[2]
        if not (valid_ip(net) and valid_mask(mask)):
            raise CommandError(INVALID)
        entry = (asn, net, mask)
        for i in self._each_iface():
            i.eigrp_summaries = [e for e in i.eigrp_summaries if e != entry]
            if not negate:
                i.eigrp_summaries.append(entry)

    # -- BGP -------------------------------------------------------------------

    def cfg_router_bgp(self, args, negate):
        asn = self._number(args[0], 1, 4294967295)
        if negate:
            if self.device.bgp and self.device.bgp.asn == asn:
                self.device.bgp = None
            return
        if self.device.bgp and self.device.bgp.asn != asn:
            raise CommandError(f"% BGP is already running; AS is {self.device.bgp.asn}")
        if self.device.bgp is None:
            self.device.bgp = BgpProcess(asn=asn)
        self._exit_to_config()
        self.mode = "bgp"

    def bgp_router_id(self, args, negate):
        if not negate and not valid_ip(args[0]):
            raise CommandError(INVALID)
        self.device.bgp.router_id = None if negate else args[0]

    def bgp_log(self, args, negate):
        self.device.bgp.log_neighbor_changes = not negate

    def bgp_remote_as(self, args, negate):
        address = args[0]
        if not valid_ip(address):
            raise CommandError(INVALID)
        neighbors = self.device.bgp.neighbors
        if negate:
            neighbors.pop(address, None)
            return
        asn = self._number(args[1], 1, 4294967295)
        if address in neighbors:
            neighbors[address].remote_as = asn
        else:
            neighbors[address] = BgpNeighbor(address, asn)

    def _bgp_neighbor(self, address: str) -> BgpNeighbor:
        nb = self.device.bgp.neighbors.get(address)
        if nb is None:
            raise CommandError("% Specify remote-as or peer-group commands first")
        return nb

    def bgp_nb_attr(self, args, negate, attr):
        nb = self._bgp_neighbor(args[0])
        value = args[1] if len(args) > 1 else ""
        if attr in ("next_hop_self", "shutdown"):
            setattr(nb, attr, not negate)
        elif attr == "update_source":
            nb.update_source = None if negate else self._iface_arg(value)
        elif attr == "ebgp_multihop":
            nb.ebgp_multihop = None if negate else self._number(value.strip() or "255", 1, 255)
        elif attr == "password":
            nb.password = None if negate else self._secret(value)
        else:
            nb.description = None if negate else value.strip()

    def bgp_nb_filter(self, args, negate, attr):
        nb = self._bgp_neighbor(args[0])
        name, direction = args[1], args[2].lower()
        if direction not in ("in", "out"):
            raise CommandError(INVALID)
        table = getattr(nb, attr)
        if negate:
            table.pop(direction, None)
        else:
            table[direction] = name

    def bgp_network(self, args, negate):
        net = args[0]
        mask = args[1] if len(args) > 1 else None
        if not valid_ip(net) or (mask is not None and not valid_mask(mask)):
            raise CommandError(INVALID)
        if mask is None:
            classful = classful_network(net)
            first = int(net.split(".")[0])
            mask = "255.0.0.0" if first < 128 else "255.255.0.0" if first < 192 else "255.255.255.0"
            net = classful
        entry = (net, mask)
        nets = [n for n in self.device.bgp.networks if n != entry]
        if not negate:
            nets.append(entry)
        self.device.bgp.networks = nets

    # -- prefix-lists, route-maps, PBR ----------------------------------------

    def cfg_prefix_list(self, args, negate):
        name, words = args[0], args[1].split()
        entries = self.device.prefix_lists.setdefault(name, [])
        if negate and not words:
            self.device.prefix_lists.pop(name, None)
            return
        if words and words[0].lower() == "description":
            return
        seq = None
        if len(words) >= 2 and words[0].lower() == "seq":
            seq = self._number(words[1], 1, 4294967294)
            words = words[2:]
        if negate and seq is not None and not words:
            self.device.prefix_lists[name] = [e for e in entries if e[0] != seq]
            return
        if len(words) < 2 or words[0].lower() not in ("permit", "deny"):
            raise CommandError(INVALID)
        action = words[0].lower()
        try:
            net = ipaddress.IPv4Network(words[1], strict=True)
        except ValueError:
            raise CommandError("% Invalid prefix range for " + words[1] + ", make sure: len < ge-value <= le-value"
                               if "/" in words[1] else INVALID) from None
        if "/" not in words[1]:
            raise CommandError(INVALID)
        ge = le = None
        rest = [w.lower() for w in words[2:]]
        while rest:
            key = rest.pop(0)
            if key not in ("ge", "le") or not rest or not rest[0].isdigit():
                raise CommandError(INVALID)
            value = int(rest.pop(0))
            if key == "ge":
                ge = value
            else:
                le = value
        length = net.prefixlen
        if (ge is not None and not length < ge <= 32) or (le is not None and not length < le <= 32) or (
                ge is not None and le is not None and ge > le):
            raise CommandError(f"% Invalid prefix range for {words[1]}, make sure: len < ge-value <= le-value")
        prefix = str(net)
        if negate:
            self.device.prefix_lists[name] = [e for e in entries if e[1:] != (action, prefix, ge, le)]
            return
        if seq is None:
            seq = (max(e[0] for e in entries) if entries else 0) + 5
        entries = [e for e in entries if e[0] != seq and e[1:] != (action, prefix, ge, le)]
        entries.append((seq, action, prefix, ge, le))
        self.device.prefix_lists[name] = sorted(entries)

    def cfg_route_map(self, args, negate):
        name, words = args[0], args[1].split()
        action, seq = "permit", None
        for word in words:
            if word.lower() in ("permit", "deny"):
                action = word.lower()
            elif word.isdigit() and 0 <= int(word) <= 65535:
                seq = int(word)
            else:
                raise CommandError(INVALID)
        if negate:
            if seq is None:
                self.device.route_maps.pop(name, None)
            else:
                self.device.route_maps.get(name, {}).pop(seq, None)
                if not self.device.route_maps.get(name):
                    self.device.route_maps.pop(name, None)
            return
        entries = self.device.route_maps.setdefault(name, {})
        if seq is None:
            seq = 10 if not entries else (10 if 10 in entries and len(entries) == 1 else min(entries))
        entry = entries.setdefault(seq, RouteMapEntry(action))
        entry.action = action
        self._exit_to_config()
        self.ctx["route_map"] = (name, seq)
        self.mode = "route-map"

    def _rmap_entry(self) -> RouteMapEntry:
        name, seq = self.ctx["route_map"]
        return self.device.route_maps[name][seq]

    def _rmap_clause(self, text: str, allowed: tuple[str, ...]) -> tuple[str, str]:
        words = text.split()
        if not words or words[0].lower() not in allowed:
            raise CommandError(INVALID)
        normalized = _normalize_policy_words(words)
        key_words = []
        for word in normalized.split():
            if word in RMAP_KEYWORDS:
                key_words.append(word)
            else:
                break
        return normalized, " ".join(key_words)

    def rmap_match(self, args, negate):
        entry = self._rmap_entry()
        text, key = self._rmap_clause(args[0], ("ip", "ipv6", "tag", "interface", "metric", "route-type",
                                                "as-path", "community", "source-protocol"))
        entry.matches = [m for m in entry.matches if m != text and not (negate and _clause_key(m) == text)]
        if not negate:
            entry.matches = [m for m in entry.matches if _clause_key(m) != key] + [text]

    def rmap_set(self, args, negate):
        entry = self._rmap_entry()
        text, key = self._rmap_clause(args[0], ("ip", "ipv6", "metric", "metric-type", "tag", "local-preference",
                                                "weight", "as-path", "community", "origin", "interface", "level"))
        if negate:
            entry.sets = [x for x in entry.sets if x != text and _clause_key(x) != text]
        else:
            entry.sets = [x for x in entry.sets if _clause_key(x) != key] + [text]

    def rmap_description(self, args, negate):
        self._rmap_entry().description = None if negate else args[0].strip()

    def if_policy(self, args, negate):
        for i in self._each_iface():
            i.policy_route_map = None if negate else args[0]

    def cfg_local_policy(self, args, negate):
        self.device.local_policy = None if negate else args[0]

    # -- VRF -------------------------------------------------------------------

    def cfg_vrf(self, args, negate, style):
        name = args[0]
        if negate:
            self.device.vrfs.pop(name, None)
            for i in self.device.interfaces.values():
                if i.vrf == name:
                    i.vrf, i.ip, i.mask = None, None, None
            self.device.vrf_routes = [r for r in self.device.vrf_routes if r[0] != name]
            return
        vrf = self.device.vrfs.setdefault(name, {"style": style, "rd": None, "route_targets": []})
        self._exit_to_config()
        self.ctx["vrf"] = name
        self.mode = "vrf" if vrf["style"] == "ip vrf" else "vrf-def"

    def _vrf(self) -> dict:
        return self.device.vrfs[self.ctx["vrf"]]

    def vrf_rd(self, args, negate):
        rd = args[0]
        if not negate:
            match = re.match(r"^(\d+|\d+\.\d+\.\d+\.\d+):(\d+)$", rd)
            if not match or (":" in rd and "." not in rd.split(":")[0] and int(rd.split(":")[0]) > 4294967295):
                raise CommandError(INVALID)
            if self._vrf().get("rd") and self._vrf()["rd"] != rd:
                raise CommandError(f"% Can't change RD, please remove VRF {self.ctx['vrf']} first")
        self._vrf()["rd"] = None if negate else rd

    def vrf_description(self, args, negate):
        self._vrf()["description"] = None if negate else args[0].strip()

    def vrf_route_target(self, args, negate):
        text = " ".join(args[0].lower().split())
        targets = [t for t in self._vrf().get("route_targets", []) if t != text]
        if not negate:
            targets.append(text)
        self._vrf()["route_targets"] = targets

    def vrf_address_family(self, args, negate):
        family = args[0].lower()
        if family not in ("ipv4", "ipv6"):
            raise CommandError(INVALID)
        self._vrf()[family] = not negate
        if not negate:
            self.mode = "vrf-af"

    def if_vrf(self, args, negate):
        name = args[0]
        if not negate and name not in self.device.vrfs:
            raise CommandError(f"% VRF {name} not configured.")
        messages = []
        for i in self._each_iface():
            if i.is_switchport:
                raise CommandError(INVALID)
            if negate:
                if i.vrf == name:
                    i.vrf = None
                    if i.ip:
                        messages.append(f"% Interface {i.name} IPv4 disabled and address(es) removed due to "
                                        f"disabling VRF {name}")
                    i.ip = i.mask = None
                continue
            if i.vrf != name and i.ip:
                messages.append(f"% Interface {i.name} IPv4 disabled and address(es) removed due to enabling "
                                f"VRF {name}")
                i.ip = i.mask = None
                i.secondary = []
            i.vrf = name
        return "\n".join(messages) or None

    def cfg_vrf_route(self, args, negate):
        vrf, net, mask, nh, rest = args
        if vrf not in self.device.vrfs:
            raise CommandError(f"% VRF {vrf} not configured.")
        if not (valid_ip(net) and valid_mask(mask)):
            raise CommandError(INVALID)
        if not valid_ip(nh):
            canonical = normalize_iface(nh)
            if not canonical or (canonical not in self.device.interfaces and canonical != "Null0"):
                raise CommandError(INVALID)
            nh = canonical
            if rest.split() and valid_ip(rest.split()[0]):
                nh = f"{nh} {rest.split()[0]}"
        route = (vrf, net, mask, nh)
        routes = [r for r in self.device.vrf_routes if r != route]
        if not negate:
            routes.append(route)
        self.device.vrf_routes = routes

    # -- AAA : serveurs, autorisation, traçabilité -----------------------------

    def cfg_aaa_enable(self, args, negate):
        if not self.device.aaa_new_model:
            raise CommandError(INVALID)
        if negate:
            self.device.aaa_authentication.pop("enable default", None)
            return
        self.device.aaa_authentication["enable default"] = self._aaa_methods(args[0], ("enable", "none", "line"))

    def cfg_aaa_other(self, args, negate, what):
        if not self.device.aaa_new_model:
            raise CommandError(INVALID)
        words = args[0].split()
        types = ("exec", "commands", "network", "console", "config-commands") if what == "authorization" else (
            "exec", "commands", "network", "connection", "system")
        if not words or words[0].lower() not in types:
            raise CommandError(INVALID)
        kind = words[0].lower()
        if kind == "console" or kind == "config-commands":
            table = self.device.aaa_authorization
            if negate:
                table.pop(kind, None)
            else:
                table[kind] = ""
            return
        size = 3 if kind == "commands" else 2
        if len(words) < size or (kind == "commands" and not words[1].isdigit()):
            raise CommandError(INCOMPLETE)
        key = " ".join([kind] + words[1:size])
        table = self.device.aaa_authorization if what == "authorization" else self.device.aaa_accounting
        if negate:
            table.pop(key, None)
            return
        rest = words[size:]
        if what == "accounting":
            if not rest or rest[0].lower() not in ("start-stop", "stop-only", "none"):
                raise CommandError(INVALID)
            mode = rest.pop(0).lower()
            table[key] = mode + (" " + self._aaa_methods(" ".join(rest), ()) if rest else "")
        else:
            table[key] = self._aaa_methods(" ".join(rest), ("local", "none", "if-authenticated"))

    def cfg_aaa_group(self, args, negate):
        kind, name = args[0].lower(), args[1]
        if kind not in ("radius", "tacacs+"):
            raise CommandError(INVALID)
        if not self.device.aaa_new_model:
            raise CommandError(INVALID)
        if negate:
            self.device.aaa_groups.pop(name, None)
            return
        self.device.aaa_groups.setdefault(name, {"type": kind, "servers": []})
        self._exit_to_config()
        self.ctx["aaa_group"] = name
        self.ctx["group_type"] = kind
        self.mode = "aaa-group"

    def aaa_group_server(self, args, negate):
        group = self.device.aaa_groups[self.ctx["aaa_group"]]
        servers = [s for s in group["servers"] if s != args[0]]
        if not negate:
            servers.append(args[0])
        group["servers"] = servers

    def cfg_aaa_server(self, args, negate, kind):
        table = self.device.radius_servers if kind == "radius" else self.device.tacacs_servers
        if negate:
            table.pop(args[0], None)
            return
        if kind == "radius":
            table.setdefault(args[0], {"address": None, "auth_port": 1645, "acct_port": 1646, "key": None})
        else:
            table.setdefault(args[0], {"address": None, "key": None})
        self._exit_to_config()
        self.ctx["aaa_server"] = (kind, args[0])
        self.mode = kind

    def _aaa_server(self) -> dict:
        kind, name = self.ctx["aaa_server"]
        return (self.device.radius_servers if kind == "radius" else self.device.tacacs_servers)[name]

    def _aaa_server_set(self, key, value):
        self._aaa_server()[key] = value

    def aaa_server_address(self, args, negate):
        server = self._aaa_server()
        if negate:
            server["address"] = None
            return
        if not valid_ip(args[0]):
            raise CommandError(INVALID)
        words = args[1].lower().split()
        while words:
            key = words.pop(0)
            if key not in ("auth-port", "acct-port") or not words:
                raise CommandError(INVALID)
            server[key.replace("-", "_")] = self._number(words.pop(0), 0, 65535)
        server["address"] = args[0]

    def aaa_server_key(self, args, negate):
        key = self._secret(args[0])
        if not negate and not key:
            raise CommandError(INCOMPLETE)
        self._aaa_server()["key"] = None if negate else key

    def _line_aaa(self, attr, args, negate):
        if not self.device.aaa_new_model:
            raise CommandError(INVALID)
        setattr(self._line(), attr, None if negate else args[0])

    # -- SNMPv3 -----------------------------------------------------------------

    def cfg_snmp_view(self, args, negate):
        name, oid, kind = args[0], args[1], args[2].lower()
        if kind not in ("included", "excluded"):
            raise CommandError(INVALID)
        entries = [e for e in self.device.snmp_views.get(name, []) if e[0] != oid]
        if not negate:
            entries.append((oid, kind))
        if entries:
            self.device.snmp_views[name] = entries
        else:
            self.device.snmp_views.pop(name, None)

    def cfg_snmp_group(self, args, negate):
        name, version = args[0], args[1].lower()
        if version != "v3":
            raise CommandError(INVALID)
        if negate:
            self.device.snmp_groups.pop(name, None)
            return
        words = args[2].split()
        if not words or words[0].lower() not in ("auth", "noauth", "priv"):
            raise CommandError(INVALID)
        group = {"level": words[0].lower()}
        rest = words[1:]
        while rest:
            key = rest.pop(0).lower()
            if key not in ("read", "write", "notify", "access") or not rest:
                raise CommandError(INVALID)
            group[key] = rest.pop(0)
        self.device.snmp_groups[name] = group

    def cfg_snmp_user(self, args, negate):
        name, group, version = args[0], args[1], args[2].lower()
        if version != "v3":
            raise CommandError(INVALID)
        if negate:
            self.device.snmp_users.pop(name, None)
            return
        words = args[3].split()
        user = {"group": group, "auth": None, "priv": None, "access": None}
        i = 0
        while i < len(words):
            key = words[i].lower()
            if key == "auth" and i + 2 < len(words) and words[i + 1].lower() in ("md5", "sha", "sha256", "sha384",
                                                                                   "sha512"):
                user["auth"] = words[i + 1].lower()
                if len(words[i + 2]) < 8:
                    raise CommandError("% Password too short - SNMPv3 passwords need at least 8 characters")
                i += 3
            elif key == "priv" and i + 2 < len(words) and words[i + 1].lower() in ("des", "3des", "aes"):
                algo = words[i + 1].lower()
                i += 2
                if algo == "aes":
                    if i >= len(words) or words[i] not in ("128", "192", "256"):
                        raise CommandError(INVALID)
                    algo += " " + words[i]
                    i += 1
                if i >= len(words):
                    raise CommandError(INCOMPLETE)
                if len(words[i]) < 8:
                    raise CommandError("% Password too short - SNMPv3 passwords need at least 8 characters")
                user["priv"] = algo
                i += 1
            elif key == "access" and i + 1 < len(words):
                user["access"] = words[i + 1]
                i += 2
            else:
                raise CommandError(INVALID)
        if user["priv"] and not user["auth"]:
            raise CommandError(INVALID)
        self.device.snmp_users[name] = user

    def cfg_snmp_traps(self, args, negate):
        text = " ".join(args[0].lower().split())
        traps = [t for t in self.device.snmp_traps if t != text]
        if not negate:
            traps.append(text)
        self.device.snmp_traps = traps

    # -- IPsec -----------------------------------------------------------------

    def cfg_isakmp_policy(self, args, negate):
        prio = self._number(args[0], 1, 10000)
        if negate:
            self.device.isakmp_policies.pop(prio, None)
            return
        self.device.isakmp_policies.setdefault(prio, {})
        self._exit_to_config()
        self.ctx["isakmp"] = prio
        self.mode = "isakmp"

    def isakmp_set(self, key, args, negate):
        policy = self.device.isakmp_policies[self.ctx["isakmp"]]
        if negate:
            policy.pop(key, None)
            return
        value = " ".join(args[0].lower().split())
        valid = {
            "encryption": ("des", "3des", "aes", "aes 128", "aes 192", "aes 256"),
            "hash": ("md5", "sha", "sha256", "sha384", "sha512"),
            "authentication": ("pre-share", "rsa-sig", "rsa-encr"),
            "group": ("1", "2", "5", "14", "15", "16", "19", "20", "21", "24"),
        }
        if key == "lifetime":
            value = str(self._number(value, 60, 86400))
        elif value not in valid[key]:
            raise CommandError(INVALID)
        policy[key] = value

    def cfg_isakmp_key(self, args, negate):
        words = args[0].split()
        if len(words) >= 2 and words[0] in ("0", "6"):
            words = words[1:]
        if len(words) < 3 or words[1].lower() != "address" or not valid_ip(words[2]):
            raise CommandError(INVALID)
        key, peer = words[0], words[2]
        if negate:
            self.device.isakmp_keys.pop(peer, None)
        else:
            self.device.isakmp_keys[peer] = key

    def cfg_transform_set(self, args, negate):
        name = args[0]
        if negate:
            self.device.transform_sets.pop(name, None)
            return
        transforms: list[str] = []
        for word in args[1].lower().split():
            if word.isdigit() and transforms and transforms[-1] in ("esp-aes", "esp-gcm") and word in (
                    "128", "192", "256"):
                transforms[-1] += " " + word
            elif word in ("esp-aes", "esp-gcm", "esp-3des", "esp-des", "esp-sha-hmac", "esp-sha256-hmac",
                          "esp-sha384-hmac", "esp-sha512-hmac", "esp-md5-hmac", "ah-sha-hmac", "ah-md5-hmac",
                          "esp-null"):
                transforms.append(word)
            else:
                raise CommandError(INVALID)
        if not transforms:
            raise CommandError(INCOMPLETE)
        self.device.transform_sets[name] = {"transforms": transforms, "mode": "tunnel"}
        self._exit_to_config()
        self.ctx["transform"] = name
        self.mode = "crypto-trans"

    def transform_mode(self, args, negate):
        mode = args[0].lower()
        if mode not in ("tunnel", "transport"):
            raise CommandError(INVALID)
        self.device.transform_sets[self.ctx["transform"]]["mode"] = "tunnel" if negate else mode

    def cfg_ipsec_profile(self, args, negate):
        if negate:
            self.device.ipsec_profiles.pop(args[0], None)
            return
        self.device.ipsec_profiles.setdefault(args[0], {})
        self._exit_to_config()
        self.ctx["crypto_entry"] = self.device.ipsec_profiles[args[0]]
        self.mode = "ipsec-profile"

    def cfg_crypto_map(self, args, negate):
        name, seq, rest = args[0], self._number(args[1], 1, 65535), args[2].strip().lower()
        if negate:
            self.device.crypto_maps.get(name, {}).pop(seq, None)
            if not self.device.crypto_maps.get(name):
                self.device.crypto_maps.pop(name, None)
            return
        if rest not in ("ipsec-isakmp", ""):
            raise CommandError(INVALID)
        entries = self.device.crypto_maps.setdefault(name, {})
        created = seq not in entries
        entry = entries.setdefault(seq, {"peers": []})
        self._exit_to_config()
        self.ctx["crypto_entry"] = entry
        self.mode = "crypto-map"
        if created:
            return ("% NOTE: This new crypto map will remain disabled until a peer\n"
                    "        and a valid access list have been configured.")

    def cmap_peer(self, args, negate):
        if not valid_ip(args[0]):
            raise CommandError(INVALID)
        entry = self.ctx["crypto_entry"]
        peers = [p for p in entry["peers"] if p != args[0]]
        if not negate:
            peers.append(args[0])
        entry["peers"] = peers

    def crypto_entry_set(self, key, args, negate):
        entry = self.ctx["crypto_entry"]
        value = args[0].strip()
        if negate:
            entry.pop(key, None)
            return
        if key == "pfs":
            value = value.lower()
            if value not in ("group1", "group2", "group5", "group14", "group15", "group16", "group19", "group20",
                             "group21", "group24"):
                raise CommandError(INVALID)
        elif key == "lifetime":
            value = str(self._number(value, 120, 86400))
        elif key == "transform_set" and value not in self.device.transform_sets:
            raise CommandError(f"% Transform set {value} does not exist.")
        entry[key] = value

    def if_crypto_map(self, args, negate):
        if not negate and args[0] not in self.device.crypto_maps:
            raise CommandError(f"% Invalid input: crypto map {args[0]} does not exist")
        for i in self._each_iface():
            i.crypto_map = None if negate else args[0]

    def if_tunnel_source(self, args, negate):
        value = args[0].strip()
        for i in self._each_iface():
            if not i.name.startswith("Tunnel"):
                raise CommandError(INVALID)
            if negate:
                i.tunnel_source = None
                continue
            i.tunnel_source = value if valid_ip(value) else self._iface_arg(value)

    def if_tunnel_destination(self, args, negate):
        if not negate and not valid_ip(args[0]):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if not i.name.startswith("Tunnel"):
                raise CommandError(INVALID)
            i.tunnel_destination = None if negate else args[0]

    def if_tunnel_mode(self, args, negate):
        mode = " ".join(args[0].lower().split())
        if not negate and mode not in ("gre ip", "gre multipoint", "ipip", "ipsec ipv4", "gre ipv6"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if not i.name.startswith("Tunnel"):
                raise CommandError(INVALID)
            i.tunnel_mode = None if negate or mode == "gre ip" else mode

    def if_tunnel_protection(self, args, negate):
        if not negate and args[0] not in self.device.ipsec_profiles:
            raise CommandError(f"% Invalid input: ipsec profile {args[0]} does not exist")
        for i in self._each_iface():
            if not i.name.startswith("Tunnel"):
                raise CommandError(INVALID)
            i.tunnel_protection = None if negate else args[0]

    def if_keepalive(self, args, negate):
        words = args[0].split()
        if not negate and (len(words) > 2 or not all(w.isdigit() for w in words)):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.keepalive = None if negate else (" ".join(words) or "10")

    # -- QoS (MQC) et CoPP ------------------------------------------------------

    def cfg_class_map(self, args, negate):
        words = args[0].split()
        kind = "match-all"
        if words and words[0].lower() in ("match-any", "match-all"):
            kind = words.pop(0).lower()
        if len(words) != 1:
            raise CommandError(INVALID if words else INCOMPLETE)
        name = words[0]
        if negate:
            self.device.class_maps.pop(name, None)
            return
        cmap = self.device.class_maps.setdefault(name, {"type": kind, "matches": []})
        cmap["type"] = kind
        self._exit_to_config()
        self.ctx["cmap"] = name
        self.mode = "cmap"

    def cmap_match(self, args, negate):
        words = args[0].split()
        if not words or words[0].lower() not in ("dscp", "ip", "access-group", "protocol", "cos", "precedence",
                                                 "any", "input-interface", "class-map", "not"):
            raise CommandError(INVALID)
        text = _normalize_policy_words(words)
        cmap = self.device.class_maps[self.ctx["cmap"]]
        cmap["matches"] = [m for m in cmap["matches"] if m != text]
        if not negate:
            cmap["matches"].append(text)

    def cfg_policy_map(self, args, negate):
        if negate:
            self.device.policy_maps.pop(args[0], None)
            return
        self.device.policy_maps.setdefault(args[0], {})
        self._exit_to_config()
        self.ctx["pmap"] = args[0]
        self.mode = "pmap"

    def pmap_class(self, args, negate):
        name = args[0]
        classes = self.device.policy_maps[self.ctx["pmap"]]
        if negate:
            classes.pop(name, None)
            self.mode = "pmap"
            return
        if name != "class-default" and name not in self.device.class_maps:
            raise CommandError(f"% class-map {name} not configured")
        if name not in classes:
            # class-default reste toujours la dernière classe évaluée
            default = classes.pop("class-default", None)
            classes[name] = []
            if default is not None:
                classes["class-default"] = default
        self.ctx["pmap_class"] = name
        self.mode = "pmap-c"

    def pmap_action(self, verb, args, negate):
        actions = self.device.policy_maps[self.ctx["pmap"]][self.ctx["pmap_class"]]
        text = _normalize_policy_words([verb] + args[0].split()) if args[0].strip() else verb
        key = " ".join(text.split()[:2]) if verb == "set" else verb
        if negate:
            actions[:] = [a for a in actions if a != text and (" ".join(a.split()[:2]) if verb == "set"
                                                               else a.split()[0]) != key]
            return
        if verb in ("priority", "bandwidth") and any(a.split()[0] in ("priority", "bandwidth") for a in actions
                                                     if a.split()[0] != verb):
            raise CommandError("% Invalid input: priority and bandwidth cannot be configured in the same class")
        actions[:] = [a for a in actions if (" ".join(a.split()[:2]) if verb == "set" else a.split()[0]) != key]
        actions.append(text)

    def if_service_policy(self, args, negate):
        direction, name = args[0].lower(), args[1]
        if direction not in ("input", "output"):
            raise CommandError(INVALID)
        if not negate and name not in self.device.policy_maps:
            raise CommandError(f"% Invalid input: policy map {name} not configured")
        for i in self._each_iface():
            if negate:
                i.service_policies.pop(direction, None)
            else:
                i.service_policies[direction] = name

    def cfg_control_plane(self, args, negate):
        self._exit_to_config()
        self.mode = "cp"

    def cp_service_policy(self, args, negate):
        if not negate and args[0] not in self.device.policy_maps:
            raise CommandError(f"% Invalid input: policy map {args[0]} not configured")
        self.device.control_plane_policy = None if negate else args[0]

    # -- sécurité des ports : compléments --------------------------------------

    def if_ps_aging_time(self, args, negate):
        self._require_switchport()
        value = None if negate else self._number(args[0], 1, 1440)
        for i in self._each_iface():
            i.port_security_aging_time = value

    def if_ps_aging_type(self, args, negate):
        self._require_switchport()
        kind = args[0].lower()
        choices = [c for c in ("absolute", "inactivity") if c.startswith(kind)]
        if len(choices) != 1:
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.port_security_aging_type = None if negate or choices[0] == "absolute" else choices[0]

    def if_ps_mac(self, args, negate):
        self._require_switchport()
        mac = args[0].lower()
        if not valid_mac(mac):
            raise CommandError(INVALID)
        for i in self._each_iface():
            if negate:
                i.port_security_macs = [m for m in i.port_security_macs if m != mac]
            elif mac not in i.port_security_macs:
                if len(i.port_security_macs) >= i.port_security_max:
                    raise CommandError(f"% Total secure mac-addresses on interface {i.name} has reached maximum "
                                       "limit.")
                i.port_security_macs.append(mac)

    def if_verify_source(self, args, negate):
        option = args[0].strip().lower()
        if option not in ("", "port-security", "mac-check"):
            raise CommandError(INVALID)
        for i in self._each_iface():
            i.ip_verify_source = None if negate else option

    # -- show ajoutés -------------------------------------------------------------

    def show_mac(self, args, negate):
        lines = ["          Mac Address Table", "-------------------------------------------", "",
                 "Vlan    Mac Address       Type        Ports", "----    -----------       --------    -----"]
        for mac, vlan, iface in self.device.mac_static:
            port = "Drop" if iface == "drop" else self.device.interfaces[iface].short
            lines.append(f"{vlan:>4}    {mac}    STATIC      {port}")
        lines.append(f"Total Mac Addresses for this criterion: {len(self.device.mac_static)}")
        if self.device.mac_aging is not None:
            lines.append(f"Aging time : {self.device.mac_aging} s")
        return "\n".join(lines)

    def show_hosts(self, args, negate):
        d = self.device
        lines = [f"Default domain is {d.domain_name or 'not set'}",
                 f"Name/address lookup uses {'domain service' if d.domain_lookup else 'static mappings'}",
                 "Name servers are " + (", ".join(d.name_servers) or "255.255.255.255"), "",
                 "Host                      Port  Flags      Age Type   Address(es)"]
        lines += [f"{name:<26}None  (perm, OK)  0   IP    {ip}" for name, ip in d.ip_hosts.items()]
        return "\n".join(lines)

    def show_clock(self, args, negate):
        zone = self.device.clock_timezone[0] if self.device.clock_timezone else "UTC"
        if self.device.clock_summer_time:
            zone = self.device.clock_summer_time.split()[0]
        return f"*10:00:00.000 {zone} Mon Oct 19 2026"

    def show_archive(self, args, negate):
        a = self.device.archive
        lines = [f"The maximum archive configurations allowed is {a.get('maximum', 10)}.",
                 f"The next archive file will be named {a.get('path', '(path non défini)')}-"
                 f"{len(self.device.archive_copies) + 1}", " Archive #  Name"]
        lines += [f"   {n}       {name}" for n, name in enumerate(self.device.archive_copies, 1)]
        return "\n".join(lines)

    def show_monitor(self, args, negate):
        lines = []
        for n, mon in sorted(self.device.monitor_sessions.items()):
            lines += [f"Session {n}", "---------", "Type                   : Local Session"]
            for way, label in (("both", "Both"), ("rx", "RX Only"), ("tx", "TX Only")):
                srcs = [self.device.interfaces[s].short for s, w in mon["sources"] if w == way]
                if srcs:
                    lines.append(f"Source Ports           :\n    {label:<19}: {','.join(srcs)}")
            if mon["vlans"]:
                lines.append(f"Source VLANs           : {','.join(mon['vlans'])}")
            dest = self.device.interfaces[mon["dest"]].short if mon["dest"] else "None"
            lines += [f"Destination Ports      : {dest}", ""]
        return "\n".join(lines) or "No SPAN configuration is present in the system."

    def show_mst(self, args, negate):
        d = self.device
        if d.kind != "switch":
            raise CommandError(INVALID)
        lines = [f"Name      [{d.mst_name or ''}]", f"Revision  {d.mst_revision}     "
                 f"Instances configured {len(d.mst_instances) + 1}", "",
                 "Instance  Vlans mapped", "--------  ---------------------------------------------------------------------"]
        mapped = set().union(*d.mst_instances.values()) if d.mst_instances else set()
        lines.append(f"0         {format_vlan_list(set(range(1, 4095)) - mapped)}")
        lines += [f"{inst:<10}{format_vlan_list(vlans)}" for inst, vlans in sorted(d.mst_instances.items())]
        if d.mst_priority:
            lines += ["", "Instance  Bridge priority"]
            lines += [f"MST{inst:<7}{prio + inst}" for inst, prio in sorted(d.mst_priority.items())]
        if d.stp_mode != "mst":
            lines.insert(0, "% Attention : le switch n'est pas en mode MST (spanning-tree mode mst)")
        return "\n".join(lines)

    def show_dhcpv6_pool(self, args, negate):
        lines = []
        for name, pool in self.device.dhcpv6_pools.items():
            lines.append(f"DHCPv6 pool: {name}")
            if pool.get("address_prefix"):
                lines.append(f"  Address allocation prefix: {pool['address_prefix'].upper()}")
            lines += [f"  DNS server: {dns.upper()}" for dns in pool["dns"]]
            if pool.get("domain"):
                lines.append(f"  Domain name: {pool['domain']}")
            users = [i.name for i in self.device.interfaces.values() if i.ipv6_dhcp_server == name]
            lines.append(f"  Active clients: 0 (interfaces : {', '.join(users) or 'aucune'})")
        return "\n".join(lines)

    def show_ospf_interface(self, args, negate):
        lines = ["Interface    PID   Area            IP Address/Mask    Cost  State Nbrs F/C  Network  Auth"]
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            pid_area = self._ospf_area_of(i)
            if not pid_area:
                continue
            pid, area = pid_area
            network = i.ospf_network or ("loopback" if i.name.startswith("Loopback") else "broadcast")
            auth = i.ospf_auth if i.ospf_auth is not None else self.device.ospf[pid].area_auth.get(area, "-")
            auth = {"": "simple", "message-digest": "md5", "null": "none"}.get(auth, auth)
            state = "DOWN" if i.shutdown else ("P2P" if network == "point-to-point" else "DR")
            lines.append(f"{i.short:<13}{pid:<6}{area:<16}{(i.ip or '') + '/' + str(mask_to_prefix(i.mask or '0.0.0.0')):<19}"
                         f"{i.ospf_cost or 1:<6}{state:<6}0/0  {network:<9}{auth}")
        return "\n".join(lines)

    def _ospf_area_of(self, iface: Interface) -> tuple[int, str] | None:
        if iface.ospf_area:
            return iface.ospf_area
        if not iface.ip or not iface.mask or not valid_ip(iface.ip):
            return None
        for pid, proc in self.device.ospf.items():
            for net, wild, area in proc.networks:
                try:
                    inverse = ".".join(str(255 - int(o)) for o in wild.split("."))
                    if ipaddress.IPv4Address(iface.ip) in ipaddress.IPv4Network(f"{net}/{inverse}", strict=False):
                        return pid, area
                except ValueError:
                    continue
        return None

    def show_ospf_neighbor(self, args, negate):
        return ("Neighbor ID     Pri   State           Dead Time   Address         Interface\n"
                "(simulateur : aucun voisin n'est raccordé ; vérifie la configuration avec show ip ospf interface)")

    def show_ipv6_protocols(self, args, negate):
        lines = ['IPv6 Routing Protocol is "connected"', 'IPv6 Routing Protocol is "static"']
        for pid, proc in self.device.ospfv3.items():
            lines.append(f'IPv6 Routing Protocol is "ospf {pid}"')
            lines.append(f"  Router ID {proc.router_id or self._auto_router_id()}")
            ifaces = [f"    {i.name} (Area {i.ospfv3_area[1]})" for i in self.device.interfaces.values()
                      if i.ospfv3_area and i.ospfv3_area[0] == pid]
            lines += ["  Interfaces:"] + ifaces
            lines += self._passive_summary(proc)
        return "\n".join(lines)

    def show_ospfv3_interface(self, args, negate):
        lines = ["Interface    PID   Area            Intf ID    Cost  State Nbrs F/C"]
        for n, i in enumerate(sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)), 1):
            if i.ospfv3_area:
                lines.append(f"{i.short:<13}{i.ospfv3_area[0]:<6}{i.ospfv3_area[1]:<16}{n:<11}{i.ospfv3_cost or 1:<6}"
                             f"{'DOWN' if i.shutdown else 'DR':<6}0/0")
        return "\n".join(lines)

    def show_bgp_summary(self, args, negate):
        bgp = self.device.bgp
        if not bgp:
            return "% BGP not active"
        lines = [f"BGP router identifier {bgp.router_id or self._auto_router_id()}, local AS number {bgp.asn}", "",
                 "Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd"]
        for nb in bgp.neighbors.values():
            state = "Idle (Admin)" if nb.shutdown else "Active"
            lines.append(f"{nb.address:<16}4 {nb.remote_as:>12}       0       0        1    0    0 never    {state}")
        return "\n".join(lines)

    def show_bgp(self, args, negate):
        bgp = self.device.bgp
        if not bgp:
            return "% BGP not active"
        lines = [f"BGP table version is 1, local router ID is {bgp.router_id or self._auto_router_id()}",
                 "Status codes: * valid, > best, i - internal", "Origin codes: i - IGP, e - EGP, ? - incomplete", "",
                 "     Network          Next Hop            Metric LocPrf Weight Path"]
        for net, mask in bgp.networks:
            routed = any(r[0] == net and r[1] == mask for r in self.device.static_routes) or any(
                i.ip and i.mask == mask and valid_ip(i.ip) and str(ipaddress.IPv4Network(f"{i.ip}/{i.mask}",
                                                                                         strict=False).network_address)
                == net and not i.shutdown for i in self.device.interfaces.values())
            flag = " *>  " if routed else "     "
            lines.append(f"{flag}{net + '/' + str(mask_to_prefix(mask)):<17}0.0.0.0                  0         32768 i"
                         + ("" if routed else "   (absent de la table de routage : non annoncé)"))
        return "\n".join(lines)

    def show_prefix_lists(self, args, negate):
        lines = []
        for name, entries in self.device.prefix_lists.items():
            lines.append(f"ip prefix-list {name}: {len(entries)} entries")
            lines += [f"   seq {e[0]} {_plist_text(e)}" for e in entries]
        return "\n".join(lines)

    def show_route_maps(self, args, negate):
        lines = []
        for name, entries in self.device.route_maps.items():
            for seq, entry in sorted(entries.items()):
                lines.append(f"route-map {name}, {entry.action}, sequence {seq}")
                lines.append("  Match clauses:")
                lines += [f"    {m}" for m in entry.matches]
                lines.append("  Set clauses:")
                lines += [f"    {x}" for x in entry.sets]
                lines.append("  Policy routing matches: 0 packets, 0 bytes")
        return "\n".join(lines)

    def show_ip_policy(self, args, negate):
        lines = ["Interface      Route map"]
        if self.device.local_policy:
            lines.append(f"local          {self.device.local_policy}")
        lines += [f"{i.short:<15}{i.policy_route_map}" for i in self.device.interfaces.values() if i.policy_route_map]
        return "\n".join(lines)

    def show_aaa_servers(self, args, negate):
        lines = []
        for name, srv in self.device.radius_servers.items():
            lines.append(f"RADIUS: id {len(lines) + 1}, priority 1, host {srv.get('address')}, auth-port "
                         f"{srv.get('auth_port')}, acct-port {srv.get('acct_port')} ({name})")
            lines.append(f"     State: current UP, duration 0s, key {'configured' if srv.get('key') else 'missing'}")
        for name, srv in self.device.tacacs_servers.items():
            lines.append(f"TACACS+: host {srv.get('address')} ({name}), key {'configured' if srv.get('key') else 'missing'}")
        return "\n".join(lines) or "% Aucun serveur AAA configuré"

    def show_snmp_user(self, args, negate):
        lines = []
        for name, user in self.device.snmp_users.items():
            lines += [f"User name: {name}", "Engine ID: 800000090300001122334455",
                      "storage-type: nonvolatile        active",
                      f"Authentication Protocol: {(user['auth'] or 'None').upper()}",
                      f"Privacy Protocol: {(user['priv'] or 'None').upper().replace(' ', '')}",
                      f"Group-name: {user['group']}", ""]
        return "\n".join(lines)

    def show_snmp_group(self, args, negate):
        lines = []
        for name, group in self.device.snmp_groups.items():
            lines += [f"groupname: {name}                   security model:v3 {group['level']}",
                      f"readview : {group.get('read', 'v1default')}    writeview: {group.get('write', '<no writeview specified>')}",
                      f"notifyview: {group.get('notify', '<no notifyview specified>')}",
                      "row status: active" + (f"        access-list: {group['access']}" if group.get("access") else ""),
                      ""]
        return "\n".join(lines)

    def show_verify_source(self, args, negate):
        lines = ["Interface  Filter-type  Filter-mode  IP-address       Mac-address        Vlan",
                 "---------  -----------  -----------  ---------------  -----------------  ----"]
        for i in self.device.interfaces.values():
            if i.ip_verify_source is not None:
                kind = "ip-mac" if i.ip_verify_source else "ip"
                bound = [b for b in self.device.ip_source_bindings if b[3] == i.name]
                if bound:
                    lines += [f"{i.short:<11}{kind:<13}active       {b[2]:<17}{b[0] if kind == 'ip-mac' else '':<19}{b[1]}"
                              for b in bound]
                else:
                    lines.append(f"{i.short:<11}{kind:<13}active       deny-all")
        return "\n".join(lines)

    def show_source_binding(self, args, negate):
        lines = ["MacAddress          IpAddress        Lease(sec)  Type           VLAN  Interface",
                 "------------------  ---------------  ----------  -------------  ----  --------------------"]
        lines += [f"{mac:<20}{ip:<17}infinite    static         {vlan:<6}{iface}"
                  for mac, vlan, ip, iface in self.device.ip_source_bindings]
        return "\n".join(lines)

    def show_isakmp(self, args, negate):
        lines = ["Global IKE policy"]
        for prio, pol in sorted(self.device.isakmp_policies.items()):
            lines += [f"Protection suite of priority {prio}",
                      f"        encryption algorithm:   {pol.get('encryption', 'des').upper()}",
                      f"        hash algorithm:         {pol.get('hash', 'sha').upper()}",
                      f"        authentication method:  {pol.get('authentication', 'rsa-sig')}",
                      f"        Diffie-Hellman group:   #{pol.get('group', '1')}",
                      f"        lifetime:               {pol.get('lifetime', '86400')} seconds"]
        return "\n".join(lines)

    def show_crypto_map(self, args, negate):
        lines = []
        for name, entries in self.device.crypto_maps.items():
            for seq, entry in sorted(entries.items()):
                lines += [f'Crypto Map "{name}" {seq} ipsec-isakmp',
                          f"        Peer = {', '.join(entry['peers']) or '(none)'}",
                          f"        Extended IP access list {entry.get('acl', '(none)')}",
                          f"        Transform sets={{ {entry.get('transform_set', '')} }}",
                          f"        PFS (Y/N): {'Y' if entry.get('pfs') else 'N'}"]
            users = [i.name for i in self.device.interfaces.values() if i.crypto_map == name]
            lines.append(f"        Interfaces using crypto map {name}: {' '.join(users)}")
        return "\n".join(lines)

    def show_transform_sets(self, args, negate):
        lines = []
        for name, ts in self.device.transform_sets.items():
            lines += [f"Transform set {name}: {{ {' '.join(ts['transforms'])} }}",
                      f"   will negotiate = {{ {ts['mode'].capitalize()}, }},"]
        return "\n".join(lines)

    def show_class_maps(self, args, negate):
        lines = []
        for name, cmap in self.device.class_maps.items():
            lines.append(f" Class Map {cmap['type']} {name} (id 1)")
            lines += [f"   Match {m}" for m in cmap["matches"]]
            lines.append("")
        return "\n".join(lines)

    def show_policy_maps(self, args, negate):
        lines = []
        for name, classes in self.device.policy_maps.items():
            lines.append(f"  Policy Map {name}")
            for cls, actions in classes.items():
                lines.append(f"    Class {cls}")
                lines += [f"      {a}" for a in actions]
        users = [f"{i.name} : service-policy {d} {n}" for i in self.device.interfaces.values()
                 for d, n in i.service_policies.items()]
        if self.device.control_plane_policy:
            users.append(f"Control Plane : service-policy input {self.device.control_plane_policy}")
        return "\n".join(lines + ([""] + users if users else []))

    def show_vrf(self, args, negate):
        lines = ["  Name                             Default RD            Interfaces"]
        for name, vrf in self.device.vrfs.items():
            ifaces = [i.short for i in self.device.interfaces.values() if i.vrf == name]
            lines.append(f"  {name:<33}{vrf.get('rd') or '<not set>':<22}{' '.join(ifaces)}")
        return "\n".join(lines)

    def show_ip_route_vrf(self, args, negate):
        vrf = args[0]
        if vrf not in self.device.vrfs:
            return f"% IP routing table {vrf} does not exist"
        lines = [f"Routing Table: {vrf}", "Codes: L - local, C - connected, S - static", ""]
        for i in sorted(self.device.interfaces.values(), key=lambda i: iface_sort_key(i.name)):
            if i.vrf == vrf and i.ip and i.mask and valid_ip(i.ip) and not i.shutdown:
                net = ipaddress.IPv4Network(f"{i.ip}/{i.mask}", strict=False)
                lines += [f"C        {net} is directly connected, {i.name}",
                          f"L        {i.ip}/32 is directly connected, {i.name}"]
        for _, net, mask, nh in [r for r in self.device.vrf_routes if r[0] == vrf]:
            lines.append(f"S        {net}/{mask_to_prefix(mask)} [1/0] via {nh}")
        return "\n".join(lines)

    def show_ipv6_acls(self, args, negate):
        lines = []
        for name, entries in self.device.ipv6_acls.items():
            lines.append(f"IPv6 access list {name}")
            lines += [f"    {e} sequence {10 * (n + 1)}" for n, e in enumerate(entries)]
        return "\n".join(lines)

    def show_interface(self, args, negate):
        name = normalize_iface(args[0] + args[1].replace(" ", ""))
        if name is None or name not in self.device.interfaces:
            raise CommandError(INVALID)
        i = self.device.interfaces[name]
        state = "administratively down" if i.shutdown else "up"
        lines = [f"{i.name} is {state}, line protocol is {'down' if i.shutdown else 'up'}"]
        if i.description:
            lines.append(f"  Description: {i.description}")
        if i.ip and valid_ip(i.ip):
            lines.append(f"  Internet address is {i.ip}/{mask_to_prefix(i.mask or '255.255.255.255')}")
        if i.vrf:
            lines.append(f"  VRF : {i.vrf}")
        if i.name.startswith("Tunnel"):
            mtu = i.ip_mtu or 1476
            lines += [f"  MTU 17916 bytes, BW 100 Kbit/sec (ip mtu {mtu})",
                      f"  Tunnel source {i.tunnel_source or 'UNKNOWN'}, destination {i.tunnel_destination or 'UNKNOWN'}",
                      f"  Tunnel protocol/transport {(i.tunnel_mode or 'gre ip').upper().replace(' ', '/')}"]
            if i.tunnel_protection:
                lines.append(f'  Tunnel protection via IPSec (profile "{i.tunnel_protection}")')
        else:
            lines.append(f"  MTU {i.ip_mtu or 1500} bytes, BW {i.bandwidth or (100000 if 'Fast' in i.name else 1000000)}"
                         " Kbit/sec")
            if i.is_physical:
                lines.append(f"  {'Full' if i.duplex == 'full' else 'Auto'}-duplex, {i.speed}")
        return "\n".join(lines)


def _strip_level(text: str) -> str:
    words = text.split()
    if len(words) > 1 and words[0] in ("0", "5", "7", "8", "9"):
        words = words[1:]
    return " ".join(words)


ACL_KEYWORDS = {"permit", "deny", "host", "any", "ip", "tcp", "udp", "icmp", "eq", "neq", "gt", "lt", "range",
                "remark", "log", "established", "echo", "echo-reply", "ospf", "eigrp", "esp", "gre"}


def _normalize_acl_entry(words: list[str]) -> str:
    return " ".join(w.lower() if w.lower() in ACL_KEYWORDS else w for w in words)


ACL6_KEYWORDS = ACL_KEYWORDS | {"ipv6", "sequence", "icmp", "nd-na", "nd-ns", "router-advertisement",
                                "router-solicitation", "packet-too-big", "time-exceeded", "unreachable", "echo-request",
                                "www", "telnet", "22", "ssh", "domain", "ftp", "smtp"}


def _normalize_acl6_entry(words: list[str]) -> str:
    out = []
    for word in words:
        low = word.lower()
        if low in ACL6_KEYWORDS:
            out.append(low)
            continue
        try:
            out.append(str(ipaddress.IPv6Network(word, strict=False)) if "/" in word else str(ipaddress.IPv6Address(word)))
        except ValueError:
            out.append(word)
    return " ".join(out)


# Mots-clés des clauses match/set des route-maps (normalisés en minuscules) ; les mots de
# VALUE_WORDS sont des valeurs : ils ne font pas partie de la « clé » d'une clause.
RMAP_KEYWORDS = {"ip", "ipv6", "address", "prefix-list", "next-hop", "metric", "metric-type", "tag",
                 "local-preference", "weight", "as-path", "prepend", "community", "origin", "interface",
                 "route-type", "source-protocol", "level", "verify-availability", "recursive", "default"}
VALUE_WORDS = {"type-1", "type-2", "igp", "incomplete", "egp", "internal", "external", "local", "none", "no-export",
               "additive", "static", "connected", "ospf", "eigrp", "bgp", "rip"}
POLICY_KEYWORDS = RMAP_KEYWORDS | VALUE_WORDS | {
    "dscp", "cos", "precedence", "access-group", "name", "protocol", "percent", "remaining", "conform-action",
    "exceed-action", "violate-action", "transmit", "drop", "set-dscp-transmit", "average", "peak", "any", "cir",
    "bc", "be", "kbps", "mbps", "ef", "default", "not", "input-interface", "class-map", "set", "priority",
    "bandwidth", "police", "shape", "fair-queue", "random-detect", "queue-limit", "service-policy", "packets",
    "dscp-based", "http", "dns", "rtp", "sip", "ssh", "telnet", "icmp"} | {
    f"af{a}{b}" for a in range(1, 5) for b in range(1, 4)} | {f"cs{n}" for n in range(8)}


def _normalize_policy_words(words: list[str]) -> str:
    return " ".join(w.lower() if w.lower() in POLICY_KEYWORDS else w for w in words)


def _clause_key(text: str) -> str:
    key = []
    for word in text.split():
        if word in RMAP_KEYWORDS:
            key.append(word)
        else:
            break
    return " ".join(key)


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
                 "% Address", "% OSPF", "% Port Priority", "% VTP", "% VRF", "% Specify", "% IPv6 routing",
                 "% class-map", "% Interface already", "% Archive", "% Transform set", "% BGP", "% Can't",
                 "% Total secure")


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
