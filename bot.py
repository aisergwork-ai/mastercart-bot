"""Telegram-бот «примерочная» деревянных карт: каталог → выбор карты →
фото стены → фотореалистичная примерка (Nano Banana) → заявка."""
from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import os
from urllib.parse import quote

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters,
)

import aimockup
import catalog
import config
import db

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
log = logging.getLogger("bot")


# ── вспомогательное ─────────────────────────────────────────────────────────────
def demo_available() -> bool:
    return bool(config.DEMO_BEFORE and config.DEMO_AFTER
                and os.path.exists(config.DEMO_BEFORE) and os.path.exists(config.DEMO_AFTER))


async def bot_link(context) -> str:
    link = context.bot_data.get("bot_link")
    if not link:
        me = await context.bot.get_me()
        link = context.bot_data["bot_link"] = f"https://t.me/{me.username}"
    return link


def discount_text() -> str:
    val = db.get_meta("discount_text")  # None = админ не трогал -> дефолт; "" = намеренно убрано
    return config.DISCOUNT_DEFAULT if val is None else val.strip()


# ── меню / каталог ────────────────────────────────────────────────────────────
def main_menu_kb():
    rows = [[InlineKeyboardButton("🗺 Каталог карт", callback_data="catalog")]]
    if demo_available():
        rows.append([InlineKeyboardButton("👀 Пример: как это выглядит", callback_data="demo")])
    rows.append([InlineKeyboardButton("🖼 Мои примерки", callback_data="myfits")])
    rows.append([InlineKeyboardButton("🌐 Сайт", url=config.SITE_URL)])
    return InlineKeyboardMarkup(rows)


