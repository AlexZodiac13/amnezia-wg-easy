from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import (
    count_enabled_peers,
    count_peers,
    delete_peer,
    get_connection,
    get_peer,
    get_peer_by_name,
    get_state,
    init_db,
    insert_peer,
    list_peers,
    update_peer,
)
from app.peers import allocate_client_ip, ensure_server_profile, generate_keypair, generate_preshared_key, load_server_profile, qr_data_uri, qr_svg_bytes, render_config
from app.runtime import server_config_text, sync_runtime_files
from app.security import is_valid_admin_login


BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
security = HTTPBasic(auto_error=False)


app = FastAPI(title="AmneziaWG Admin")
app.add_middleware(SessionMiddleware, secret_key=get_settings().secret_key, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class PeerCreateRequest(BaseModel):
    name: str


def db_conn(settings: Settings = Depends(get_settings)) -> sqlite3.Connection:
    connection = get_connection(settings)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def require_admin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if request.session.get("is_admin"):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.on_event("startup")
def on_startup() -> None:
    settings = get_settings()
    init_db(settings)
    with get_connection(settings) as conn:
        ensure_server_profile(conn, settings)
        sync_runtime_files(conn, settings)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, settings: Settings = Depends(get_settings), conn: sqlite3.Connection = Depends(db_conn)):
    if not request.session.get("is_admin"):
        return RedirectResponse(url="/login", status_code=303)

    peers = list_peers(conn)
    server_profile = ensure_server_profile(conn, settings)

    rendered_peers = []
    for peer in peers:
        config_text = render_config(peer, settings, server_profile)
        rendered_peers.append(
            {
                **dict(peer),
                "config_text": config_text,
                "qr_uri": qr_data_uri(config_text),
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "settings": settings,
            "peers": rendered_peers,
            "stats": {
                "total": count_peers(conn),
                "enabled": count_enabled_peers(conn),
            },
            "server_profile": server_profile,
            "server_endpoint": f"{settings.server_endpoint_host}:{settings.server_endpoint_port}",
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "app_name": get_settings().app_name},
    )


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), settings: Settings = Depends(get_settings)):
    if not is_valid_admin_login(settings, username, password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "app_name": settings.app_name, "error": "Неверный логин или пароль"},
            status_code=401,
        )

    request.session["is_admin"] = True
    return RedirectResponse(url="/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.post("/peers")
def create_peer(
    request: Request,
    name: str = Form(...),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(db_conn),
    _: None = Depends(require_admin),
):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    if get_peer_by_name(conn, name):
        raise HTTPException(status_code=409, detail="Peer already exists")

    existing_ips = [row["client_ip"] for row in list_peers(conn)]
    client_ip = allocate_client_ip(existing_ips, settings)
    private_key, public_key = generate_keypair()
    preshared_key = generate_preshared_key()
    insert_peer(conn, name=name, public_key=public_key, private_key=private_key, preshared_key=preshared_key, client_ip=client_ip)
    sync_runtime_files(conn, settings)
    return RedirectResponse(url="/", status_code=303)


@app.post("/peers/{peer_id}/toggle")
def toggle_peer(peer_id: int, conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    update_peer(conn, peer_id, enabled=0 if peer["enabled"] else 1)
    sync_runtime_files(conn, get_settings())
    return RedirectResponse(url="/", status_code=303)


@app.post("/peers/{peer_id}/delete")
def remove_peer(peer_id: int, conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    delete_peer(conn, peer_id)
    sync_runtime_files(conn, get_settings())
    return RedirectResponse(url="/", status_code=303)


@app.get("/peers/{peer_id}", response_class=HTMLResponse)
def peer_detail(request: Request, peer_id: int, settings: Settings = Depends(get_settings), conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    server_profile = load_server_profile(settings, lambda key: get_state(conn, key))
    config_text = render_config(peer, settings, server_profile)
    return templates.TemplateResponse(
        request=request,
        name="peer_detail.html",
        context={
            "request": request,
            "peer": dict(peer),
            "config_text": config_text,
            "qr_url": f"/peers/{peer_id}/qr.svg",
            "server_endpoint": f"{settings.server_endpoint_host}:{settings.server_endpoint_port}",
        },
    )


@app.get("/peers/{peer_id}/qr.svg")
def peer_qr_svg(peer_id: int, settings: Settings = Depends(get_settings), conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    server_profile = ensure_server_profile(conn, settings)
    config_text = render_config(peer, settings, server_profile)
    return Response(content=qr_svg_bytes(config_text), media_type="image/svg+xml")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def api_login(credentials: HTTPBasicCredentials = Depends(security), settings: Settings = Depends(get_settings)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing credentials")
    if not is_valid_admin_login(settings, credentials.username, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"ok": True, "message": "Login successful"}


@app.get("/api/peers")
def api_list_peers(conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    return {"items": [dict(peer) for peer in list_peers(conn)]}


@app.get("/api/peers/{peer_id}")
def api_get_peer(peer_id: int, settings: Settings = Depends(get_settings), conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    server_profile = load_server_profile(settings, lambda key: get_state(conn, key))
    config_text = render_config(peer, settings, server_profile)
    return {"item": {**dict(peer), "config_text": config_text}}


@app.post("/api/peers")
def api_create_peer(
    payload: PeerCreateRequest = Body(...),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(db_conn),
    _: None = Depends(require_admin),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if len(name) > 64:
        raise HTTPException(status_code=422, detail="name is too long")
    if get_peer_by_name(conn, name):
        raise HTTPException(status_code=409, detail="peer already exists")
    existing_ips = [row["client_ip"] for row in list_peers(conn)]
    client_ip = allocate_client_ip(existing_ips, settings)
    private_key, public_key = generate_keypair()
    preshared_key = generate_preshared_key()
    peer_id = insert_peer(conn, name=name, public_key=public_key, private_key=private_key, preshared_key=preshared_key, client_ip=client_ip)
    sync_runtime_files(conn, settings)
    return {"id": peer_id, "name": name, "client_ip": client_ip}


@app.delete("/api/peers/{peer_id}")
def api_delete_peer(peer_id: int, conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    delete_peer(conn, peer_id)
    sync_runtime_files(conn, get_settings())
    return Response(status_code=204)


@app.post("/api/peers/{peer_id}/toggle")
def api_toggle_peer(peer_id: int, conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    new_value = 0 if peer["enabled"] else 1
    update_peer(conn, peer_id, enabled=new_value)
    sync_runtime_files(conn, get_settings())
    return {"id": peer_id, "enabled": bool(new_value)}


@app.get("/api/stats")
def api_stats(conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    return {"total": count_peers(conn), "enabled": count_enabled_peers(conn)}


@app.get("/api/server-config")
def api_server_config(settings: Settings = Depends(get_settings), conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    return Response(content=server_config_text(conn, settings), media_type="text/plain")


@app.get("/api/peers/{peer_id}/config")
def api_peer_config(peer_id: int, settings: Settings = Depends(get_settings), conn: sqlite3.Connection = Depends(db_conn), _: None = Depends(require_admin)):
    peer = get_peer(conn, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found")
    server_profile = ensure_server_profile(conn, settings)
    return Response(content=render_config(peer, settings, server_profile), media_type="text/plain")
