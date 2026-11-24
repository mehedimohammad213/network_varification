"""TLS handshake and certificate verification. Verification fails closed."""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass


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


def tls_handshake(host: str, port: int, timeout: float, server_hostname: str | None = None) -> TlsHandshake:
    """Complete a verified handshake. server_hostname defaults to host (SNI)."""
    context = ssl.create_default_context()
    name = server_hostname or host
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=name) as tls:
                cipher = tls.cipher()
                return TlsHandshake(
                    host=host,
                    port=port,
                    protocol=tls.version() or "",
                    cipher=cipher[0] if cipher else "",
                    subject=_subject(tls.getpeercert()),
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
