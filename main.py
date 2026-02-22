import asyncio
import argparse
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

_log_format = '[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s'
_formatter = logging.Formatter(_log_format)

# 콘솔 핸들러
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

# 파일 핸들러 (자정마다 새 파일로 교체, 최대 30일치 보관)
_file_handler = TimedRotatingFileHandler(
    filename=os.path.join(LOG_DIR, 'telebot.log'),
    when='midnight',
    interval=1,
    backupCount=30,
    encoding='utf-8',
)
_file_handler.setFormatter(_formatter)
_file_handler.suffix = '%Y-%m-%d'  # 예: telebot.log.2026-02-22

logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])

# --- .env 파일에서 설정값 불러오기 ---
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
SOURCE_CHANNEL_ID = int(os.getenv('SOURCE_CHANNEL_ID', '0'))
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID', '0'))
KEYWORDS = [kw.strip() for kw in os.getenv('KEYWORDS', '').split(',')]
# ------------------------------------

# 사용자 계정 클라이언트 (감시용)
user_client = TelegramClient('user_session', API_ID, API_HASH)
# 봇 클라이언트 (알림용)
bot_client = TelegramClient('bot_session', API_ID, API_HASH)


async def send_notification(message_text: str, message_date: datetime, chat_id: int, message_id: int, mode: str) -> None:
    """키워드가 포함된 메시지를 봇을 통해 알림 채널로 전송합니다."""
    link_chat_id = chat_id
    if str(link_chat_id).startswith('-100'):
        link_chat_id = int(str(link_chat_id)[4:])

    mode_label = "📅 과거 검색" if mode == "scan" else "🔴 실시간 감지"
    found_keywords = [kw for kw in KEYWORDS if kw.lower() in message_text.lower()]

    notification = (
        f"🔔 키워드 알림 ({mode_label}) 🔔\n\n"
        f"찾은 키워드: {', '.join(found_keywords)}\n"
        f"메시지 작성 시간: {message_date.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"--- 원본 메시지 ---\n"
        f"{message_text}\n"
        f"------------------\n\n"
        f"🔗 원본 메시지 링크:\n"
        f"https://t.me/c/{link_chat_id}/{message_id}"
    )

    await bot_client.send_message(TARGET_CHANNEL_ID, notification, link_preview=False)


async def scan_mode() -> None:
    """지난 7일간의 메시지를 검색하여 키워드가 포함된 메시지를 알림 채널로 전송합니다."""
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    found_count = 0

    logging.info(f"과거 7일 메시지 검색을 시작합니다... (키워드: {', '.join(KEYWORDS)})")
    print(KEYWORDS)
    async for message in user_client.iter_messages(  # type: ignore
        SOURCE_CHANNEL_ID, offset_date=seven_days_ago, reverse=True
    ):
        if not message.text:
            continue

        found_keywords = [kw for kw in KEYWORDS if kw.lower() in message.text.lower()]
        if found_keywords:
            found_count += 1
            logging.info(f"키워드 '{', '.join(found_keywords)}' 발견! 봇이 알림을 보냅니다.")
            await send_notification(message.text, message.date, message.chat_id, message.id, "scan")
            await asyncio.sleep(1)  # API 속도 제한 방지

    logging.info(f"검색 완료. 총 {found_count}개의 메시지에서 키워드를 발견했습니다.")


async def monitor_mode() -> None:
    """새로운 메시지를 실시간으로 감시하여 키워드가 포함된 경우 알림을 전송합니다."""

    @user_client.on(events.NewMessage(chats=SOURCE_CHANNEL_ID))
    async def handler(event) -> None:  # type: ignore
        if not event.message or not event.message.text:
            return

        found_keywords = [kw for kw in KEYWORDS if kw.lower() in event.message.text.lower()]
        if found_keywords:
            logging.info(f"키워드 '{', '.join(found_keywords)}' 발견! 봇이 알림을 보냅니다.")
            await send_notification(
                event.message.text,
                event.message.date,
                event.chat_id,
                event.message.id,
                "monitor"
            )

    logging.info(f"실시간 감시 중... (채널: {SOURCE_CHANNEL_ID}, 키워드: {', '.join(KEYWORDS)})")
    logging.info("종료하려면 Ctrl+C를 누르세요.")
    await user_client.run_until_disconnected()  # type: ignore


async def main(mode: str) -> None:
    """두 클라이언트를 시작하고 지정된 모드를 실행합니다."""
    await bot_client.start(bot_token=BOT_TOKEN)  # type: ignore
    logging.info("봇 클라이언트 시작됨.")

    await user_client.start()  # type: ignore
    logging.info("사용자 클라이언트 시작됨.")

    if mode == 'scan':
        await scan_mode()
    elif mode == 'monitor':
        await monitor_mode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='텔레그램 키워드 알림 봇')
    parser.add_argument(
        'mode',
        choices=['scan', 'monitor'],
        help="scan: 지난 7일간 키워드 검색 후 종료 | monitor: 실시간 감시 (무한 실행)"
    )
    args = parser.parse_args()

    # with 블록: 스크립트 종료 시 클라이언트 연결 자동 해제
    with user_client, bot_client:
        user_client.loop.run_until_complete(main(args.mode))
