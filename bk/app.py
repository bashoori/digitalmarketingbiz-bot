import os
import json
import smtplib
import asyncio
import threading
import requests
from flask import Flask, request
from email.message import EmailMessage
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://digitalmarketingbiz-bot.onrender.com")

ASK_NAME, ASK_EMAIL = range(2)
DATA_FILE = "leads.json"

# === Helper functions ===
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def post_to_sheet(payload: dict):
    if not GOOGLE_SHEET_URL:
        print("⚠️ GOOGLE_SHEET_WEBAPP_URL not set.")
        return
    try:
        print(f"📤 Sending data to Google Sheet: {payload}")
        resp = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=20)
        print(f"📊 Sheet response: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Google Sheet error: {e}")

def send_email(name, recipient_email):
    msg = EmailMessage()
    msg["Subject"] = "Welcome to Digital Marketing Business 🚀"
    msg["From"] = f"Digital Marketing Business <{SMTP_EMAIL}>"
    msg["To"] = recipient_email
    msg.set_content(
        f"Hello {name},\n\n"
        "Welcome to Digital Marketing Business! 🎉\n"
        "Here’s your first step into learning online marketing and building your business.\n\n"
        "Visit our website or check your Telegram messages for more info.\n\n"
        "— The Digital Marketing Team"
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Email error: {e}")

# === Telegram logic ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Please enter your full name:")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Now enter your email address:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_input = update.message.text.strip()
    name = context.user_data.get("name", "User")
    leads = load_data()
    record = {
        "name": name,
        "email": email_input,
        "username": update.effective_user.username,
        "user_id": update.effective_user.id,
        "status": "New"
    }
    leads.append(record)
    save_data(leads)
    post_to_sheet(record)
    send_email(name, email_input)
    await update.message.reply_text(f"✅ Thanks {name}! We'll contact you at {email_input}.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# === Flask + Telegram setup ===
flask_app = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
application.add_handler(conv_handler)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@flask_app.route("/", methods=["GET"])
def home():
    return "🤖 Digital Marketing Bot is live!", 200

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    asyncio.run_coroutine_threadsafe(handle_update(update), loop)
    return "ok", 200

async def handle_update(update: Update):
    if not application.running:
        await application.initialize()
        await application.start()
    await application.process_update(update)

async def set_webhook():
    url = f"{RENDER_URL}/{TOKEN}"
    await application.bot.set_webhook(url)
    print(f"✅ Webhook set to {url}")

def run_bot():
    loop.run_until_complete(set_webhook())
    loop.run_forever()

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    run_flask()
