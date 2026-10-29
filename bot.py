"""Telegram-бот «примерочная» деревянных карт: каталог → выбор карты →
фото стены → фотореалистичная примерка (Nano Banana) → заявка."""
from __future__ import annotations

import asyncio
import contextlib
import io
import logging

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update,
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


# ── меню / каталог ────────────────────────────────────────────────────────────
def main_menu_kb():
    rows = [[InlineKeyboardButton("🗺 Каталог карт", callback_data="catalog")],
            [InlineKeyboardButton("🌐 Сайт", url=config.SITE_URL)]]
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪄 Примерить на свою стену", callback_data=f"fit:{pid}")],
        [InlineKeyboardButton("🛒 Заказать / задать вопрос", callback_data=f"order:{pid}")],
        [InlineKeyboardButton("« Назад", callback_data="catalog")],
    ])


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
    await update.message.reply_text(WELCOME.format(brand=config.BRAND), reply_markup=main_menu_kb())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["/start — меню и каталог"]
    if db.is_admin(update.effective_user.id):
        lines += ["/setleadchat — слать заявки в текущий чат", "/leads — последние заявки", "/whoami — id/роль"]
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


# ── показ карточки товара ─────────────────────────────────────────────────────
async def show_product(context, chat_id, pid):
    p = catalog.get(pid)
    if not p:
        return
    caption = f"<b>{p['title']}</b>\n{p['desc']}"
    with open(catalog.image_path(p), "rb") as f:
        await context.bot.send_photo(chat_id, InputFile(f), caption=caption,
                                     parse_mode="HTML", reply_markup=product_kb(pid))


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


# ── колбэки ───────────────────────────────────────────────────────────────────
async def on_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    chat_id = update.effective_chat.id
    await q.answer()

    if data == "menu":
        await q.message.reply_text(WELCOME.format(brand=config.BRAND), reply_markup=main_menu_kb())
    elif data == "catalog":
        await q.message.reply_text("Выбери раздел:", reply_markup=catalog_kb())
    elif data.startswith("cat:"):
        idx = int(data.split(":")[1])
        cats = catalog.categories()
        await q.message.reply_text(f"{cats[idx]} — выбери карту:", reply_markup=category_kb(idx))
    elif data.startswith("prod:"):
        await show_product(context, chat_id, data.split(":", 1)[1])
    elif data.startswith("fit:"):
        pid = data.split(":", 1)[1]
        p = catalog.get(pid)
        widths = p.get("widths_cm") or []
        if len(widths) > 1:
            rows = [[InlineKeyboardButton(f"{w}×{round(w * 0.6)} см", callback_data=f"fitsize:{pid}:{w}")]
                    for w in widths]
            await q.message.reply_text(f"{p['title']} — выбери размер карты:",
                                       reply_markup=InlineKeyboardMarkup(rows))
        else:
            await ask_wall_width(q.message, context, pid, widths[0] if widths else None)
    elif data.startswith("fitsize:"):
        _, pid, cm = data.split(":")
        await ask_wall_width(q.message, context, pid, int(cm))
    elif data == "fitskip":
        context.user_data["wall_width_cm"] = None
        context.user_data.pop("awaiting", None)
        await q.message.reply_text("Ок, подберу масштаб на глаз. Пришли <b>одно фото</b> стены 📷", parse_mode="HTML")
    elif data == "refit":
        if context.user_data.get("fit_product"):
            await q.message.reply_text("Пришли новое фото стены 📷")
        else:
            await q.message.reply_text("Выбери карту в каталоге:", reply_markup=catalog_kb())
    elif data.startswith("order:"):
        pid = data.split(":", 1)[1]
        context.user_data["order_product"] = pid
        context.user_data["awaiting"] = "name"
        await q.message.reply_text("Как тебя зовут?")


# ── приём фото стены → примерка ───────────────────────────────────────────────
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = context.user_data.get("fit_product")
    if not pid:
        await update.message.reply_text(
            "Чтобы сделать примерку — выбери карту в каталоге и нажми «Примерить на свою стену».",
            reply_markup=main_menu_kb())
        return
    p = catalog.get(pid)
    if not p:
        return
    uid = update.effective_user.id
    if config.MOCKUP_DAILY_LIMIT and db.mockups_today(uid) >= config.MOCKUP_DAILY_LIMIT:
        await update.message.reply_text(
            "На сегодня лимит бесплатных примерок исчерпан. Оставь контакт — менеджер поможет с подбором.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Оставить заявку", callback_data=f"order:{pid}")]]))
        return

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    msg = await update.message.reply_text("Генерирую примерку… 10–40 сек ⏳")
    try:
        photo = update.message.photo[-1]  # самое большое
        tgfile = await photo.get_file()
        wall_bytes = bytes(await tgfile.download_as_bytearray())
        hint = aimockup.scale_hint(context.user_data.get("fit_map_cm"), context.user_data.get("wall_width_cm"))
        result = await asyncio.to_thread(aimockup.make_mockup, wall_bytes, catalog.image_path(p), hint)
    except Exception as e:  # noqa: BLE001
        log.exception("ошибка примерки")
        await msg.edit_text(f"Не получилось сделать примерку 😔 Попробуй другое фото.\n({str(e)[:120]})")
        return
    db.log_mockup(uid, pid)
    with contextlib.suppress(Exception):
        await msg.delete()
    await update.message.reply_photo(
        InputFile(io.BytesIO(result), filename="mockup.png"),
        caption=f"Вот как «{p['title']}» будет смотреться у тебя ✨\n(примерно — финальный вид зависит от размера и света)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Заказать", callback_data=f"order:{pid}")],
            [InlineKeyboardButton("🪄 Другое фото стены", callback_data="refit")],
            [InlineKeyboardButton("📐 Другой размер", callback_data=f"fit:{pid}")],
            [InlineKeyboardButton("« В каталог", callback_data="catalog")],
        ]))


# ── сбор заявки (имя → телефон) ───────────────────────────────────────────────
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
        await update.message.reply_text("Отлично. Теперь пришли <b>одно фото</b> стены 📷", parse_mode="HTML")
        return
    if awaiting == "name":
        context.user_data["lead_name"] = (update.message.text or "").strip()[:100]
        context.user_data["awaiting"] = "phone"
        await update.message.reply_text("Оставь номер телефона — менеджер свяжется и поможет с подбором/заказом.")
        return
    if awaiting == "phone":
        phone = (update.message.text or "").strip()[:40]
        name = context.user_data.get("lead_name", "")
        pid = context.user_data.get("order_product", "")
        lead_id = db.add_lead(update.effective_user.id, name, phone, pid)
        context.user_data.pop("awaiting", None)
        await update.message.reply_text(
            "Спасибо! Заявка принята ✅ Менеджер скоро свяжется.", reply_markup=main_menu_kb())
        await forward_lead(context, lead_id, name, phone, pid, update.effective_user)
        return
    # вне сценария — подсказка
    await update.message.reply_text("Открой каталог, чтобы выбрать карту 👇", reply_markup=main_menu_kb())


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
    app.add_handler(CommandHandler("leads", cmd_leads))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, on_text))
    log.info("бот запущен, товаров: %s", len(catalog.PRODUCTS))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
