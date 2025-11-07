import os
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder
from bot_logic import setup_bot

TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = os.getenv("RENDER_EXTERNAL_URL")

app = Flask(__name__)
application = ApplicationBuilder().token(TOKEN).build()
setup_bot(application)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "🤖 Digital Marketing Bot is alive!", 200

if __name__ == "__main__":
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    webhook_url = f"{URL}/{TOKEN}"
    requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}")
    print("🌐 Webhook set to:", webhook_url)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
