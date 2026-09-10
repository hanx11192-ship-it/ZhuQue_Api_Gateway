import ipaddress
import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)
_running_global = 0
_running_slug: dict[str, int] = defaultdict(int)


def _parse_networks(items: list[str]):
    nets = []
    for item in items:
        try:
            if "/" in item:
                nets.append(ipaddress.ip_network(item, strict=False))
            else:
                nets.append(ipaddress.ip_network(item + "/32" if ":" not in item else item + "/128", strict=False))
        except ValueError:
            continue
    return nets


def ip_in_list(ip: str, items: list[str]) -> bool:
    if not ip or not items:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in _parse_networks(items):
        if addr in net:
            return True
    return False


def check_rate(bucket: str, limit: int) -> tuple[bool, int]:
    if limit <= 0:
        return False, 60
    now = time.time()
    with _lock:
        q = _hits[bucket]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= limit:
            retry = max(1, int(60 - (now - q[0])))
            return False, retry
        q.append(now)
        return True, 0


def try_acquire(slug: str, endpoint_limit: int, global_limit: int) -> bool:
    global _running_global
    with _lock:
        if _running_global >= global_limit:
            return False
        if _running_slug[slug] >= endpoint_limit:
            return False
        _running_global += 1
        _running_slug[slug] += 1
        return True


def release(slug: str):
    global _running_global
    with _lock:
        _running_global = max(0, _running_global - 1)
        _running_slug[slug] = max(0, _running_slug[slug] - 1)


def snapshot() -> dict:
    with _lock:
        return {
            "running_global": _running_global,
            "running_by_slug": dict(_running_slug),
        }
