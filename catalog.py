"""Каталог карт. Список товаров с картинкой в assets/.
Легко расширять: добавь запись и файл изображения. Картинка используется и в
карточке, и для примерки на стене (для примерки нужен чистый фон).

Поля:
  fit — показывать ли «Примерить на свою стену». True только у моделей с чистым
        студийным фото (иначе вырезка карты на стене выходит грязной). У витринных
        моделей (интерьерное фото) fit=False — карточка + «Заказать» без примерки.
  prices_cm — {ширина_см: цена_₽}. Пока пусто: заполнишь — цены сами появятся.
"""
from __future__ import annotations

import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

WORLD_URL = "https://mastercart.shop/catalog/karty_mira/mnogourovnevye/"
RUS_URL = "https://mastercart.shop/catalog/karty_rossii2/mnogourovnevye_rus/"

# category: "Карты мира" | "Карты России"
PRODUCTS = [
    # ── Карты мира (с примеркой — чистые студийные фото) ──────────────────────
    {"id": "world_borneo_grey", "title": "Карта мира «Борнео Грей»", "category": "Карты мира",
     "desc": "Серо-голубые тона, многоуровневая, с подсветкой.",
     "image": "world_borneo_grey.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": True, "url": WORLD_URL},
    {"id": "world_borneo_turquoise", "title": "Карта мира «Борнео Бирюза»", "category": "Карты мира",
     "desc": "Бирюзовые акценты, тёплое дерево, с подсветкой.",
     "image": "world_borneo_turquoise.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": True, "url": WORLD_URL},
    {"id": "world_borneo_brown", "title": "Карта мира «Борнео Браун»", "category": "Карты мира",
     "desc": "Тёплые коричневые тона, многоуровневая, с подсветкой.",
     "image": "world_borneo_brown.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": True, "url": WORLD_URL},
    {"id": "world_redwood", "title": "Карта мира «Ред Вуд»", "category": "Карты мира",
     "desc": "Насыщенные красно-древесные оттенки, многоуровневая, с подсветкой.",
     "image": "world_redwood.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": True, "url": WORLD_URL},
    {"id": "world_borneo_light", "title": "Карта мира «Борнео Лайт»", "category": "Карты мира",
     "desc": "Светлое дерево, лёгкая и воздушная, с подсветкой.",
     "image": "world_borneo_light.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": True, "url": WORLD_URL},
    # ── Карты мира (витрина — интерьерное фото, пока без примерки) ─────────────
    {"id": "world_schwarzwald", "title": "Карта мира «Шварцвальд»", "category": "Карты мира",
     "desc": "Глубокий тёмный дуб, графичная и строгая, с подсветкой.",
     "image": "world_schwarzwald.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": False, "url": WORLD_URL},
    {"id": "world_belovezh", "title": "Карта мира «Беловежская пуща»", "category": "Карты мира",
     "desc": "Натуральные лесные оттенки дерева, с подсветкой.",
     "image": "world_belovezh.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": False, "url": WORLD_URL},
    {"id": "world_stone", "title": "Карта мира «Стоун Форест»", "category": "Карты мира",
     "desc": "Контраст тёмного дерева, эффектная подсветка.",
     "image": "world_stone.jpg", "widths_cm": [130, 150, 200], "prices_cm": {},
     "fit": False, "url": WORLD_URL},
    # ── Карты России ──────────────────────────────────────────────────────────
    {"id": "russia_borneo_brown", "title": "Карта России «Борнео Браун»", "category": "Карты России",
     "desc": "Многоуровневая карта России, тёплые коричневые тона, с подсветкой.",
     "image": "russia_borneo_brown.jpg", "widths_cm": [130, 150], "prices_cm": {},
     "fit": True, "url": RUS_URL},
    {"id": "russia_sib_taiga", "title": "Карта России «Сибирская тайга»", "category": "Карты России",
     "desc": "Многоуровневая карта России, природные зелёно-древесные оттенки.",
     "image": "russia_sib_taiga.jpg", "widths_cm": [130, 150], "prices_cm": {},
     "fit": True, "url": RUS_URL},
    {"id": "russia_lapland", "title": "Карта России «Лапландский лес»", "category": "Карты России",
     "desc": "Карта России, тёплые красно-янтарные оттенки дерева.",
     "image": "russia_lapland.jpg", "widths_cm": [130, 150], "prices_cm": {},
     "fit": False, "url": RUS_URL},
    {"id": "russia_shipov", "title": "Карта России «Шипов лес»", "category": "Карты России",
     "desc": "Карта России, насыщенное тёмное дерево, с подсветкой.",
     "image": "russia_shipov.jpg", "widths_cm": [130, 150], "prices_cm": {},
     "fit": False, "url": RUS_URL},
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


# ── цены ──────────────────────────────────────────────────────────────────────
def price_for(p: dict, width_cm: int) -> int | None:
    prices = p.get("prices_cm") or {}
    return prices.get(width_cm) or prices.get(str(width_cm))


def min_price(p: dict) -> int | None:
    vals = [v for v in (p.get("prices_cm") or {}).values() if v]
    return min(vals) if vals else None


def fmt_price(v: int | None) -> str:
    if not v:
        return ""
    return f"{int(v):,}".replace(",", " ") + " ₽"
