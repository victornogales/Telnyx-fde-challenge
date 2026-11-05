import hashlib
import secrets


def caller_key(e164: str) -> str:
    """First 16 hex chars of SHA-256 of the E.164 number."""
    digest = hashlib.sha256(e164.encode("utf-8")).hexdigest()
    return digest[:16]


def new_trace_id() -> str:
    return "tr_" + secrets.token_hex(6)