def catalog_kb():
    cats = catalog.categories()
    rows = [[InlineKeyboardButton(c, callback_data=f"cat:{i}")] for i, c in enumerate(cats)]
    rows.append([InlineKeyboardButton("« В меню", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def category_kb(cat_idx: int):
    cats = catalog.categories()
    cat = cats[cat_idx]
    rows = [[InlineKeyboardButton(p["title"], callback_data=f"prod:{p['id']}")]
            for p in catalog.by_category(cat)]
    rows.append([InlineKeyboardButton("« Категории", callback_data="catalog")])
    return InlineKeyboardMarkup(rows)


def product_kb(pid: str):
    p = catalog.get(pid)
    rows = []
    if p and catalog.is_fittable(p):
        rows.append([InlineKeyboardButton("🪄 Примерить на свою стену", callback_data=f"fit:{pid}")])
    rows.append([InlineKeyboardButton("🛒 Заказать / задать вопрос", callback_data=f"order:{pid}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="catalog")])
    return InlineKeyboardMarkup(rows)


WELCOME = (
    "Привет! Это бот «{brand}» — деревянные карты мира и России для интерьера.\n\n"
    "Главная фишка: выбери карту и пришли фото своей стены — покажу, "
    "как она будет выглядеть именно у тебя, с подсветкой. Бесплатно.\n\n"
    "Загляни в каталог 👇"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.full_name, u.username)
    if not db.any_admin_exists():
        db.make_admin(u.id)
    context.user_data.clear()
    # реферальная метка из deep-link (t.me/bot?start=ref_123)
    arg = context.args[0] if getattr(context, "args", None) else ""
    db.log_event(u.id, "start", arg if arg.startswith("ref_") else None)
    await update.message.reply_text(WELCOME.format(brand=config.BRAND), reply_markup=main_menu_kb())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["/start — меню и каталог"]
    if db.is_admin(update.effective_user.id):
        lines += ["/setleadchat — слать заявки в текущий чат", "/leads — последние заявки",
                  "/setdiscount <текст> — акция после примерки (пусто — убрать)",
                  "/stats — воронка за 7 дней", "/whoami — id/роль"]
    await update.message.reply_text("\n".join(lines))


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    role = "админ" if db.is_admin(u.id) else "клиент"
    await update.message.reply_text(f"id: {u.id}\nроль: {role}\nчат: {update.effective_chat.id}")


async def cmd_setleadchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        return
    db.set_meta("lead_chat", str(update.effective_chat.id))
    await update.message.reply_text(f"Готово. Заявки буду слать сюда (id {update.effective_chat.id}).")


async def cmd_setdiscount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        return
    text = " ".join(context.args).strip() if getattr(context, "args", None) else ""
    db.set_meta("discount_text", text)
    if text:
        await update.message.reply_text(f"Акция показывается после примерки:\n\n{text}")
    else:
        await update.message.reply_text("Акция убрана.")


async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        return
    rows = db.recent_leads(20)
    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return
    out = ["Последние заявки:"]
    for r in rows:
        p = catalog.get(r["product_id"] or "")
        pt = p["title"] if p else (r["product_id"] or "—")
        out.append(f"#{r['id']} {r['name']} · {r['phone']} · {pt} · {(r['created_at'] or '')[:16]}")
    await update.message.reply_text("\n".join(out))


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        return
    e = db.event_counts(7)
    order = [("start", "Запусков"), ("catalog", "Открыли каталог"), ("open_product", "Смотрели карту"),
             ("fit_start", "Начали примерку"), ("photo", "Прислали фото"),
             ("render", "Фотореалистичных примерок"), ("order_start", "Начали заявку"), ("lead", "Оставили заявку")]
    lines = ["Воронка за 7 дней (всего / уникальных):"]
    for key, label in order:
        d = e.get(key, {"n": 0, "u": 0})
        lines.append(f"• {label}: {d['n']} / {d['u']}")
    await update.message.reply_text("\n".join(lines))


# ── показ карточки товара ─────────────────────────────────────────────────────
def product_caption(p: dict) -> str:
    cap = f"<b>{p['title']}</b>\n{p['desc']}"
    mp = catalog.min_price(p)
    if mp:
        cap += f"\n\nЦена: от {catalog.fmt_price(mp)}"
    return cap


async def show_product(context, chat_id, pid):
    p = catalog.get(pid)
    if not p:
        return
    db.log_event(chat_id, "open_product", pid)
    with open(catalog.image_path(p), "rb") as f:
        await context.bot.send_photo(chat_id, InputFile(f), caption=product_caption(p),
                                     parse_mode="HTML", reply_markup=product_kb(pid))


async def send_demo(context, message):
    cap_b = "Было: обычная стена."
    cap_a = "Стало: карта с подсветкой — так бот покажет её на твоём фото."
    with open(config.DEMO_BEFORE, "rb") as fb, open(config.DEMO_AFTER, "rb") as fa:
        media = [InputMediaPhoto(fb, caption=cap_b), InputMediaPhoto(fa, caption=cap_a)]
        await context.bot.send_media_group(message.chat_id, media)
    await message.reply_text("Хочешь так же? Выбери карту и пришли фото своей стены 👇",
                             reply_markup=catalog_kb())


async def ask_wall_width(message, context, pid: str, map_cm: int | None):
    context.user_data["fit_product"] = pid
    context.user_data["fit_map_cm"] = map_cm
    context.user_data["wall_width_cm"] = None
    context.user_data["awaiting"] = "wall_width"
    p = catalog.get(pid)
    size = f" ({map_cm}×{round(map_cm * 0.6)} см)" if map_cm else ""
    await message.reply_text(
        f"{p['title']}{size}.\n\n"
        "Чтобы подобрать <b>правильный масштаб</b>, напиши примерную <b>ширину стены в метрах</b> "
        "(например, 3 или 2.5).",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Пропустить", callback_data="fitskip")]]))


PHOTO_TIP = (
    "Теперь пришли <b>одно фото</b> стены 📷\n\n"
    "Чтобы примерка вышла точной и наглядной:\n"
    "• снимай стену <b>прямо, фронтально</b> (встань напротив), а не сбоку;\n"
    "• держи телефон ровно, без наклона — стена должна быть прямой в кадре;\n"
    "• отойди на 1.5–2 м, чтобы в кадр попала вся стена целиком."
)


async def ask_photo(message):
    await message.reply_text(PHOTO_TIP, parse_mode="HTML")


# ── колбэки ───────────────────────────────────────────────────────────────────
async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    chat_id = update.effective_chat.id
    await q.answer()

    if data == "menu":
        await q.message.reply_text(WELCOME.format(brand=config.BRAND), reply_markup=main_menu_kb())
    elif data == "demo":
        db.log_event(chat_id, "demo")
        await send_demo(context, q.message)
    elif data == "myfits":
        await show_myfits(context, q.message, update.effective_user.id)
    elif data == "catalog":
        db.log_event(chat_id, "catalog")
        await q.message.reply_text("Выбери раздел:", reply_markup=catalog_kb())
    elif data.startswith("cat:"):
        idx = int(data.split(":")[1])
        cats = catalog.categories()
        await q.message.reply_text(f"{cats[idx]} — выбери карту:", reply_markup=category_kb(idx))
    elif data.startswith("prod:"):
        await show_product(context, chat_id, data.split(":", 1)[1])
    elif data.startswith("fit:"):
        pid = data.split(":", 1)[1]
        db.log_event(chat_id, "fit_start", pid)
        p = catalog.get(pid)
        widths = p.get("widths_cm") or []
        if len(widths) > 1:
            rows = []
            for w in widths:
                price = catalog.price_for(p, w)
                label = f"{w}×{round(w * 0.6)} см"
                if price:
                    label += f" — {catalog.fmt_price(price)}"
                rows.append([InlineKeyboardButton(label, callback_data=f"fitsize:{pid}:{w}")])
            await q.message.reply_text(f"{p['title']} — выбери размер карты:",
                                       reply_markup=InlineKeyboardMarkup(rows))
        else:
            await ask_wall_width(q.message, context, pid, widths[0] if widths else None)
    elif data.startswith("fitsize:"):
        _, pid, cm = data.split(":")
        await ask_wall_width(q.message, context, pid, int(cm))
    elif data == "fitskip":
        context.user_data["wall_width_cm"] = None
        await ask_photo(q.message)
    elif data == "refit":
        if context.user_data.get("fit_product"):
            await q.message.reply_text(PHOTO_TIP, parse_mode="HTML")
        else:
            await q.message.reply_text("Выбери карту в каталоге:", reply_markup=catalog_kb())
    elif data.startswith("adj:"):
        d = data.split(":")[1]
        adj = context.user_data.setdefault("adj", default_adj(context))
        if d == "left":
            adj["cx"] = max(0.12, adj["cx"] - 0.05)
        elif d == "right":
            adj["cx"] = min(0.88, adj["cx"] + 0.05)
        elif d == "up":
            adj["cy"] = max(0.12, adj["cy"] - 0.05)
        elif d == "down":
            adj["cy"] = min(0.88, adj["cy"] + 0.05)
        elif d == "smaller":
            adj["sz"] = max(0.15, adj["sz"] - 0.05)
        elif d == "bigger":
            adj["sz"] = min(0.95, adj["sz"] + 0.05)
        await send_preview(context, q.message, edit=True)
    elif data == "render":
        await do_render(context, q.message, update.effective_user.id)
    elif data.startswith("order:"):
        pid = data.split(":", 1)[1]
        db.log_event(update.effective_user.id, "order_start", pid)
        context.user_data["order_product"] = pid
        context.user_data["awaiting"] = "name"
        await q.message.reply_text("Как тебя зовут?")


# ── предпросмотр (бесплатно) + доводка ИИ ─────────────────────────────────────
def default_adj(context) -> dict:
    sz = aimockup.default_size_fraction(context.user_data.get("fit_map_cm"),
                                        context.user_data.get("wall_width_cm"))
    return {"cx": 0.5, "cy": 0.5, "sz": sz}


def preview_kb(pid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️", callback_data="adj:left"),
         InlineKeyboardButton("⬆️", callback_data="adj:up"),
         InlineKeyboardButton("⬇️", callback_data="adj:down"),
         InlineKeyboardButton("➡️", callback_data="adj:right")],
        [InlineKeyboardButton("➖ мельче", callback_data="adj:smaller"),
         InlineKeyboardButton("➕ крупнее", callback_data="adj:bigger")],
        [InlineKeyboardButton("✨ Сделать фотореалистичной", callback_data="render")],
        [InlineKeyboardButton("🪄 Другое фото", callback_data="refit"),
         InlineKeyboardButton("📐 Размер", callback_data=f"fit:{pid}")],
    ])


def final_kb(pid: str, share_url: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Заказать", callback_data=f"order:{pid}")],
        [InlineKeyboardButton("📤 Поделиться", url=share_url)],
        [InlineKeyboardButton("🪄 Другое фото", callback_data="refit"),
         InlineKeyboardButton("📐 Размер", callback_data=f"fit:{pid}")],
        [InlineKeyboardButton("« В каталог", callback_data="catalog")],
    ])


async def _wall_bytes(context):
    tgfile = await context.bot.get_file(context.user_data["last_wall_file_id"])
    return bytes(await tgfile.download_as_bytearray())


async def send_preview(context, message, edit: bool = False):
    """Бесплатный предпросмотр: кладём карту на стену программно, со стрелками."""
    pid = context.user_data.get("fit_product")
    p = catalog.get(pid or "")
    if not p or not context.user_data.get("last_wall_file_id"):
        await message.reply_text("Пришли фото стены 📷")
        return
    adj = context.user_data.setdefault("adj", default_adj(context))
    comp = aimockup.compose_preview(await _wall_bytes(context), catalog.image_path(p),
                                    adj["cx"], adj["cy"], adj["sz"])
    cap = ("Черновой предпросмотр (бесплатно). Двигай стрелками, размер — ±.\n"
           "Как встанет ровно — жми «✨ Сделать фотореалистичной».")
    if edit:
        with contextlib.suppress(Exception):
            await message.edit_media(InputMediaPhoto(io.BytesIO(comp), caption=cap),
                                     reply_markup=preview_kb(pid))
            return
    await message.reply_photo(io.BytesIO(comp), caption=cap, reply_markup=preview_kb(pid))


async def do_render(context, message, uid):
    """Одна генерация ИИ доводит текущую вклейку до фотореализма."""
    pid = context.user_data.get("fit_product")
    p = catalog.get(pid or "")
    if not p or not context.user_data.get("last_wall_file_id"):
        await message.reply_text("Пришли фото стены 📷")
        return
    if config.MOCKUP_DAILY_LIMIT and db.mockups_today(uid) >= config.MOCKUP_DAILY_LIMIT:
        await message.reply_text(
            "На сегодня лимит фотореалистичных примерок исчерпан. Оставь контакт — менеджер поможет.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Оставить заявку", callback_data=f"order:{pid}")]]))
        return
    adj = context.user_data.setdefault("adj", default_adj(context))
    await context.bot.send_chat_action(message.chat_id, ChatAction.UPLOAD_PHOTO)
    msg = await message.reply_text("Довожу до фотореализма… 10–40 сек ⏳")
    try:
        comp = aimockup.compose_preview(await _wall_bytes(context), catalog.image_path(p),
                                        adj["cx"], adj["cy"], adj["sz"])
        result = await asyncio.to_thread(aimockup.enhance, comp)
    except Exception as e:  # noqa: BLE001
        log.exception("ошибка доводки")
        await msg.edit_text(f"Не получилось 😔 Попробуй ещё раз.\n({str(e)[:120]})")
        return
    db.log_mockup(uid, pid)
    db.log_event(uid, "render", pid)
    with contextlib.suppress(Exception):
        await msg.delete()

    link = await bot_link(context)
    share_text = f"Смотри, как карта «{p['title']}» будет смотреться на стене — примерил в боте {config.BRAND}"
    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(share_text)}"

    caption = f"«{p['title']}» у тебя на стене ✨"
    disc = discount_text()
    if disc:
        caption += f"\n\n🎁 {disc}"
    sent = await message.reply_photo(
        InputFile(io.BytesIO(result), filename="mockup.png"),
        caption=caption, reply_markup=final_kb(pid, share_url))
    # сохраняем результат в «Мои примерки»
    with contextlib.suppress(Exception):
        if sent.photo:
            db.log_render(uid, pid, sent.photo[-1].file_id)


