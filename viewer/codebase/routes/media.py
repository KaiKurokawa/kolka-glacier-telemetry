"""Ретранслятор медиа-бэкенда: фото (latest_per_camera) + индикатор + байты картинки."""
import os
import requests
from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse, Response

router = APIRouter(prefix="/api/v1", tags=["Медиа (ретрансляция)"])

MEDIA_BASE_URL = os.getenv("INTERFACE_BASE_URL", "").rstrip("/")
TIMEOUT_META = 15
TIMEOUT_IMAGE = 30


def _unreachable(exc: Exception) -> JSONResponse:
    return JSONResponse(
        {"error": "media upstream unreachable",
         "detail": f"MEDIA_BASE_URL={MEDIA_BASE_URL or '(не задан)'}; {exc}"},
        status_code=502)


def _upstream_bad(r: requests.Response) -> JSONResponse:
    return JSONResponse(
        {"error": "media upstream error", "status": r.status_code,
         "body": (r.text or "")[:500]},
        status_code=r.status_code if r.status_code >= 400 else 502)


@router.get("/photos/latest_per_camera")
def relay_photos_per_camera():
    if not MEDIA_BASE_URL:
        return _unreachable(ValueError("MEDIA_BASE_URL не задан"))
    try:
        r = requests.get(f"{MEDIA_BASE_URL}/api/v1/photos/latest_per_camera",
                         timeout=TIMEOUT_META)
    except requests.RequestException as exc:
        return _unreachable(exc)
    if r.status_code != 200:
        return _upstream_bad(r)
    try:
        return JSONResponse(r.json())
    except ValueError:
        return JSONResponse({"error": "media upstream returned non-JSON"}, status_code=502)


@router.get("/indicator/")
def relay_indicator():
    if not MEDIA_BASE_URL:
        return _unreachable(ValueError("MEDIA_BASE_URL не задан"))
    try:
        r = requests.get(f"{MEDIA_BASE_URL}/api/v1/indicator/", timeout=TIMEOUT_META)
    except requests.RequestException as exc:
        return _unreachable(exc)
    if r.status_code != 200:
        return _upstream_bad(r)
    try:
        return JSONResponse(r.json())
    except ValueError:
        return JSONResponse({"error": "media upstream returned non-JSON"}, status_code=502)


@router.get("/photos/{photo_id}/image")
def relay_photo_image(photo_id: int = Path(..., ge=1)):
    if not MEDIA_BASE_URL:
        return _unreachable(ValueError("MEDIA_BASE_URL не задан"))
    try:
        r = requests.get(f"{MEDIA_BASE_URL}/api/v1/photos/{photo_id}/image",
                         timeout=TIMEOUT_IMAGE)
    except requests.RequestException as exc:
        return _unreachable(exc)
    if r.status_code != 200:
        return Response(content=r.content, status_code=r.status_code,
                        media_type=r.headers.get("content-type", "application/json"))
    return Response(content=r.content,
                    media_type=r.headers.get("content-type", "image/jpeg"))