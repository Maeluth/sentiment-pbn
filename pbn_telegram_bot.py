"""Устарело: запускайте из этой папки:  python run_bot.py"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbn_app.telegram_bot import main

if __name__ == "__main__":
    main()
