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
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from dotenv import load_dotenv

# ========== Load environment variables ==========
load_dotenv()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
TOKEN = os.getenv("TELEGRAM_TOKEN")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_WEBAPP_URL")
WELCOME_LINK = os.getenv("WELCOME_LINK")
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render gives you this automatically

DATA_FILE = "leads.json"
PDF_PATH = "docs/franchise_intro.pdf"

# ========== Flask Setup ==========
app = Flask(__name__)

# ========== Telegram Bot Setup ==========
telegram_app = Application.builder().token(TOKEN).build()

ASK_NAME, ASK_EMAIL = range(2)

# ---------- Helper Functions ----------
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

def normalize_email(raw: str) -> str:
    return raw.replace("\u200c", "").replace("\u200f", "").strip().lower()

def is_valid_email(email_str: str) -> bool:
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email_str) is not None

def post_to_sheet(payload: dict, note: str = "") -> None:
    if not GOOGLE_SHEET_URL or not GOOGLE_SHEET_URL.startswith("https://script.google.com/macros/"):
        print("⚠️ Invalid or missing GOOGLE_SHEET_WEBAPP_URL.")
        return
    try:
        print(f"📤 Sending to Google Sheet ({note}): {payload}")
        resp = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=15)
        print(f"📊 Response {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"❌ Failed to send to Google Sheet: {e}")

def send_verification_email(name, recipient_email):
    msg = EmailMessage()
    msg["Subject"] = "Digital Marketing Business — Email Verification"
    msg["From"] = f"Digital Marketing Business <{SMTP_EMAIL}>"
    msg["To"] = recipient_email
    msg.set_content(
        f"Hello {name},\n\n"
        "This is a verification email from Digital Marketing Business.\n"
        "If you received this, your email address is working.\n\n"
        "Thanks,\nDigital Marketing Business Team"
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Sent verification to {recipient_email}")
        return True
    except Exception as e:
        print("❌ Email send error:", e)
        return False

def send_followup_email(name, recipient_email, welcome_link):
    msg = EmailMessage()
    msg["Subject"] = "Welcome to Digital Marketing Business — Start Here!"
    msg["From"] = f"Digital Marketing Business <{SMTP_EMAIL}>"
    msg["To"] = recipient_email
    link = welcome_link or "https://example.com/start"
    msg.set_content(
        f"Hello {name},\n\n"
        "Your email has been verified successfully 🎉\n"
        f"Start your training here: {link}\n\n"
        "• Learn how digital marketing franchises work\n"
        "• Attract your first clients online\n"
        "• Scale with automation\n\n"
        "— Digital Marketing Business Team"
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(msg)
        print(f"📨 Follow-up email sent to {recipient_email}")
        return True
    except Exception as e:
        print("❌ Error sending follow-up:", e)
        return False

def check_bounce_messages(target_email):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SMTP_EMAIL, SMTP_PASSWORD)
        mail.select("inbox")
        result, data = mail.search(None, '(FROM "mailer-daemon@googlemail.com")')
        if result != "OK":
            return False
        for num in data[0].split()[-10:]:
            result, msg_data = mail.fetch(num, "(RFC822)")
            if result != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode(errors="ignore")
            else:
                body += msg.get_payload(decode=True).decode(errors="ignore")

            if target_email.lower() in body.lower() and "550 5.1.1" in body.lower():
                print(f"🚨 Bounce detected for {target_email}")
                return True
        return False
    except Exception as e:
        print("Error checking Gmail:", e)
        return False

# ---------- Telegram Conversation ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Digital Marketing Business Franchise!\n\n"
        "Learn how to build your own digital business.\n"
        "Please enter your full name:"
    )
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Great 🌟 Now enter your email address:")
    return ASK_EMAIL

async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email_input = normalize_email(update.message.text)
    name = context.user_data.get("name")
    if not is_valid_email(email_input):
        await update.message.reply_text("❌ Invalid email. Try again:")
        return ASK_EMAIL

    leads = load_data()
    lead_record = {
        "name": name,
        "email": email_input,
        "user_id": update.effective_user.id,
        "username": update.effective_user.username,
        "status": "Pending",
    }
    leads.append(lead_record)
    save_data(leads)
    post_to_sheet(lead_record, note="create")

    await update.message.reply_text("📧 Checking your email...")
    sent = send_verification_email(name, email_input)
    if not sent:
        await update.message.reply_text("⚠️ Could not send email. Try again later.")
        return ConversationHandler.END

    await asyncio.sleep(20)
    bounced = check_bounce_messages(email_input)
    lead_record["status"] = "Invalid" if bounced else "Verified"
    save_data(leads)
    post_to_sheet(lead_record, note="status_update")

    if bounced:
        await update.message.reply_text("❌ Email invalid. Try again:")
        return ASK_EMAIL

    await update.message.reply_text("✅ Email verified! Sending introduction PDF...")
    if os.path.exists(PDF_PATH):
        try:
            with open(PDF_PATH, "rb") as f:
                await update.message.reply_document(f, filename="Franchise_Intro.pdf")
        except:
            await update.message.reply_text("⚠️ Could not send PDF.")
    send_followup_email(name, email_input, WELCOME_LINK)
    await update.message.reply_text("📬 Training email sent! Check inbox/spam.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Conversation cancelled.")
    return ConversationHandler.END

# ---------- Telegram Handlers ----------
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
telegram_app.add_handler(conv_handler)

# ---------- Flask Routes ----------
@app.route("/healthz", methods=["GET"])
def healthz():
    return "OK", 200

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run(telegram_app.process_update(update))
    return "ok", 200

# ---------- Start Webhook ----------
async def setup_webhook():
    url = f"{WEBHOOK_URL}/{TOKEN}"
    await telegram_app.bot.set_webhook(url)
    print(f"✅ Webhook set to: {url}")

if __name__ == "__main__":
    import threading

    def run_flask():
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

    threading.Thread(target=run_flask).start()
    asyncio.run(setup_webhook())
