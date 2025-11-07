# Digital Marketing Biz Bot 🤖

A Telegram automation bot for collecting business information and sending it directly to Google Sheets.
Perfect for marketing agencies, franchises, and local businesses.

## 🌟 Features
- Collect customer data directly from Telegram
- Auto-store in Google Sheet
- Email and admin notifications
- Easy to deploy (Render, Railway, Heroku)

## 🚀 Deployment
1. Clone the repo
2. Set up `.env` variables
3. Deploy to Render or Heroku
4. Add your bot token and Google Sheet ID

## 💳 Pricing
- Free Plan: Basic bot with Google Sheet
- Pro Plan: Email + weekly reports + admin alerts

## 📄 Privacy
All data is encrypted and only accessible to authorized accounts.


pip install python-telegram-bot==20.7
python3 -m pip install --upgrade pip
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client



git add .
git commit -m "Added dotenv support"
git push



pip install -r requirements.txt
python authorize_gmail.py

python bot.py