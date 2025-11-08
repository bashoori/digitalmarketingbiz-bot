from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
import base64

def send_welcome_email(name, to_email):
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.send"])
    service = build("gmail", "v1", credentials=creds)

    subject = "Welcome to Digital Marketing Business 🎉"
    body = (
        f"Hello {name},\n\n"
        "Welcome aboard! 🌟\n"
        "We’re excited to have you here.\n\n"
        "If this email landed in Spam, please mark it as 'Not Spam' to receive future updates.\n\n"
        "– Digital Marketing Business Team"
    )

    message = MIMEText(body)
    message["to"] = to_email
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"✅ Sent welcome email to {to_email}")
