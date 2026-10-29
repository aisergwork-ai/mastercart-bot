"""Примерка карты на фото стены через AITUNNEL (Nano Banana / Gemini Image).
Синхронная функция — в боте вызывать через asyncio.to_thread."""
from __future__ import annotations

import base64
import io
import json
import logging
import urllib.request

from PIL import Image

import config

log = logging.getLogger("aimockup")

PROMPT = (
    "You are given two photos. Photo 1 is the interior of a customer's room (walls, furniture). "
    "Photo 2 is a real multi-layered wooden wall map (a physical product with raised wooden layers, "
    "country/region labels and small blue lakes). "
    "Task: realistically place the wooden map from Photo 2 onto the largest suitable empty wall in Photo 1. "
    "Keep the map's exact design, proportions, colors and labels unchanged — do NOT redraw or restyle it. "
    "Match the room's perspective and lighting, cast soft natural drop shadows from the map's raised layers, "
    "and add a subtle warm LED backlight glow behind the map on the wall. By default center the map "
    "horizontally on the empty wall and place it at eye level — its vertical center about 150 cm from the "
    "floor, typically just above the sofa/furniture, NOT up near the ceiling. "
    "Keep the rest of the room photo unchanged. Output one photorealistic image, as if "
    "professionally photographed."
)


def _data_url(src, max_side=1536) -> str:
    im = Image.open(src).convert("RGB") if not isinstance(src, Image.Image) else src
    w, h = im.size
    if max(w, h) > max_side:
        k = max_side / max(w, h)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build_hint(map_width_cm: int | None, wall_width_cm: int | None,
               left_cm: int | None = None, top_cm: int | None = None) -> str:
    """Подсказка модели по масштабу и позиции карты на стене."""
    parts = []
    if map_width_cm and wall_width_cm and wall_width_cm > 0:
        frac = max(5, min(95, round(map_width_cm / wall_width_cm * 100)))
        parts.append(f"the physical map is about {map_width_cm} cm wide and the wall is about "
                     f"{wall_width_cm} cm wide, so the map must span about {frac}% of the visible "
                     f"wall width — size it exactly to this proportion, not smaller.")
    pos = []
    if left_cm is not None:
        pos.append(f"about {left_cm} cm from the left edge of the wall to the left edge of the map")
    if top_cm is not None:
        pos.append(f"about {top_cm} cm from the ceiling (top of the wall) to the top of the map")
    if pos:
        parts.append("Position the map so there is " + " and ".join(pos) + ".")
    return (" IMPORTANT: " + " ".join(parts)) if parts else ""


def make_mockup(wall_bytes: bytes, product_image_path: str, hint: str = "") -> bytes:
    """Возвращает PNG-байты примерки. Бросает RuntimeError при ошибке."""
    if not config.AITUNNEL_KEY:
        raise RuntimeError("AITUNNEL_KEY не задан")
    wall_url = _data_url(Image.open(io.BytesIO(wall_bytes)))
    prod_url = _data_url(product_image_path)
    payload = {
        "model": config.AIMODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT + hint},
                {"type": "image_url", "image_url": {"url": wall_url}},
                {"type": "image_url", "image_url": {"url": prod_url}},
            ],
        }],
        "modalities": ["image", "text"],
    }
    req = urllib.request.Request(
        config.AITUNNEL_URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {config.AITUNNEL_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"AITUNNEL HTTP {e.code}: {e.read().decode()[:200]}")
    msg = (res.get("choices") or [{}])[0].get("message", {})
    imgs = msg.get("images") or []
    if not imgs:
        raise RuntimeError("модель не вернула изображение: " + (msg.get("content") or "")[:200])
    url = imgs[0]["image_url"]["url"]
    return base64.b64decode(url.split(",", 1)[1])
