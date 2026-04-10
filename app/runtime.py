from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.db import get_state, list_peers
from app.peers import ServerProfile, ensure_server_profile, render_config, write_text


def runtime_root(settings: Settings) -> Path:
    return Path(settings.database_path).expanduser().resolve().parent / "runtime"


def server_config_text(conn, settings: Settings) -> str:
    profile = ensure_server_profile(conn, settings)
    peer_rows = list_peers(conn)
    peers = [peer for peer in peer_rows if int(peer["enabled"]) == 1]

    amnezia_lines = [
        f"Jc = {settings.amnezia_jc}",
        f"Jmin = {settings.amnezia_jmin}",
        f"Jmax = {settings.amnezia_jmax}",
        f"S1 = {settings.amnezia_s1}",
        f"S2 = {settings.amnezia_s2}",
        f"H1 = {settings.amnezia_h1}",
        f"H2 = {settings.amnezia_h2}",
        f"H3 = {settings.amnezia_h3}",
        f"H4 = {settings.amnezia_h4}",
    ]

    server_lines = [
        "[Interface]",
        f"PrivateKey = {profile.private_key}",
        f"Address = {settings.server_address}",
        f"ListenPort = {settings.listen_port}",
        f"MTU = {settings.mtu}",
        *amnezia_lines,
        "",
    ]

    for peer in peers:
        server_lines.extend(
            [
                "[Peer]",
                f"PublicKey = {peer['public_key']}",
                f"PresharedKey = {peer['preshared_key']}",
                f"AllowedIPs = {peer['client_ip']}",
                "",
            ]
        )

    return "\n".join(server_lines).rstrip() + "\n"


def sync_runtime_files(conn, settings: Settings) -> None:
    root = runtime_root(settings)
    peer_dir = root / "peers"
    peer_dir.mkdir(parents=True, exist_ok=True)

    profile = ensure_server_profile(conn, settings)
    server_text = server_config_text(conn, settings)
    write_text(str(root / "server.conf"), server_text)

    for peer in list_peers(conn):
        if int(peer["enabled"]) != 1:
            continue
        peer_text = render_config(peer, settings, profile)
        safe_name = "".join(ch for ch in peer["name"] if ch.isalnum() or ch in {"-", "_"}).strip("._-") or f"peer-{peer['id']}"
        write_text(str(peer_dir / f"{safe_name}.conf"), peer_text)
