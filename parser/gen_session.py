#!/usr/bin/env python3
"""
Запусти ОДИН РАЗ ЛОКАЛЬНО, чтобы получить StringSession для CI.
В CI логиниться по телефону нельзя — туда кладётся уже готовая строка.

  cd parser
  pip install -r requirements.txt
  TG_API_ID=12345 TG_API_HASH=abc... python gen_session.py

Введёшь номер телефона дедик-аккаунта + код из Telegram.
Скопируй напечатанную строку в GitHub Secret TG_SESSION.
НИКОМУ не показывай: это полный доступ к аккаунту.
"""
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(os.environ["TG_API_ID"])
api_hash = os.environ["TG_API_HASH"]

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\n===== TG_SESSION (скопируй целиком в GitHub Secret) =====\n")
    print(client.session.save())
    print("\n========================================================\n")