async def show_myfits(context, message, uid):
    rows = db.recent_renders(uid, 5)
    if not rows:
        await message.reply_text("Пока нет сохранённых примерок. Сделай первую — это бесплатно 👇",
                                 reply_markup=catalog_kb())
        return
    await message.reply_text("Твои последние примерки:")
    for r in rows:
        p = catalog.get(r["product_id"] or "")
        pt = p["title"] if p else "Карта"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Заказать эту", callback_data=f"order:{r['product_id']}")]])
        with contextlib.suppress(Exception):
            await context.bot.send_photo(message.chat_id, r["file_id"], caption=pt, reply_markup=kb)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("fit_product"):
        await update.message.reply_text(
            "Чтобы сделать примерку — выбери карту в каталоге и нажми «Примерить на свою стену».",
            reply_markup=main_menu_kb())
        return
    context.user_data["last_wall_file_id"] = (
        update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id)
    context.user_data["adj"] = default_adj(context)
    db.log_event(update.effective_user.id, "photo", context.user_data.get("fit_product"))
    await send_preview(context, update.message, edit=False)


# ── сбор заявки (имя → телефон) ───────────────────────────────────────────────
def phone_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting = context.user_data.get("awaiting")
    if awaiting == "wall_width":
        txt = (update.message.text or "").replace(",", ".").strip()
        try:
            cm = int(round(float(txt) * 100))
            if not (50 <= cm <= 2000):
                raise ValueError
        except ValueError:
            await update.message.reply_text("Напиши ширину стены в метрах числом — например 3 или 2.5. Или нажми «Пропустить».")
            return
        context.user_data["wall_width_cm"] = cm
        context.user_data.pop("awaiting", None)
        await ask_photo(update.message)
        return
    if awaiting == "name":
        context.user_data["lead_name"] = (update.message.text or "").strip()[:100]
        context.user_data["awaiting"] = "phone"
        await update.message.reply_text(
            "Оставь номер телефона — менеджер свяжется и поможет с подбором/заказом.\n"
            "Можно нажать кнопку ниже или написать номер вручную.",
            reply_markup=phone_kb())
        return
    if awaiting == "phone":
        await submit_lead(update, context, (update.message.text or "").strip()[:40])
        return
    # вне сценария — подсказка
    await update.message.reply_text("Открой каталог, чтобы выбрать карту 👇", reply_markup=main_menu_kb())


