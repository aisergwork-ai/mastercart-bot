"""Каталог карт: товары с фото в assets/, реальными размерами и ценами.

Структура размера (sizes[i]) — словарь с базовой ценой и ценами опций:
  w, h    — ширина/высота, см
  base    — цена база (без подсветки/оргстекла/антарктиды)
  org     — доплата за оргстекло
  led     — доплата за подсветку (провода)
  led_acc — доплата за подсветку (аккумулятор)
  ant     — доплата за Антарктиду (None = недоступно, напр. у карт России)
  eng     — доплата за цветную гравировку (None = недоступно)
Для многоцветной подсветки в прайсе +3000 (LED_MULTICOLOR_EXTRA).

Сейчас бот показывает только базовую цену («от N ₽»). Матрица опций лежит здесь
заранее — под будущий конфигуратор (галочки → пересчёт цены).

fit — показывать ли «Примерить» (True только где чистое студийное фото).
"""
from __future__ import annotations

import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
WORLD_URL = "https://mastercart.shop/catalog/karty_mira/mnogourovnevye/"
RUS_URL = "https://mastercart.shop/catalog/karty_rossii2/mnogourovnevye_rus/"
LED_MULTICOLOR_EXTRA = 3000  # доплата за многоцветную подсветку (из прайса)


def _sz(w, h, base, org, led, led_acc, ant, eng):
    return {"w": w, "h": h, "base": base, "org": org, "led": led,
            "led_acc": led_acc, "ant": ant, "eng": eng}


# размеры Борнео (многоуровневая, карта мира) — общие для Браун/Бирюза/Грей/Лайт
_BORNEO_W = [
    _sz(130, 75, 7900, 5000, 6000, 8500, 400, 2000),
    _sz(160, 95, 10900, 6000, 6500, 9000, 500, 2000),
    _sz(200, 130, 16900, 8500, 7000, 9500, 700, 2000),
    _sz(250, 160, 20900, 12000, 9000, 12500, 1000, 2500),
    _sz(300, 180, 22900, 15000, 11000, 14000, 2500, 3000),
]
# Супер премиум (Ред Вуд, Стоун Форест) — одинаковый прайс
_SUPER = [
    _sz(150, 90, 33900, 9000, 6000, 8500, 700, 2000),
    _sz(200, 130, 44400, 11500, 7000, 9500, 1000, 2000),
    _sz(250, 160, 53400, 12000, 9000, 12000, 2000, 2500),
    _sz(300, 180, 59400, 15000, 11000, 14000, 2500, 3000),
]
# Карты России — размеры 130/200/300; антарктида/гравировка недоступны (None)
_RUS_SIZES = lambda b1, b2, b3: [
    _sz(130, 70, b1, 9000, 7000, 9000, None, None),
    _sz(200, 100, b2, 11000, 8000, 10000, None, None),
    _sz(300, 160, b3, 20000, 11000, 14000, None, None),
]

