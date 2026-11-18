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
import urllib.error
import urllib.request
import uuid

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


def _jpeg(im: Image.Image, max_side=1536) -> bytes:
    im = im.convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        k = max_side / max(w, h)
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (fn, data, ct) in files.items():
        out += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\n'
                f'Content-Type: {ct}\r\n\r\n').encode() + data + b"\r\n"
    return out + f"--{b}--\r\n".encode(), "multipart/form-data; boundary=" + b


def _enhance_edits(jpeg: bytes) -> bytes:
    """Основной путь: /v1/images/edits (с ноября 2026 AITUNNEL отдаёт картинки только так)."""
    body, ct = _multipart({"model": config.AIMODEL, "prompt": ENHANCE_PROMPT, "n": "1"},
                          {"image": ("wall.jpg", jpeg, "image/jpeg")})
    req = urllib.request.Request(config.AITUNNEL_IMG_URL, data=body,
                                 headers={"Authorization": f"Bearer {config.AITUNNEL_KEY}", "Content-Type": ct})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"AITUNNEL edits HTTP {e.code}: {e.read().decode()[:200]}")
    data = res.get("data") or []
    if not data or not data[0].get("b64_json"):
        raise RuntimeError("edits: модель не вернула изображение")
    return base64.b64decode(data[0]["b64_json"])


def _enhance_chat(jpeg: bytes) -> bytes:
    """Старый путь через chat/completions — запасной."""
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
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
        raise RuntimeError(f"AITUNNEL chat HTTP {e.code}: {e.read().decode()[:200]}")
    msg = (res.get("choices") or [{}])[0].get("message", {})
    imgs = msg.get("images") or []
    if not imgs:
        raise RuntimeError("chat: модель не вернула изображение: " + (msg.get("content") or "")[:200])
    return base64.b64decode(imgs[0]["image_url"]["url"].split(",", 1)[1])


def enhance(composite_bytes: bytes) -> bytes:
    """Доводит готовую вклейку до фотореализма одной генерацией. Байты изображения."""
    if not config.AITUNNEL_KEY:
        raise RuntimeError("AITUNNEL_KEY не задан")
    jpeg = _jpeg(Image.open(io.BytesIO(composite_bytes)))
    try:
        return _enhance_edits(jpeg)
    except Exception as e:
        log.warning("images/edits не сработал (%s), пробую chat/completions", e)
        return _enhance_chat(jpeg)


def default_size_fraction(map_cm, wall_cm) -> float:
    if map_cm and wall_cm and wall_cm > 0:
        return max(0.15, min(0.9, map_cm / wall_cm))
    return 0.5
