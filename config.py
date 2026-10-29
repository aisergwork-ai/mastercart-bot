"""Конфигурация бота-примерочной деревянных карт."""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# AITUNNEL (Nano Banana / Gemini Image) — примерка карты на фото стены
AITUNNEL_KEY = os.environ.get("AITUNNEL_KEY", "").strip()
AITUNNEL_URL = os.environ.get("AITUNNEL_URL", "https://api.aitunnel.ru/v1/chat/completions").strip()
AIMODEL = os.environ.get("AIMODEL", "gemini-2.5-flash-image").strip()  # Flash — ~4x дешевле Pro

# Админы (Telegram id через запятую). Пусто -> первый /start станет админом.
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()}
# Чат менеджеров для заявок (можно задать и командой /setleadchat в нужном чате).
LEAD_CHAT_ID = os.environ.get("LEAD_CHAT_ID", "").strip()

# Лимит примерок на пользователя в сутки (контроль расходов на API). 0 = без лимита.
MOCKUP_DAILY_LIMIT = int(os.environ.get("MOCKUP_DAILY_LIMIT", "5"))

TZ = ZoneInfo(os.environ.get("TZ_NAME", "Asia/Yekaterinburg"))
DB_PATH = os.environ.get("DB_PATH", "data/bot.db").strip()

SITE_URL = os.environ.get("SITE_URL", "https://mastercart.shop").strip()
BRAND = os.environ.get("BRAND", "МастерКарт").strip()

# Пример «до/после» для хука на старте. Положи файлы в assets/ (или задай пути через env).
# Кнопка показа примера появляется, только если оба файла существуют.
_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
DEMO_BEFORE = os.environ.get("DEMO_BEFORE", os.path.join(_ASSETS, "demo_before.jpg")).strip()
DEMO_AFTER = os.environ.get("DEMO_AFTER", os.path.join(_ASSETS, "demo_after.jpg")).strip()