async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting") == "phone" and update.message.contact:
        await submit_lead(update, context, update.message.contact.phone_number[:40])


async def submit_lead(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    name = context.user_data.get("lead_name", "")
    pid = context.user_data.get("order_product", "")
    lead_id = db.add_lead(update.effective_user.id, name, phone, pid)
    db.log_event(update.effective_user.id, "lead", pid)
    context.user_data.pop("awaiting", None)
    await update.message.reply_text(
        "Спасибо! Заявка принята ✅ Менеджер скоро свяжется.", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text("Что дальше?", reply_markup=main_menu_kb())
    await forward_lead(context, lead_id, name, phone, pid, update.effective_user)


async def forward_lead(context, lead_id, name, phone, pid, user):
    chat = db.get_meta("lead_chat") or config.LEAD_CHAT_ID
    if not chat:
        log.warning("lead_chat не задан — заявка #%s не переслана", lead_id)
        return
    p = catalog.get(pid or "")
    pt = p["title"] if p else "—"
    uname = f"@{user.username}" if user.username else f"id {user.id}"
    text = (f"🛒 <b>Заявка #{lead_id}</b>\n"
            f"Имя: {name}\nТелефон: {phone}\nКарта: {pt}\nКлиент: {uname}")
    with contextlib.suppress(Exception):
        await context.bot.send_message(int(chat), text, parse_mode="HTML")


# ── запуск ────────────────────────────────────────────────────────────────────
def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN")
    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("setleadchat", cmd_setleadchat))
    app.add_handler(CommandHandler("setdiscount", cmd_setdiscount))
    app.add_handler(CommandHandler("leads", cmd_leads))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.CONTACT & filters.ChatType.PRIVATE, on_contact))
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & filters.ChatType.PRIVATE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, on_text))
    log.info("бот запущен, товаров: %s", len(catalog.PRODUCTS))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
