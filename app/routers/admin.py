import subprocess
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AccessMode,
    Camera,
    ObsInput,
    PlaybackType,
    SourceType,
    SystemSetting,
    Tournament,
    TournamentStatus,
    TournamentStream,
    User,
    UserRole,
)
from app.security import form_bool, generate_token, hash_password, require_admin_user
from app.services.access import set_tournament_password
from app.services.camera_check import update_camera_status
from app.services.ome import OmeService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_user)])
templates = Jinja2Templates(directory="app/templates")

LOG_SERVICES = {
    "app",
    "nginx",
    "mediamtx",
    "mediamtx-configurator",
    "postgres",
}

LOG_CONTAINERS = {
    "app": "bowling-portal-app-1",
    "nginx": "bowling-portal-nginx-1",
    "mediamtx": "bowling-portal-mediamtx-1",
    "mediamtx-configurator": "bowling-portal-mediamtx-configurator-1",
    "postgres": "bowling-portal-postgres-1",
}


def redirect(path: str = "/admin"):
    return RedirectResponse(path, status_code=303)


def read_service_logs(service: str, lines: int = 200) -> tuple[str, str | None]:
    if service not in LOG_SERVICES:
        return "", "Неизвестный сервис"
    safe_lines = max(20, min(lines, 1000))
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return "", "Docker CLI не найден в контейнере app. Пересоберите app: docker compose build app && docker compose up -d --force-recreate app"
    try:
        result = subprocess.run(
            [docker_bin, "compose", "logs", f"--tail={safe_lines}", service],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return "", str(exc)
    if result.returncode != 0:
        container = LOG_CONTAINERS[service]
        try:
            result = subprocess.run(
                [docker_bin, "logs", f"--tail={safe_lines}", container],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception as exc:
            return "", str(exc)
    output = (result.stdout or "") + (result.stderr or "")
    error = None if result.returncode == 0 else f"docker logs завершился с кодом {result.returncode}"
    return output, error


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    ome_ok, ome_status = await OmeService().check_status()
    stats = {
        "active_tournaments": db.scalar(select(func.count()).select_from(Tournament).where(Tournament.status == TournamentStatus.active)),
        "cameras": db.scalar(select(func.count()).select_from(Camera)),
        "active_streams": db.scalar(select(func.count()).select_from(TournamentStream).where(TournamentStream.is_active.is_(True))),
        "ome_ok": ome_ok,
        "ome_status": ome_status,
    }
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "stats": stats})


