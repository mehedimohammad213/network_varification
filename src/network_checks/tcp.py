"""TCP reachability. ICMP is not used: many paths block ping and still pass TCP."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class TcpResult:
    host: str
    port: int
    open: bool
    elapsed_ms: float
    address: str = ""
    error: str = ""


def check_tcp(host: str, port: int, timeout: float) -> TcpResult:
    """Try configured addresses until one accepts TCP or the budget runs out.

    Only the first address family that resolves is used, IPv4 preferred.
    The timeout is a deadline for the whole attempt, not per address, so a
    filtered port cannot multiply the wait by the number of A records.
    """
    started = time.perf_counter()
    try:
        infos = _resolve(host, port)
    except socket.gaierror as exc:
        return TcpResult(
            host=host,
            port=port,
            open=False,
            elapsed_ms=_elapsed(started),
            error=f"DNS: {exc}",
        )

    deadline = time.monotonic() + timeout
    errors: list[str] = []
    address = ""
    for info in infos:
        remaining = deadline - time.monotonic()
        if remaining <= 0.05:
            errors.append("deadline exceeded before the next address")
            break
        address = info[4][0]
        try:
            with socket.create_connection((address, port), timeout=remaining):
                return TcpResult(
                    host=host,
                    port=port,
                    open=True,
                    elapsed_ms=_elapsed(started),
                    address=address,
                )
        except OSError as exc:
            errors.append(f"{address}: {exc.__class__.__name__}: {exc}")
    return TcpResult(
        host=host,
        port=port,
        open=False,
        elapsed_ms=_elapsed(started),
        address=address,
        error="; ".join(errors) or "connection failed",
    )


def _resolve(host: str, port: int) -> list[tuple]:
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        infos = []
    if infos:
        return infos
    return socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)


def _elapsed(started: float) -> float:
    return (time.perf_counter() - started) * 1000
