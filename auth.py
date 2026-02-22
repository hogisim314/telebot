"""
최초 1회 또는 세션이 만료되었을 때 실행하는 인증 스크립트입니다.
텔레그램 전화번호 인증을 완료하면 user_session.session 파일이 생성됩니다.

사용법:
    python auth.py
"""
import os
from telethon.sync import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

print("=== 텔레그램 사용자 인증 ===")
print("전화번호와 인증 코드를 입력하여 로그인합니다.")
print("이 과정은 최초 1회 또는 세션 만료 시에만 필요합니다.\n")

with TelegramClient('user_session', API_ID, API_HASH) as client:
    client.start()
    print("\n✅ 인증 완료! user_session.session 파일이 생성되었습니다.")
    print("이제 'python main.py scan' 또는 'python main.py monitor'를 실행할 수 있습니다.")
