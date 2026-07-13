"""
Единое место для путей проекта.

Корень проекта — папка, где лежат run_bot.py, PBN.py и каталог pbn_app/.
Базы по возможности в data/; старые файлы в корне подхватываются автоматически.
"""

from __future__ import annotations

from pathlib import Path

# Корень: .../PBN
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = PROJECT_ROOT / "exports"


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def analyzer_db_path() -> Path:
    """База анализатора ChatExport (тяжёлая)."""
    ensure_data_dir()
    preferred = DATA_DIR / "analyzer_state.db"
    legacy = PROJECT_ROOT / "analyzer_state.db"
    if preferred.exists():
        return preferred
    if legacy.exists():
        return legacy
    return preferred


def settings_db_path() -> Path:
    """База токена, админов, whitelist, журнала бота."""
    ensure_data_dir()
    preferred = DATA_DIR / "settings.db"
    legacy = PROJECT_ROOT / "pbn_settings.db"
    if preferred.exists():
        return preferred
    if legacy.exists():
        return legacy
    return preferred


def default_exports_scan_dir() -> Path:
    """
    Папка по умолчанию для поиска ChatExport_*.
    Если exports/ не пустая — она; иначе весь корень проекта (как раньше).
    """
    if EXPORTS_DIR.is_dir():
        try:
            if any(EXPORTS_DIR.iterdir()):
                return EXPORTS_DIR
        except OSError:
            pass
    return PROJECT_ROOT
