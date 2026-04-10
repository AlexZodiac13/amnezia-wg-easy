from __future__ import annotations

import base64
import io
import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path

import segno
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from app.config import Settings
from app.db import get_state, set_state


@dataclass(frozen=True)
class ServerProfile:
    private_key: str
    public_key: str


def generate_keypair() -> tuple[str, str]:
    private_key = x25519.X25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_key_b64 = base64.b64encode(
        private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode("ascii")
    public_key_b64 = base64.b64encode(public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")
    return private_key_b64, public_key_b64


def generate_preshared_key() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


def load_server_profile(settings: Settings, state_getter) -> ServerProfile:
    private_key = state_getter("server_private_key")
    public_key = state_getter("server_public_key")
    if private_key and public_key:
        return ServerProfile(private_key=private_key, public_key=public_key)

    private_key, public_key = generate_keypair()
    return ServerProfile(private_key=private_key, public_key=public_key)


def ensure_server_profile(conn, settings: Settings) -> ServerProfile:
    private_key = get_state(conn, "server_private_key")
    public_key = get_state(conn, "server_public_key")
    if private_key and public_key:
        return ServerProfile(private_key=private_key, public_key=public_key)

    private_key, public_key = generate_keypair()
    set_state(conn, "server_private_key", private_key)
    set_state(conn, "server_public_key", public_key)
    return ServerProfile(private_key=private_key, public_key=public_key)


def allocate_client_ip(existing_ips: list[str], settings: Settings) -> str:
    network = ipaddress.ip_network(settings.address_pool, strict=False)
    used_addresses = {ipaddress.ip_interface(settings.server_address).ip}
    for client_ip in existing_ips:
        used_addresses.add(ipaddress.ip_interface(client_ip).ip)

    for candidate in network.hosts():
        if candidate not in used_addresses:
            return f"{candidate}/{network.prefixlen}"

    raise ValueError("No available addresses left in the configured pool")


def amnezia_params(settings: Settings) -> dict[str, int]:
    return {
        "Jc": settings.amnezia_jc,
        "Jmin": settings.amnezia_jmin,
        "Jmax": settings.amnezia_jmax,
        "S1": settings.amnezia_s1,
        "S2": settings.amnezia_s2,
        "H1": settings.amnezia_h1,
        "H2": settings.amnezia_h2,
        "H3": settings.amnezia_h3,
        "H4": settings.amnezia_h4,
    }


def render_config(peer_row, settings: Settings, server_profile: ServerProfile) -> str:
    amnezia_block = "\n".join(f"{key} = {value}" for key, value in amnezia_params(settings).items())
    dns = settings.dns_servers.replace(",", ", ")
    return (
        "[Interface]\n"
        f"PrivateKey = {peer_row['private_key']}\n"
        f"Address = {peer_row['client_ip']}\n"
        f"DNS = {dns}\n"
        f"MTU = {settings.mtu}\n"
        f"{amnezia_block}\n\n"
        "[Peer]\n"
        f"PublicKey = {server_profile.public_key}\n"
        f"PresharedKey = {peer_row['preshared_key']}\n"
        f"Endpoint = {settings.server_endpoint_host}:{settings.server_endpoint_port}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        f"PersistentKeepalive = {settings.handshake_keepalive}\n"
    )


def qr_data_uri(config_text: str) -> str:
    qr = segno.make(config_text, error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=4)
    svg_bytes = buffer.getvalue()
    b64 = base64.b64encode(svg_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def qr_svg_bytes(config_text: str) -> bytes:
    qr = segno.make(config_text, error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=4)
    return buffer.getvalue()


def write_text(path: str, content: str) -> None:
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")
