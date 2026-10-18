"""Malware scan before parsing (FR-11.7). The scanner is an open decision (OPEN.md):
ClamAV as a private service, or a scanning API. Until then "basic" refuses the EICAR test
file and executables, which is not a real malware scan."""

import socket
import struct
from typing import Protocol

from boardroom.config import get_settings

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class Scanner(Protocol):
    def scan(self, data: bytes) -> str | None:
        """The threat's name, or None if the file is clean."""
        ...


class BasicScanner:
    def scan(self, data: bytes) -> str | None:
        if EICAR in data[:4096]:
            return "EICAR test file"
        if data.startswith((b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"#!")):
            return "executable"
        return None


class ClamdScanner:
    """Speaks clamd's INSTREAM protocol to a ClamAV service on the private network."""

    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port

    def scan(self, data: bytes) -> str | None:
        with socket.create_connection((self.host, self.port), timeout=60) as sock:
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 65536):
                chunk = data[i : i + 65536]
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = sock.recv(4096).decode(errors="replace").strip("\0 \n")
        if reply.endswith("OK"):
            return None
        if "FOUND" in reply:
            return reply.split(":", 1)[-1].replace("FOUND", "").strip()
        raise RuntimeError("virus scanner error")


def get_scanner() -> Scanner:
    s = get_settings()
    if s.scanner == "clamav":
        return ClamdScanner(s.clamav_host, s.clamav_port)
    return BasicScanner()
