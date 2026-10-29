"""Примерка карты на фото стены.

Два шага:
1) compose_preview() — быстрый БЕСПЛАТНЫЙ предпросмотр: кладём реальное фото карты
   на стену программно (Pillow), позиция/размер задаются долями. Клиент двигает
   стрелками сколько угодно — без обращений к ИИ.
2) enhance() — ОДНА платная генерация (AITUNNEL / Nano Banana): доводит готовую
   вклейку до фотореализма (тени, подсветка, свет), НЕ меняя позицию/размер/дизайн.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import urllib.request

from PIL import Image, ImageChops

import config

log = logging.getLogger("aimockup")

ENHANCE_PROMPT = (
    "This image shows a wooden wall map placed on a room wall as a flat overlay. Make it look "
    "photorealistic: add natural soft drop shadows from the map's raised wooden layers, a warm LED "
    "backlight glow behind the map, and match the room's lighting so it looks physically mounted on "
    "the wall. Do NOT move, resize, redraw or restyle the map — keep its exact position, size, design, "
    "colors and labels. Keep the rest of the room photo unchanged. Output one photorealistic image."
)


def _map_rgba(map_path: str, target_w: int):
    """Фото карты с убранным белым фоном (мягкая альфа), масштабированное до ширины target_w."""
    mp = Image.open(map_path).convert("RGB")
    th = max(1, round(mp.height * target_w / mp.width))
    mp = mp.resize((target_w, th), Image.LANCZOS)
    r, g, b = mp.split()
    minc = ImageChops.darker(ImageChops.darker(r, g), b)      # светлый фон -> ~255
    alpha = minc.point(lambda p: 0 if p >= 232 else min(255, int((232 - p) * 3.0)))
    mp.putalpha(alpha)
    return mp


def compose_preview(wall_bytes: bytes, map_path: str, cx: float, cy: float, sz: float) -> bytes:
    """cx,cy — центр карты (доли ширины/высоты стены), sz — ширина карты (доля ширины стены)."""
    wall = Image.open(io.BytesIO(wall_bytes)).convert("RGB")
    W, H = wall.size
    tw = max(40, min(W, round(sz * W)))
    mp = _map_rgba(map_path, tw)
    x = round(cx * W - mp.width / 2)
    y = round(cy * H - mp.height / 2)
    out = wall.copy()
    out.paste(mp, (x, y), mp)
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def _data_url(src, max_side=1536) -> str:
    im = Image.open(src).convert("RGB") if not isinstance(src, Image.Image) else src
    w, h = im.size
    if max(w, h) > max_side:
        k = max_side / max(w, h)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def enhance(composite_bytes: bytes) -> bytes:
    """Доводит готовую вклейку до фотореализма одной генерацией. PNG-байты."""
    if not config.AITUNNEL_KEY:
        raise RuntimeError("AITUNNEL_KEY не задан")
    url = _data_url(Image.open(io.BytesIO(composite_bytes)))
    payload = {
        "model": config.AIMODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": ENHANCE_PROMPT},
            {"type": "image_url", "image_url": {"url": url}},
        ]}],
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
    return base64.b64decode(imgs[0]["image_url"]["url"].split(",", 1)[1])


def default_size_fraction(map_cm, wall_cm) -> float:
    if map_cm and wall_cm and wall_cm > 0:
        return max(0.15, min(0.9, map_cm / wall_cm))
    return 0.5
