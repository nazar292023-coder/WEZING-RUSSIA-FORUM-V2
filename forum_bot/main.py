import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from flask import Flask
from threading import Thread

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

logging.basicConfig(level=logging.INFO)

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "WEZING RUSSIA FORUM BOT: OK"

def db():
    return sqlite3.connect("forum_bot.sqlite3")

def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            section TEXT,
            message TEXT,
            status TEXT DEFAULT 'new'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS recruitment (
            section TEXT PRIMARY KEY,
            opened INTEGER DEFAULT 1
        )
    """)
    con.commit()
    con.close()

ORGS = [
    "ЦБ", "ВЧ", "ОПГ ARZ", "ОПГ BAT",
    "ОПГ LYT", "Правительство", "СМИ",
    "ГИБДД", "УМВД"
]

RULES = [
    "Запрещено оскорблять игроков.",
    "Запрещён спам.",
    "Запрещена реклама без разрешения.",
    "Запрещено использование читов.",
    "Запрещено злоупотреблять багами.",
    "Уважайте администрацию и игроков."
]

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Подать заявку", callback_data="apply")],
        [InlineKeyboardButton("🏢 Организации", callback_data="orgs")],
        [InlineKeyboardButton("🎬 Медиа", callback_data="media")],
        [InlineKeyboardButton("💎 Донат-услуги", callback_data="donate")],
        [InlineKeyboardButton("🎁 Ежедневный подарок", callback_data="gift")],
        [InlineKeyboardButton("📜 Правила", callback_data="rules")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать на форум WEZING RUSSIA!\n\n"
        "Выберите нужный раздел:",
        reply_markup=main_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back":
        await query.edit_message_text(
            "Главное меню:", reply_markup=main_menu()
        )

    elif data == "orgs":
        keyboard = [
            [InlineKeyboardButton(x, callback_data="org_" + x)]
            for x in ORGS
        ]
        keyboard.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="back")
        ])
        await query.edit_message_text(
            "🏢 Организации WEZING RUSSIA:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("org_"):
        name = data[4:]
        await query.edit_message_text(
            f"🏢 Раздел организации: {name}\n\n"
            "Информация и набор будут добавлены.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="orgs")]
            ])
        )

    elif data in ("apply", "media"):
        section = "Медиа" if data == "media" else "Администрация / лидерство"
        context.user_data["application"] = section
        await query.edit_message_text(
            f"📝 Заявка: {section}\n\n"
            "Напиши одним сообщением свой игровой ник и причину подачи заявки."
        )

    elif data == "rules":
        await query.edit_message_text(
            "📜 Правила сервера:\n\n" +
            "\n".join(f"{i+1}. {r}" for i, r in enumerate(RULES)),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
            ])
        )

    elif data == "donate":
        await query.edit_message_text(
            "💎 Донат-услуги:\n"
            "• Игровая валюта\n• Транспорт\n• Скины\n• VIP\n\n"
            "Для заказа обратись к администрации.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
            ])
        )

    elif data == "gift":
        await query.edit_message_text(
            "🎁 Ежедневный подарок\n\n"
            "Система подарков будет подключена следующим этапом.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
            ])
        )

    elif data == "support":
        context.user_data["support"] = True
        await query.edit_message_text(
            "🆘 Напиши сообщение для поддержки."
        )

    elif data == "profile":
        user = query.from_user
        await query.edit_message_text(
            f"👤 Твой профиль\n\n"
            f"ID: {user.id}\n"
            f"Имя: {user.full_name}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
            ])
        )

    elif data.startswith("approve_") or data.startswith("reject_"):
        if query.from_user.id not in ADMIN_IDS:
            return

        app_id = int(data.split("_")[1])
        status = "approved" if data.startswith("approve_") else "rejected"

        con = db()
        con.execute(
            "UPDATE applications SET status=? WHERE id=?",
            (status, app_id)
        )
        con.commit()
        con.close()

        await query.edit_message_text(
            f"Заявка №{app_id}: {status}"
        )

async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if context.user_data.get("application"):
        section = context.user_data.pop("application")

        con = db()
        cur = con.execute(
            "INSERT INTO applications (user_id, username, section, message) "
            "VALUES (?, ?, ?, ?)",
            (user.id, user.username or "", section, text)
        )
        app_id = cur.lastrowid
        con.commit()
        con.close()

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app_id}")
            ]
        ])

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"📝 Новая заявка №{app_id}\n"
                    f"Раздел: {section}\n"
                    f"Пользователь: {user.full_name}\n"
                    f"ID: {user.id}\n\n{text}",
                    reply_markup=keyboard
                )
            except Exception:
                logging.exception("Не удалось отправить заявку админу")

        await update.message.reply_text(
            "✅ Заявка отправлена администрации!",
            reply_markup=main_menu()
        )
        return

    if context.user_data.get("support"):
        context.user_data.pop("support")
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                admin_id,
                f"🆘 Обращение от {user.full_name} (ID {user.id}):\n{text}"
            )
        await update.message.reply_text(
            "✅ Сообщение отправлено поддержке.",
            reply_markup=main_menu()
        )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Нет доступа.")
        return

    con = db()
    count = con.execute(
        "SELECT COUNT(*) FROM applications"
    ).fetchone()[0]
    con.close()

    await update.message.reply_text(
        f"⚙️ Панель администратора\nЗаявок всего: {count}\n\n"
        "Управление наборами и тестами добавим следующим этапом."
    )

def run_web():
    app_web.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

def main():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN")

    init_db()
    Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(buttons))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, messages)
    )
    application.run_polling()

if __name__ == "__main__":
    main()
