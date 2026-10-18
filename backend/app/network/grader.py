"""Sessions CLI réseau et moulinette de vérification de la configuration."""

from __future__ import annotations

import secrets
import time
from typing import Any

from .ios import Device, Session, apply_commands, expand_range, mask_to_prefix, parse_vlan_list

SESSION_TTL = 6 * 3600
MAX_SESSIONS = 500

_sessions: dict[str, tuple[float, str, Session]] = {}


def new_device(exercise: dict[str, Any]) -> Device:
    device = Device(exercise.get("device", "switch"), exercise.get("hostname"))
    initial = exercise.get("initial")
    if initial:
        apply_commands(device, ["configure terminal", *initial.splitlines(), "end"])
    return device


def create_session(exercise: dict[str, Any]) -> tuple[str, Session]:
    _cleanup()
    session = Session(new_device(exercise))
    session_id = secrets.token_urlsafe(16)
    _sessions[session_id] = (time.time(), exercise["id"], session)
    return session_id, session


def get_session(session_id: str) -> tuple[str, Session] | None:
    entry = _sessions.get(session_id)
    if entry is None:
        return None
    _, exercise_id, session = entry
    _sessions[session_id] = (time.time(), exercise_id, session)
    return exercise_id, session


def _cleanup() -> None:
    now = time.time()
    for sid, (seen, _, _) in list(_sessions.items()):
        if now - seen > SESSION_TTL:
            del _sessions[sid]
    while len(_sessions) >= MAX_SESSIONS:
        oldest = min(_sessions, key=lambda k: _sessions[k][0])
        del _sessions[oldest]


SAFE_BUILTINS = {"len": len, "any": any, "all": all, "set": set, "sorted": sorted, "str": str,
                 "int": int, "range": range, "list": list, "min": min, "max": max, "zip": zip,
                 "True": True, "False": False, "None": None}


def check(exercise: dict[str, Any], device: Device) -> dict[str, Any]:
    """Évalue chaque vérification (expression Python écrite par l'auteur de l'exercice)."""
    namespace = {
        "d": device,
        "intf": device.intf,
        "has_intf": device.has_intf,
        "vlan": device.vlan_name,
        "vlan_ports": device.vlan_ports,
        "route": device.has_route,
        "route6": device.has_route6,
        "ospf_net": device.ospf_has_network,
        "eigrp_net": device.eigrp_has_network,
        "rip_net": device.rip_has_network,
        "nat": device.has_nat,
        "ipv6": lambda name, address: device.intf(name).has_ipv6(address),
        "hsrp": lambda name, group: device.intf(name).standby[group],
        "members": device.channel_members,
        "vlans": parse_vlan_list,
        "prefix": mask_to_prefix,
        "ports": lambda spec: [device.intf(n) for n in expand_range(spec)],
        "acl": lambda name: [e for e in device.acls.get(str(name), []) if e != "__ext__"],
        "line": lambda kind: device.lines[kind],
    }
    results = []
    for item in exercise.get("checks", []):
        try:
            ok = bool(eval(item["expr"], {"__builtins__": SAFE_BUILTINS, **namespace}))
        except Exception:  # noqa: BLE001 - une interface absente, etc. = vérification échouée
            ok = False
        results.append({"name": item["desc"], "passed": ok, "message": "" if ok else item.get("hint", "")})
    passed = sum(r["passed"] for r in results)
    return {"success": bool(results) and passed == len(results), "passed": passed, "total": len(results),
            "results": results}
