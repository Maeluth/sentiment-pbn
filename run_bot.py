"""
Запуск Telegram-бота из папки проекта PBN:

  python run_bot.py

Перед первым запуском: токен и id главного админа — в консоли PBN, пункт 1, панель, пункт 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pbn_app.telegram_bot import main

if __name__ == "__main__":
    main()