@router.get("/cameras", response_class=HTMLResponse)
def cameras(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/cameras.html", {"request": request, "items": db.query(Camera).order_by(Camera.id).all()})


@router.get("/cameras/new", response_class=HTMLResponse)
def camera_new(request: Request):
    return templates.TemplateResponse("admin/camera_form.html", {"request": request, "item": None})


@router.get("/cameras/{item_id}/edit", response_class=HTMLResponse)
def camera_edit(item_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/camera_form.html", {"request": request, "item": db.get(Camera, item_id)})


@router.post("/cameras")
async def camera_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    item = db.get(Camera, int(form["id"])) if form.get("id") else Camera()
    item.title = str(form["title"])
    item.description = str(form.get("description") or "")
    item.camera_type = str(form.get("camera_type") or "hikvision_rtsp")
    item.rtsp_url = str(form["rtsp_url"])
    item.rtsp_username = str(form.get("rtsp_username") or "")
    if form.get("rtsp_password"):
        item.rtsp_password = str(form["rtsp_password"])
    item.lane_from = int(form["lane_from"]) if form.get("lane_from") else None
    item.lane_to = int(form["lane_to"]) if form.get("lane_to") else None
    item.is_scoreboard_camera = form_bool(form.get("is_scoreboard_camera"))
    item.is_active = form_bool(form.get("is_active"))
    item.preview_url = str(form.get("preview_url") or "")
    if not item.ome_stream_name:
        db.add(item)
        db.flush()
        item.ome_stream_name = OmeService().generate_stream_name("camera", item.id)
    db.add(item)
    db.commit()
    return redirect("/admin/cameras")


@router.post("/cameras/{item_id}/delete")
def camera_delete(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Camera, item_id)
    if item:
        db.delete(item)
        db.commit()
    return redirect("/admin/cameras")


@router.post("/cameras/{item_id}/check")
def camera_check(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Camera, item_id)
    if item:
        update_camera_status(db, item)
    return redirect("/admin/cameras")


@router.get("/obs-inputs", response_class=HTMLResponse)
def obs_inputs(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/obs_inputs.html", {"request": request, "items": db.query(ObsInput).order_by(ObsInput.id).all()})


@router.get("/obs-inputs/new", response_class=HTMLResponse)
def obs_new(request: Request):
    return templates.TemplateResponse("admin/obs_form.html", {"request": request, "item": None})


@router.get("/obs-inputs/{item_id}/edit", response_class=HTMLResponse)
def obs_edit(item_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/obs_form.html", {"request": request, "item": db.get(ObsInput, item_id)})


@router.post("/obs-inputs")
async def obs_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    item = db.get(ObsInput, int(form["id"])) if form.get("id") else ObsInput(stream_key=generate_token(18))
    item.title = str(form["title"])
    item.description = str(form.get("description") or "")
    item.ingest_protocol = str(form.get("ingest_protocol") or "rtmp")
    item.stream_key = str(form.get("stream_key") or item.stream_key or generate_token(18))
    item.is_active = form_bool(form.get("is_active"))
    if not item.ome_stream_name:
        item.ome_stream_name = item.stream_key
    item.ingest_url = OmeService().obs_ingest_url(item.stream_key, item.ingest_protocol)
    db.add(item)
    db.commit()
    return redirect("/admin/obs-inputs")


@router.post("/obs-inputs/{item_id}/delete")
def obs_delete(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ObsInput, item_id)
    if item:
        db.delete(item)
        db.commit()
    return redirect("/admin/obs-inputs")


@router.get("/tournaments", response_class=HTMLResponse)
def tournaments(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/tournaments.html", {"request": request, "items": db.query(Tournament).order_by(Tournament.created_at.desc()).all()})


@router.get("/tournaments/new", response_class=HTMLResponse)
def tournament_new(request: Request):
    return templates.TemplateResponse("admin/tournament_form.html", {"request": request, "item": None})


@router.get("/tournaments/{item_id}/edit", response_class=HTMLResponse)
def tournament_edit(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(Tournament, item_id)
    return templates.TemplateResponse("admin/tournament_form.html", {"request": request, "item": item, "streams": item.streams if item else []})


@router.post("/tournaments")
async def tournament_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    item = db.get(Tournament, int(form["id"])) if form.get("id") else Tournament()
    item.title = str(form["title"])
    item.slug = str(form.get("slug") or slugify(item.title))
    item.description = str(form.get("description") or "")
    item.date_start = parse_dt(form.get("date_start"))
    item.date_end = parse_dt(form.get("date_end"))
    item.status = TournamentStatus(str(form.get("status") or "draft"))
    item.poster_image = str(form.get("poster_image") or "")
    item.is_public = form_bool(form.get("is_public"))
    item.access_mode = AccessMode(str(form.get("access_mode") or "public"))
    set_tournament_password(item, str(form.get("password") or ""))
    item.archive_enabled = form_bool(form.get("archive_enabled"))
    item.archive_depth_days = int(form.get("archive_depth_days") or 14)
    item.show_on_homepage = form_bool(form.get("show_on_homepage"))
    db.add(item)
    db.commit()
    return redirect("/admin/tournaments")


@router.post("/tournaments/{item_id}/delete")
def tournament_delete(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Tournament, item_id)
    if item:
        db.delete(item)
        db.commit()
    return redirect("/admin/tournaments")


@router.get("/tournaments/{tournament_id}/streams/new", response_class=HTMLResponse)
def stream_new(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/stream_form.html", context_for_stream_form(request, db, tournament_id, None))


@router.get("/streams/{item_id}/edit", response_class=HTMLResponse)
def stream_edit(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(TournamentStream, item_id)
    return templates.TemplateResponse("admin/stream_form.html", context_for_stream_form(request, db, item.tournament_id, item))


def context_for_stream_form(request: Request, db: Session, tournament_id: int, item: TournamentStream | None) -> dict:
    return {
        "request": request,
        "item": item,
        "tournament": db.get(Tournament, tournament_id),
        "cameras": db.query(Camera).order_by(Camera.title).all(),
        "obs_inputs": db.query(ObsInput).order_by(ObsInput.title).all(),
    }


@router.post("/streams")
async def stream_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    item = db.get(TournamentStream, int(form["id"])) if form.get("id") else TournamentStream()
    item.tournament_id = int(form["tournament_id"])
    item.title = str(form["title"])
    item.description = str(form.get("description") or "")
    item.source_type = SourceType(str(form.get("source_type") or "camera"))
    item.camera_id = int(form["camera_id"]) if form.get("camera_id") else None
    item.obs_input_id = int(form["obs_input_id"]) if form.get("obs_input_id") else None
    item.external_url = str(form.get("external_url") or "")
    item.playback_type = PlaybackType(str(form.get("playback_type") or "hls"))
    item.ome_app_name = str(form.get("ome_app_name") or "app")
    item.is_main = form_bool(form.get("is_main"))
    item.is_active = form_bool(form.get("is_active"))
    item.token_required = form_bool(form.get("token_required"))
    item.sort_order = int(form.get("sort_order") or 100)
    if item.source_type == SourceType.camera and item.camera_id:
        item.ome_stream_name = db.get(Camera, item.camera_id).ome_stream_name
    elif item.source_type == SourceType.obs and item.obs_input_id:
        item.ome_stream_name = db.get(ObsInput, item.obs_input_id).ome_stream_name
    elif not item.ome_stream_name:
        item.ome_stream_name = OmeService().generate_stream_name("stream")
    item.playback_url = item.external_url if item.source_type == SourceType.external else OmeService().playback_url(item.ome_app_name, item.ome_stream_name or "", item.playback_type.value)
    if item.is_main:
        db.query(TournamentStream).filter(TournamentStream.tournament_id == item.tournament_id).update({"is_main": False})
    db.add(item)
    db.commit()
    return redirect(f"/admin/tournaments/{item.tournament_id}/edit")


@router.post("/streams/{item_id}/delete")
def stream_delete(item_id: int, db: Session = Depends(get_db)):
    item = db.get(TournamentStream, item_id)
    tournament_id = item.tournament_id if item else None
    if item:
        db.delete(item)
        db.commit()
    return redirect(f"/admin/tournaments/{tournament_id}/edit" if tournament_id else "/admin/tournaments")


@router.get("/users", response_class=HTMLResponse)
def users(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/users.html", {"request": request, "items": db.query(User).order_by(User.id).all()})


@router.get("/users/new", response_class=HTMLResponse)
def user_new(request: Request):
    return templates.TemplateResponse("admin/user_form.html", {"request": request, "item": None})


@router.get("/users/{item_id}/edit", response_class=HTMLResponse)
def user_edit(item_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("admin/user_form.html", {"request": request, "item": db.get(User, item_id)})


@router.post("/users")
async def user_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    item = db.get(User, int(form["id"])) if form.get("id") else User()
    item.email = str(form["email"])
    item.username = str(form["username"])
    item.role = UserRole(str(form.get("role") or "operator"))
    item.is_active = form_bool(form.get("is_active"))
    if form.get("password"):
        item.password_hash = hash_password(str(form["password"]))
    db.add(item)
    db.commit()
    return redirect("/admin/users")


@router.post("/users/{item_id}/delete")
def user_delete(item_id: int, db: Session = Depends(get_db)):
    item = db.get(User, item_id)
    if item:
        db.delete(item)
        db.commit()
    return redirect("/admin/users")


@router.get("/settings", response_class=HTMLResponse)
def settings(request: Request, db: Session = Depends(get_db)):
    items = db.query(SystemSetting).order_by(SystemSetting.key).all()
    values = {item.key: item.value for item in items}
    return templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "items": items,
            "values": values,
        },
    )


@router.post("/settings")
async def settings_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    keys = form.getlist("key")
    values = form.getlist("value")
    descriptions = form.getlist("description")
    for key, value, description in zip(keys, values, descriptions):
        if not key:
            continue
        item = db.scalar(select(SystemSetting).where(SystemSetting.key == key)) or SystemSetting(key=key)
        item.value = value
        item.description = description
        db.add(item)
    db.commit()
    return redirect("/admin/settings")


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request, service: str = "mediamtx", lines: int = 200):
    logs, error = read_service_logs(service, lines)
    return templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "services": sorted(LOG_SERVICES),
            "selected_service": service,
            "lines": max(20, min(lines, 1000)),
            "logs": logs,
            "error": error,
        },
    )


@router.get("/ome", response_class=HTMLResponse)
async def ome_page(request: Request, db: Session = Depends(get_db)):
    service = OmeService()
    diagnostics = await service.diagnostics(str(request.base_url))
    config_text, config_error = service.config_text()
    config_paths, config_paths_error = await service.config_paths()
    active_paths, active_paths_error = await service.active_paths()
    path_diagnostics = service.path_diagnostics(active_paths)
    hls_muxers, hls_muxers_error = await service.hls_muxers()
    rtmp_connections, rtmp_connections_error = await service.rtmp_connections()
    rtsp_sessions, rtsp_sessions_error = await service.rtsp_sessions()
    streams = db.query(TournamentStream).order_by(TournamentStream.tournament_id, TournamentStream.sort_order).all()
    return templates.TemplateResponse(
        "admin/ome.html",
        {
            "request": request,
            "diagnostics": diagnostics,
            "config_text": config_text,
            "config_error": config_error,
            "config_paths": config_paths,
            "config_paths_error": config_paths_error,
            "active_paths": active_paths,
            "active_paths_error": active_paths_error,
            "path_diagnostics": path_diagnostics,
            "hls_muxers": hls_muxers,
            "hls_muxers_error": hls_muxers_error,
            "rtmp_connections": rtmp_connections,
            "rtmp_connections_error": rtmp_connections_error,
            "rtsp_sessions": rtsp_sessions,
            "rtsp_sessions_error": rtsp_sessions_error,
            "streams": streams,
            "cameras": db.query(Camera).order_by(Camera.id).all(),
            "obs_inputs": db.query(ObsInput).order_by(ObsInput.id).all(),
            "check_result": None,
        },
    )


@router.post("/ome/check-streams", response_class=HTMLResponse)
async def ome_check_streams(request: Request, db: Session = Depends(get_db)):
    service = OmeService()
    diagnostics = await service.diagnostics(str(request.base_url))
    config_text, config_error = service.config_text()
    config_paths, config_paths_error = await service.config_paths()
    active_paths, active_paths_error = await service.active_paths()
    path_diagnostics = service.path_diagnostics(active_paths)
    hls_muxers, hls_muxers_error = await service.hls_muxers()
    rtmp_connections, rtmp_connections_error = await service.rtmp_connections()
    rtsp_sessions, rtsp_sessions_error = await service.rtsp_sessions()
    streams = db.query(TournamentStream).order_by(TournamentStream.tournament_id, TournamentStream.sort_order).all()
    results = []
    for stream in streams:
        playback_url = (
            stream.external_url
            if stream.source_type == SourceType.external
            else service.browser_playback_url(stream.ome_app_name, stream.ome_stream_name or "", str(request.base_url))
        )
        ok, status = await service.check_stream(playback_url)
        results.append({"stream": stream, "playback_url": playback_url, "ok": ok, "status": status})
    return templates.TemplateResponse(
        "admin/ome.html",
        {
            "request": request,
            "diagnostics": diagnostics,
            "config_text": config_text,
            "config_error": config_error,
            "config_paths": config_paths,
            "config_paths_error": config_paths_error,
            "active_paths": active_paths,
            "active_paths_error": active_paths_error,
            "path_diagnostics": path_diagnostics,
            "hls_muxers": hls_muxers,
            "hls_muxers_error": hls_muxers_error,
            "rtmp_connections": rtmp_connections,
            "rtmp_connections_error": rtmp_connections_error,
            "rtsp_sessions": rtsp_sessions,
            "rtsp_sessions_error": rtsp_sessions_error,
            "streams": streams,
            "cameras": db.query(Camera).order_by(Camera.id).all(),
            "obs_inputs": db.query(ObsInput).order_by(ObsInput.id).all(),
            "check_result": results,
        },
    )


@router.post("/ome/regenerate-urls")
def ome_regenerate_urls(db: Session = Depends(get_db)):
    service = OmeService()
    for obs_input in db.query(ObsInput).all():
        obs_input.ingest_url = service.obs_ingest_url(obs_input.stream_key, obs_input.ingest_protocol)
    for stream in db.query(TournamentStream).all():
        if stream.source_type == SourceType.external:
            stream.playback_url = stream.external_url
        elif stream.ome_stream_name:
            stream.playback_url = service.playback_url(stream.ome_app_name, stream.ome_stream_name, stream.playback_type.value)
    db.commit()
    return redirect("/admin/ome")
