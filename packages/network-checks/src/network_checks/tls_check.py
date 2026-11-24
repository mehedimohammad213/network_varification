"""TLS handshake and certificate verification. Verification fails closed."""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class TlsError(Exception):
    def __init__(self, message: str, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class TlsHandshake:
    host: str
    port: int
    protocol: str
    cipher: str
    subject: str
    days_remaining: float | None = None


def tls_handshake(host: str, port: int, timeout: float, server_hostname: str | None = None) -> TlsHandshake:
    """Complete a verified handshake. server_hostname defaults to host (SNI)."""
    context = ssl.create_default_context()
    return _handshake(context, host, port, timeout, server_hostname or host)


def mtls_handshake(
    host: str,
    port: int,
    timeout: float,
    cert_file: str,
    key_file: str,
    ca_file: str | None = None,
    server_hostname: str | None = None,
) -> TlsHandshake:
    """Verified handshake presenting a client certificate (fintech gateways)."""
    cert_path = Path(cert_file).expanduser()
    key_path = Path(key_file).expanduser()
    if not cert_path.is_file():
        raise TlsError(f"client cert not found: {cert_path}", kind="config")
    if not key_path.is_file():
        raise TlsError(f"client key not found: {key_path}", kind="config")
    context = ssl.create_default_context()
    if ca_file:
        ca_path = Path(ca_file).expanduser()
        if not ca_path.is_file():
            raise TlsError(f"CA file not found: {ca_path}", kind="config")
        context.load_verify_locations(cafile=str(ca_path))
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return _handshake(context, host, port, timeout, server_hostname or host)


def days_remaining_for_host(host: str, port: int, timeout: float, server_hostname: str | None = None) -> float:
    """Return whole days left on the peer certificate (fractional)."""
    handshake = tls_handshake(host, port, timeout, server_hostname=server_hostname)
    if handshake.days_remaining is None:
        raise TlsError(f"{host}: peer certificate has no notAfter", kind="verify")
    return handshake.days_remaining


def _handshake(
    context: ssl.SSLContext,
    host: str,
    port: int,
    timeout: float,
    server_hostname: str,
) -> TlsHandshake:
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=server_hostname) as tls:
                cipher = tls.cipher()
                cert = tls.getpeercert()
                return TlsHandshake(
                    host=host,
                    port=port,
                    protocol=tls.version() or "",
                    cipher=cipher[0] if cipher else "",
                    subject=_subject(cert),
                    days_remaining=_days_remaining(cert),
                )
    except ssl.SSLCertVerificationError as exc:
        raise TlsError(str(exc), kind="verify") from exc
    except ssl.SSLError as exc:
        raise TlsError(str(exc), kind="handshake") from exc
    except TimeoutError as exc:
        raise TlsError(str(exc), kind="timeout") from exc
    except OSError as exc:
        raise TlsError(str(exc), kind="connect") from exc


def _subject(cert: dict | None) -> str:
    if not cert:
        return ""
    parts: list[str] = []
    for item in cert.get("subject", ()):
        for key, value in item:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _days_remaining(cert: dict | None) -> float | None:
    if not cert or not cert.get("notAfter"):
        return None
    # OpenSSL format from ssl: 'Jun 15 12:00:00 2025 GMT'
    not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    return (not_after - datetime.now(timezone.utc)).total_seconds() / 86400.0
