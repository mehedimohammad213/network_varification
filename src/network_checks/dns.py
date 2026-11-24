"""Name resolution via the system resolver, plus one direct UDP query.

The direct query is how NET-D04 talks to a resolver that must not answer.
stdlib sockets are enough; dnspython is not required.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass


class DNSError(Exception):
    def __init__(self, message: str, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class DnsAnswer:
    name: str
    addresses: tuple[str, ...]


def resolve(host: str) -> DnsAnswer:
    """Return unique IP addresses for host using the system resolver."""
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        kind = "nxdomain" if _is_negative(exc) else "resolver"
        raise DNSError(f"{host}: {exc}", kind=kind) from exc
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise DNSError(f"{host}: resolver returned no addresses", kind="resolver")
    return DnsAnswer(name=host, addresses=tuple(addresses))


def query_resolver(name: str, resolver: str, port: int, timeout: float) -> int:
    """Send one DNS A query. Return the rcode, or raise TimeoutError."""
    payload = _query_packet(name)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(payload, (resolver, port))
        packet, _source = sock.recvfrom(2048)
    except socket.timeout as exc:
        raise TimeoutError(f"resolver {resolver}:{port} did not answer within {timeout}s") from exc
    finally:
        sock.close()
    if len(packet) < 12:
        raise DNSError("short DNS response", kind="protocol")
    return packet[3] & 0x0F


def _is_negative(exc: socket.gaierror) -> bool:
    negative = {
        socket.EAI_NONAME,
        getattr(socket, "EAI_NODATA", -5),
        getattr(socket, "EAI_FAIL", -4),
    }
    return exc.errno in negative


def _query_packet(name: str) -> bytes:
    header = os.urandom(2) + b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    labels = b"".join(
        bytes([len(label)]) + label.encode("ascii")
        for label in name.strip(".").split(".")
        if label
    )
    question = labels + b"\x00" + (1).to_bytes(2, "big") + (1).to_bytes(2, "big")
    return header + question
