from typing import Dict, Any
# from .config import DEFAULT_TZ

def ensure_user_bucket(ud: Dict[str, Any]):
    # ud.setdefault("tz", DEFAULT_TZ)
    ud.setdefault("gid_next", 1)
    ud.setdefault("items", {})  # gid -> {id, kind, ...}

def alloc_gid(ud: Dict[str, Any]) -> str:
    gid = str(ud["gid_next"])
    ud["gid_next"] += 1
    return gid
