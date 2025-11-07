import os
import json
import re
import smtplib
import imaplib
import email
import asyncio
import requests
from flask import Flask, request
from email.message import EmailMessage
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv

load_dotenv()

# --- ENV ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
WELCOME_LINK = os.getenv("WELCOME_LINK")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://digitalmarketingbiz-bot.onrender.com")

# --- Constants ---
ASK_NAME, ASK_EMAIL = range(2)
DATA_FILE = "leads.json"
PDF_PATH = "docs/franchise_intro.pdf"

# --- Flask app ---
flask_app = Flask(__name__)

# --- Telegram app ---
bot_app = Application.builder().token(TOKEN).build()

# --- Simple helper for saving data ---
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump([], f)
        return []
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

# --- Telegram conversation handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Please enter your full name:")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Now enter your email address:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_addr = update.message.text.strip()
    name = context.user_data.get("name")

    leads = load_data()
    leads.append({"name": name, "email": email_addr})
    save_data(leads)

    await update.message.reply_text(f"✅ Thanks {name}! We'll reach you at {email_addr}.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
bot_app.add_handler(conv)

# --- Flask routes ---
@flask_app.route("/", methods=["GET"])
def home():
    return "🤖 Digital Marketing Bot is running!", 200

@flask_app.route("/healthz", methods=["GET"])
def healthz():
    return "OK", 200

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        asyncio.run(bot_app.process_update(update))
    except Exception as e:
        print(f"❌ Error processing update: {e}")
    return "ok", 200

# --- Setup webhook when app starts ---
async def setup_webhook():
    url = f"{RENDER_URL}/{TOKEN}"
    await bot_app.bot.set_webhook(url)
    print(f"✅ Webhook set to {url}")

if __name__ == "__main__":
    import threading

    def run_flask():
        flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

    threading.Thread(target=run_flask).start()
    asyncio.run(setup_webhook())
