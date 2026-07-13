"""
Консольная панель: журнал бота и первичная настройка settings.db.
"""

from __future__ import annotations

import datetime as dt

from pbn_app.paths import PROJECT_ROOT, settings_db_path
from pbn_app.runtime_config import RuntimeConfigStore


def _ts(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def interactive_configure_settings(store: RuntimeConfigStore) -> None:
    print("\n--- Настройка базы бота (settings.db) ---")
    print(f"Файл: {store.db_path}")
    cur_tok = store.get_bot_token()
    print(f"Токен сейчас: {'задан (' + str(len(cur_tok)) + ' симв.)' if cur_tok else 'НЕ ЗАДАН'}")
    t = input("Новый токен бота (Enter — не менять): ").strip()
    if t:
        store.set_bot_token(t)
        print("Токен сохранён.")
    chief = store.get_chief_admin_id()
    print(f"ID главного админа сейчас: {chief if chief is not None else 'НЕ ЗАДАН'}")
    raw = input("Новый числовой Telegram user id главного админа (Enter — не менять): ").strip()
    if raw:
        store.set_chief_admin_id(int(raw))
        print("ID главного админа сохранён.")
    print("Доп. админов можно назначить в Telegram: /appoint <id>")


def show_recent_logs(store: RuntimeConfigStore, n: int = 50) -> None:
    rows = store.recent_logs(n)
    if not rows:
        print("Записей в журнале пока нет.")
        return
    print(f"\n--- Последние {len(rows)} событий ---")
    for r in rows:
        uid = r.get("tg_user_id")
        un = r.get("username") or "—"
        et = r.get("event_type")
        sm = (r.get("summary") or "")[:120]
        print(f"{_ts(int(r['created_at']))} | user={uid} @{un} | {et} | {sm}")


def bot_admin_console_menu() -> None:
    store = RuntimeConfigStore()
    while True:
        print("\n=== Панель: Telegram-бот (журнал и настройки) ===")
        print(f"Корень проекта: {PROJECT_ROOT}")
        print(f"База настроек/логов: {store.db_path}")
        print("1. Показать последние записи журнала")
        print("2. Задать токен бота и ID главного администратора")
        print("3. Показать белый список (id)")
        print("4. Назад")
        c = input("Выбор: ").strip()
        if c == "1":
            try:
                n = int(input("Сколько строк (по умол. 50): ").strip() or "50")
            except ValueError:
                n = 50
            show_recent_logs(store, n)
        elif c == "2":
            interactive_configure_settings(store)
        elif c == "3":
            wl = store.whitelist_list(500)
            if not wl:
                print("Белый список пуст (доступ у главного и доп. админов всегда).")
            else:
                for row in wl:
                    print(
                        f"  id={row['tg_user_id']} добавил={row['added_by']} "
                        f"время={_ts(int(row['added_at']))} {row.get('note') or ''}"
                    )
        elif c == "4":
            break
        else:
            print("Некорректный выбор")