PRODUCTS = [
    # ── Карты мира (с примеркой) ──────────────────────────────────────────────
    {"id": "world_borneo_grey", "title": "Карта мира «Борнео Грей»", "category": "Карты мира",
     "desc": "Серо-голубые тона, многоуровневая, с подсветкой.",
     "image": "world_borneo_grey.jpg", "fit": True, "url": WORLD_URL, "sizes": _BORNEO_W},
    {"id": "world_borneo_turquoise", "title": "Карта мира «Борнео Бирюза»", "category": "Карты мира",
     "desc": "Бирюзовые акценты, тёплое дерево, с подсветкой.",
     "image": "world_borneo_turquoise.jpg", "fit": True, "url": WORLD_URL, "sizes": _BORNEO_W},
    {"id": "world_borneo_brown", "title": "Карта мира «Борнео Браун»", "category": "Карты мира",
     "desc": "Тёплые коричневые тона, многоуровневая, с подсветкой.",
     "image": "world_borneo_brown.jpg", "fit": True, "url": WORLD_URL, "sizes": _BORNEO_W},
    {"id": "world_redwood", "title": "Карта мира «Ред Вуд»", "category": "Карты мира",
     "desc": "Насыщенные красно-древесные оттенки, многоуровневая, с подсветкой.",
     "image": "world_redwood.jpg", "fit": True, "url": WORLD_URL, "sizes": _SUPER},
    {"id": "world_borneo_light", "title": "Карта мира «Борнео Лайт»", "category": "Карты мира",
     "desc": "Светлое дерево, лёгкая и воздушная, с подсветкой.",
     "image": "world_borneo_light.jpg", "fit": True, "url": WORLD_URL, "sizes": _BORNEO_W},
    # ── Карты мира (витрина) ──────────────────────────────────────────────────
    {"id": "world_schwarzwald", "title": "Карта мира «Шварцвальд»", "category": "Карты мира",
     "desc": "Глубокий тёмный дуб, графичная и строгая, с подсветкой.",
     "image": "world_schwarzwald.jpg", "fit": False, "url": WORLD_URL, "sizes": [
         _sz(150, 90, 12900, 6000, 6000, 8500, 500, 2000),
         _sz(200, 130, 17400, 8500, 7000, 9500, 700, 2000),
         _sz(250, 160, 21400, 12000, 9000, 12000, 2000, 2500),
         _sz(300, 180, 24400, 15000, 11000, 14000, 2500, 3000)]},
    {"id": "world_belovezh", "title": "Карта мира «Беловежская пуща»", "category": "Карты мира",
     "desc": "Натуральные лесные оттенки дерева, с подсветкой.",
     "image": "world_belovezh.jpg", "fit": False, "url": WORLD_URL, "sizes": [
         _sz(150, 90, 15900, 6000, 5000, 7500, 500, 2000),
         _sz(200, 130, 21400, 8500, 7000, 9500, 700, 2000),
         _sz(250, 160, 27700, 12000, 9000, 12000, 2000, 2500),
         _sz(300, 180, 32600, 15000, 11000, 14000, 2500, 3000)]},
    {"id": "world_stone", "title": "Карта мира «Стоун Форест»", "category": "Карты мира",
     "desc": "Контраст тёмного дерева, эффектная подсветка.",
     "image": "world_stone.jpg", "fit": False, "url": WORLD_URL, "sizes": _SUPER},
    # ── Карты России ──────────────────────────────────────────────────────────
    {"id": "russia_borneo_brown", "title": "Карта России «Борнео Браун»", "category": "Карты России",
     "desc": "Многоуровневая карта России, тёплые коричневые тона, с подсветкой.",
     "image": "russia_borneo_brown.jpg", "fit": True, "url": RUS_URL, "sizes": [
         _sz(130, 70, 12000, 9000, 7000, 9000, None, 2000),
         _sz(160, 85, 15000, 10000, 7500, 9500, None, 2000),
         _sz(200, 110, 19000, 11000, 8000, 10000, None, 2000),
         _sz(300, 160, 29000, 20000, 11000, 14000, None, 3000)]},
    {"id": "russia_sib_taiga", "title": "Карта России «Сибирская тайга»", "category": "Карты России",
     "desc": "Многоуровневая карта России, природные зелёно-древесные оттенки.",
     "image": "russia_sib_taiga.jpg", "fit": True, "url": RUS_URL,
     "sizes": _RUS_SIZES(13900, 18900, 30900)},
    {"id": "russia_lapland", "title": "Карта России «Лапландский лес»", "category": "Карты России",
     "desc": "Карта России, тёплые красно-янтарные оттенки дерева.",
     "image": "russia_lapland.jpg", "fit": False, "url": RUS_URL,
     "sizes": _RUS_SIZES(13900, 18900, 30900)},
    {"id": "russia_shipov", "title": "Карта России «Шипов лес»", "category": "Карты России",
     "desc": "Карта России, насыщенное тёмное дерево, с подсветкой.",
     "image": "russia_shipov.jpg", "fit": False, "url": RUS_URL,
     "sizes": _RUS_SIZES(9900, 14900, 26900)},
]

_BY_ID = {p["id"]: p for p in PRODUCTS}


def categories() -> list[str]:
    seen = []
    for p in PRODUCTS:
        if p["category"] not in seen:
            seen.append(p["category"])
    return seen


def by_category(cat: str) -> list[dict]:
    return [p for p in PRODUCTS if p["category"] == cat]


def get(pid: str) -> dict | None:
    return _BY_ID.get(pid)


def image_path(p: dict) -> str:
    return os.path.join(ASSETS, p["image"])


def is_fittable(p: dict) -> bool:
    return bool(p.get("fit", True))


# ── размеры и цены ────────────────────────────────────────────────────────────
def sizes(p: dict) -> list[dict]:
    return p.get("sizes") or []


def widths(p: dict) -> list[int]:
    return [s["w"] for s in sizes(p)]


def size_of(p: dict, width_cm: int) -> dict | None:
    for s in sizes(p):
        if s["w"] == width_cm:
            return s
    return None


def price_for(p: dict, width_cm: int) -> int | None:
    """Базовая цена за ширину (пока показываем именно базу)."""
    s = size_of(p, width_cm)
    return s["base"] if s else None


def min_price(p: dict) -> int | None:
    vals = [s["base"] for s in sizes(p) if s.get("base")]
    return min(vals) if vals else None


def fmt_price(v: int | None) -> str:
    if not v:
        return ""
    return f"{int(v):,}".replace(",", " ") + " ₽"
