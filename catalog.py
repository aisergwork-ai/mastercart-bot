"""Каталог карт. Для MVP — список товаров с картинкой в assets/.
Легко расширять: добавь запись и файл изображения. Картинка используется и в
карточке, и для примерки на стене.

Цены: в `prices_cm` — словарь {ширина_см: цена_₽}. Пока пусто — заполни реальными
ценами, и они сами появятся в карточке и при выборе размера. Без цен бот работает
как раньше (просто не показывает цену).
"""
from __future__ import annotations

import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# category: "Карты мира" | "Карты России"
PRODUCTS = [
    {
        "id": "world_borneo_grey",
        "title": "Карта мира «Борнео Грей»",
        "category": "Карты мира",
        "desc": "Многоуровневая, серо-голубые тона, с подсветкой.",
        "image": "world_borneo_grey.jpg",
        "widths_cm": [130, 150, 200],   # ширина × примерно 0.6 = высота
        "prices_cm": {},                # {130: 00000, 150: 00000, 200: 00000}
        "url": "https://mastercart.shop/catalog/karty_mira/mnogourovnevye/",
    },
    {
        "id": "world_borneo_turquoise",
        "title": "Карта мира «Борнео Бирюза»",
        "category": "Карты мира",
        "desc": "Многоуровневая, бирюзовые акценты, тёплое дерево, с подсветкой.",
        "image": "world_borneo_turquoise.jpg",
        "widths_cm": [130, 150, 200],
        "prices_cm": {},
        "url": "https://mastercart.shop/catalog/karty_mira/mnogourovnevye/",
    },
    {
        "id": "russia_borneo_brown",
        "title": "Карта России «Борнео Браун»",
        "category": "Карты России",
        "desc": "Многоуровневая карта России, тёплые коричневые тона, с подсветкой.",
        "image": "russia_borneo_brown.jpg",
        "widths_cm": [130, 150],
        "prices_cm": {},
        "url": "https://mastercart.shop/catalog/karty_rossii2/mnogourovnevye_rus/",
    },
    {
        "id": "russia_sib_taiga",
        "title": "Карта России «Сибирская тайга»",
        "category": "Карты России",
        "desc": "Многоуровневая карта России, природные зелёно-древесные оттенки.",
        "image": "russia_sib_taiga.jpg",
        "widths_cm": [130, 150],
        "prices_cm": {},
        "url": "https://mastercart.shop/catalog/karty_rossii2/mnogourovnevye_rus/",
    },
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


# ── цены ──────────────────────────────────────────────────────────────────────
def price_for(p: dict, width_cm: int) -> int | None:
    """Цена за конкретную ширину. Ключи словаря могут быть int или str."""
    prices = p.get("prices_cm") or {}
    return prices.get(width_cm) or prices.get(str(width_cm))


def min_price(p: dict) -> int | None:
    vals = [v for v in (p.get("prices_cm") or {}).values() if v]
    return min(vals) if vals else None


def fmt_price(v: int | None) -> str:
    """12345 -> '12 345 ₽'."""
    if not v:
        return ""
    return f"{int(v):,}".replace(",", " ") + " ₽"
