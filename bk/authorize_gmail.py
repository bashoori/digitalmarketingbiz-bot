from __future__ import print_function
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# اسکوپ دسترسی فقط برای ارسال ایمیل
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    creds = None
    # اگر قبلاً مجوز داده شده، همون رو استفاده کن
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # در غیر این صورت، درخواست جدید بساز
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # توکن را ذخیره کن
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    print("✅ Authorization successful. Token saved to token.json")

if __name__ == '__main__':
    main()
