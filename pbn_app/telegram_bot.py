"""
Telegram-бот: меню, whitelist, лог в settings.db.

Запуск из корня PBN:  python run_bot.py
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from pbn_app.paths import PROJECT_ROOT
from pbn_app.runtime_config import RuntimeConfigStore

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("pbn_bot")

STORE = RuntimeConfigStore()


def _load_analyzer_class():
    for name in ("PBN.py", "pbn.py", "PBN.py.txt"):
        p = PROJECT_ROOT / name
        if p.is_file() and p.stat().st_size > 0:
            spec = importlib.util.spec_from_file_location("pbn_analyzer_mod", p)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules["pbn_analyzer_mod"] = mod
                spec.loader.exec_module(mod)
                return getattr(mod, "Analyzer", None)
    return None


AnalyzerCls = _load_analyzer_class()
_analyzer_instance = None


def _analyzer_db_file() -> Path:
    from pbn_app.paths import analyzer_db_path

    return analyzer_db_path()


def _get_analyzer():
    global _analyzer_instance
    if AnalyzerCls is None:
        return None
    if _analyzer_instance is None:
        _analyzer_instance = AnalyzerCls(str(_analyzer_db_file()))
    return _analyzer_instance


async def _log_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else None
    un = update.effective_user.username if update.effective_user else None
    cid = update.effective_chat.id if update.effective_chat else None
    et = "update"
    summary = ""
    if update.message:
        et = "message"
        summary = (update.message.text or update.message.caption or "")[:800]
    elif update.callback_query:
        et = "callback"
        summary = (update.callback_query.data or "")[:500]
    elif update.edited_message:
        et = "edit"
        summary = (update.edited_message.text or "")[:500]

    allowed = STORE.is_allowed(uid) if uid is not None else False
    extra = " | ALLOWED" if allowed else " | DENIED(no whitelist/privilege)"
    STORE.log_interaction(
        tg_user_id=uid,
        username=un,
        chat_id=cid,
        event_type=et,
        summary=summary + extra,
        raw={"update_id": update.update_id},
    )


def _main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("👤 Профиль"), KeyboardButton("📋 Досье")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def _gate(update: Update) -> bool:
    u = update.effective_user
    if u is None:
        return False
    return STORE.is_allowed(u.id)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    await update.effective_message.reply_text(
        "MoriTrustNet: вы в белом списке или администратор.\n"
        "Кнопки меню или команды.",
        reply_markup=_main_keyboard(),
    )


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    u = update.effective_user
    un = f"@{u.username}" if u.username else "username не задан"
    await update.effective_message.reply_text(
        f"👤 {u.full_name}\n🪪 User ID: `{u.id}`\n📛 {un}",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    await update.effective_message.reply_text(
        "Команды:\n/start — меню\n/me — ваш id\n"
        "/dossie <ник> — досье из базы анализа\n"
        "/admin — админам (whitelist)\n"
        "Кнопки дублируют действия."
    )


async def _send_dossier_report(message, username: str) -> None:
    an = _get_analyzer()
    if an is None:
        await message.reply_text(
            "Анализатор не найден. Нужен непустой файл PBN.py или PBN.py.txt в папке проекта."
        )
        return
    username = username.strip()
    if not username:
        await message.reply_text("Укажите ник.")
        return
    try:
        text = an.generate_report(username)
        if len(text) > 4000:
            text = text[:3990] + "\n…"
        await message.reply_text(text)
    except Exception as e:
        await message.reply_text(f"Ошибка отчёта: {e}")


async def cmd_dossie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    if not context.args:
        await update.effective_message.reply_text("Укажите ник: /dossie Username")
        return
    username = " ".join(context.args).strip()
    await _send_dossier_report(update.effective_message, username)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    an = _get_analyzer()
    lines = [
        f"В whitelist: {STORE.whitelist_count()}",
        f"Доп. админов: {len(STORE.get_extra_admin_ids())}",
    ]
    if an:
        try:
            lines.append("")
            lines.append(an.collect_stats())
        except Exception as e:
            lines.append(f"(статистика анализатора: {e})")
    await update.effective_message.reply_text("\n".join(lines)[:4000])


def _is_chief(uid: int) -> bool:
    return STORE.get_chief_admin_id() == uid


def _is_any_admin(uid: int) -> bool:
    return _is_chief(uid) or uid in STORE.get_extra_admin_ids()


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    uid = update.effective_user.id
    if not _is_any_admin(uid):
        await update.effective_message.reply_text("Недостаточно прав.")
        return
    extra = ""
    if _is_chief(uid):
        extra = "/appoint <user_id>\n/revoke <user_id>\n"
    await update.effective_message.reply_text(
        "Админ:\n/whitelist_add <user_id> [заметка]\n"
        "/whitelist_remove <user_id>\n/whitelist_list\n" + extra
    )


async def cmd_whitelist_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    actor = update.effective_user.id
    if not _is_any_admin(actor):
        return
    if len(context.args) < 1:
        await update.effective_message.reply_text("/whitelist_add <id> [заметка]")
        return
    tid = int(context.args[0])
    note = " ".join(context.args[1:]) if len(context.args) > 1 else None
    STORE.whitelist_add(tid, actor, note)
    STORE.log_interaction(
        tg_user_id=actor,
        username=update.effective_user.username,
        chat_id=update.effective_chat.id,
        event_type="admin_whitelist_add",
        summary=f"target={tid} note={note}",
        raw=None,
    )
    await update.effective_message.reply_text(f"В whitelist добавлен id {tid}")


async def cmd_whitelist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    actor = update.effective_user.id
    if not _is_any_admin(actor):
        return
    if len(context.args) < 1:
        await update.effective_message.reply_text("/whitelist_remove <id>")
        return
    tid = int(context.args[0])
    ok = STORE.whitelist_remove(tid)
    STORE.log_interaction(
        tg_user_id=actor,
        username=update.effective_user.username,
        chat_id=update.effective_chat.id,
        event_type="admin_whitelist_remove",
        summary=f"target={tid} ok={ok}",
        raw=None,
    )
    await update.effective_message.reply_text("Удалено." if ok else "Такого id не было.")


async def cmd_whitelist_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    if not _is_any_admin(update.effective_user.id):
        return
    wl = STORE.whitelist_list(100)
    if not wl:
        await update.effective_message.reply_text("Whitelist пуст.")
        return
    lines = [f"{r['tg_user_id']} (от {r['added_by']})" for r in wl]
    await update.effective_message.reply_text("\n".join(lines)[:4000])


async def cmd_appoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    actor = update.effective_user.id
    if not _is_chief(actor):
        await update.effective_message.reply_text("Только главный администратор.")
        return
    if len(context.args) < 1:
        await update.effective_message.reply_text("/appoint <user_id>")
        return
    tid = int(context.args[0])
    ids = STORE.get_extra_admin_ids()
    ids.add(tid)
    STORE.set_extra_admin_ids(ids)
    STORE.log_interaction(
        tg_user_id=actor,
        username=update.effective_user.username,
        chat_id=update.effective_chat.id,
        event_type="admin_appoint",
        summary=f"target={tid}",
        raw=None,
    )
    await update.effective_message.reply_text(f"Пользователь {tid} — админ.")


async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    actor = update.effective_user.id
    if not _is_chief(actor):
        await update.effective_message.reply_text("Только главный администратор.")
        return
    if len(context.args) < 1:
        await update.effective_message.reply_text("/revoke <user_id>")
        return
    tid = int(context.args[0])
    if tid == STORE.get_chief_admin_id():
        await update.effective_message.reply_text("Нельзя снять главного через бота.")
        return
    ids = STORE.get_extra_admin_ids()
    ids.discard(tid)
    STORE.set_extra_admin_ids(ids)
    STORE.log_interaction(
        tg_user_id=actor,
        username=update.effective_user.username,
        chat_id=update.effective_chat.id,
        event_type="admin_revoke",
        summary=f"target={tid}",
        raw=None,
    )
    await update.effective_message.reply_text("Готово.")


async def on_text_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _gate(update):
        return
    text = (update.message.text or "").strip()
    if text == "👤 Профиль":
        await cmd_me(update, context)
    elif text == "📋 Досье":
        context.user_data["await_dossier"] = True
        await update.effective_message.reply_text(
            "Напишите ник для досье одним следующим сообщением."
        )
    elif text == "📊 Статистика":
        await cmd_stats(update, context)
    elif text == "ℹ️ Помощь":
        await cmd_help(update, context)
    elif context.user_data.get("await_dossier"):
        context.user_data["await_dossier"] = False
        await _send_dossier_report(update.effective_message, text)
    else:
        await update.effective_message.reply_text(
            "Не понял. Кнопки меню или /help."
        )


def main() -> None:
    token = STORE.get_bot_token()
    chief = STORE.get_chief_admin_id()
    if not token:
        log.error(
            "Нет bot_token. Запустите анализатор PBN → пункт 1 → панель → задайте токен. "
            "Файл: %s",
            STORE.db_path,
        )
        sys.exit(1)
    if chief is None:
        log.error(
            "Нет chief_admin_id. Задайте в той же панели. Файл: %s",
            STORE.db_path,
        )
        sys.exit(1)

    app = Application.builder().token(token).build()
    app.add_handler(TypeHandler(Update, _log_update), group=-100)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("me", cmd_me))
    app.add_handler(CommandHandler("я", cmd_me))
    app.add_handler(CommandHandler("dossie", cmd_dossie))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("whitelist_add", cmd_whitelist_add))
    app.add_handler(CommandHandler("whitelist_remove", cmd_whitelist_remove))
    app.add_handler(CommandHandler("whitelist_list", cmd_whitelist_list))
    app.add_handler(CommandHandler("appoint", cmd_appoint))
    app.add_handler(CommandHandler("revoke", cmd_revoke))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_button),
        group=0,
    )

    log.info("Бот запущен. База настроек: %s", STORE.db_path)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
