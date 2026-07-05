#!/usr/bin/env python3
"""
Telegram interface for clims.

All credentials live in .clims/credentials.json — no env vars needed.
First run: a terminal wizard collects everything and saves the file.
After that, manage keys and users via bot chat commands.

Run (after `pip install clims_code[telegram]`):
    clims-bot
    # or
    python -m clims_cli.telegram_bot

Chat commands (admin):
    /adduser <id>            — add an allowed Telegram user
    /removeuser <id>         — remove an allowed user
    /setkey llm <provider> <key>   — change LLM provider + key
    /setkey google <key>     — Google API key (Gemini / image gen)
    /setkey meta <token>     — Meta Ads access token
    /config                  — show current settings (keys masked)

Chat commands (any allowed user):
    /start                   — welcome + help
    /reset                   — clear conversation history
    /cancel                  — interrupt current response
    /skills                  — list loaded skills
    /myid                    — show your Telegram user ID

Not allowed but messaging the bot:
    /myid                    — still works so they can send you their ID
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import asyncio
from pathlib import Path

# ── credentials path ───────────────────────────────────────────────────────────
# Launcher (repl.py) passes the exact creds path via CLIMS_CREDS_FILE env var
# so the bot finds the right file regardless of how it was started.
_creds_env = os.environ.get("CLIMS_CREDS_FILE")
CREDS_FILE = Path(_creds_env) if _creds_env else Path.cwd() / ".clims" / "credentials.json"
SETTINGS_FILE = CREDS_FILE.parent / "settings.json"
_WORK_DIR = CREDS_FILE.parent.parent   # directory that contains .clims/

TELEGRAM_MAX_LEN = 4000
STREAM_EDIT_INTERVAL = 0.8
TYPING_INTERVAL = 4.0

log = logging.getLogger("clims.telegram")

# ── credentials helpers ────────────────────────────────────────────────────────

def _load_creds() -> dict:
    if CREDS_FILE.exists():
        try:
            return json.loads(CREDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_creds(creds: dict) -> None:
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDS_FILE.write_text(json.dumps(creds, indent=2), encoding="utf-8")


def _mask(key: str) -> str:
    if not key:
        return "(not set)"
    return key[:6] + "..." + key[-4:] if len(key) > 12 else "***"


def _inject_env(creds: dict) -> None:
    """Push credentials into os.environ so clims load_config picks them up."""
    if creds.get("llm_api_key"):
        os.environ["CLIMS_API_KEY"] = creds["llm_api_key"]
    if creds.get("google_api_key"):
        os.environ.setdefault("GOOGLE_API_KEY", creds["google_api_key"])
        os.environ.setdefault("GEMINI_API_KEY", creds["google_api_key"])
    if creds.get("meta_ads_token"):
        os.environ.setdefault("META_ADS_TOKEN", creds["meta_ads_token"])
    if creds.get("comfyui_api_url"):
        os.environ.setdefault("COMFYUI_API_URL", creds["comfyui_api_url"])
    if creds.get("comfyui_model"):
        os.environ.setdefault("COMFYUI_MODEL", creds["comfyui_model"])


def _update_settings(provider: str, model: str | None = None) -> None:
    """Write provider (and optionally model) to .clims/settings.json."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
    except Exception:
        settings = {}
    settings["provider"] = provider
    if model:
        settings["model"] = model
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


# ── bootstrap ──────────────────────────────────────────────────────────────────

_PROVIDER_DEFAULTS = {
    "deepseek":  "deepseek-chat",
    "anthropic": "claude-sonnet-4-6",
    "openai":    "gpt-4o",
    "gemini":    "gemini-2.5-flash",
    "ollama":    "llama3.2",
}


def _bootstrap() -> dict:
    """
    Load credentials.json (written by `clims` on first run) and inject into
    os.environ so clims load_config picks up the keys.  No wizard here —
    run `clims` once to set everything up via the chat interface.
    """
    creds = _load_creds()

    if not creds.get("llm_api_key") or not creds.get("telegram_bot_token"):
        print()
        print("  clims Telegram Bot")
        print()
        print("  No credentials found.  Run `clims` first to set everything up")
        print("  through the chat — it will ask for your keys on the first launch.")
        print(f"  (looking for: {CREDS_FILE})")
        print()
        sys.exit(1)

    _inject_env(creds)
    _update_settings(
        creds.get("llm_provider", "deepseek"),
        creds.get("llm_model"),
    )
    return creds


_CREDS: dict = {}   # populated by main() / _bootstrap(); empty when imported as a library

# ── clims imports (after env vars are set) ─────────────────────────────────────
from clims_core.agent.message import Message          # noqa: E402
from clims_core.commands import load_skills           # noqa: E402
from clims_core.config import load_config             # noqa: E402
from clims_core.tools.base import Tool, ToolResult, ToolContext  # noqa: E402
from clims_core.permissions.policy import PermissionClass  # noqa: E402
from clims_cli.repl import build_agent                # noqa: E402

# ── telegram imports ───────────────────────────────────────────────────────────
from telegram import Update                           # noqa: E402
from telegram.constants import ChatAction, ParseMode  # noqa: E402
from telegram.ext import (                            # noqa: E402
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── runtime state ──────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

_cfg    = load_config(_WORK_DIR)
_skills = load_skills(_WORK_DIR)


def _allowed_users() -> list[int]:
    return _CREDS.get("telegram_allowed_users", [])


def _is_allowed(uid: int) -> bool:
    users = _allowed_users()
    return not users or uid in users   # empty list = open to all (dev mode)


def _is_admin(uid: int) -> bool:
    users = _allowed_users()
    return bool(users) and uid == users[0]   # first entry = admin


# ── telegram app reference (set in main, used by SendFileTool) ────────────────
_app = None          # telegram.ext.Application
_event_loop = None   # running asyncio event loop

_VIDEO_EXT  = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
_AUDIO_EXT  = {".mp3", ".ogg", ".m4a", ".wav", ".flac", ".aac"}
_PHOTO_EXT  = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


class SendFileTool(Tool):
    """Lets the clims agent send a local file directly to the Telegram chat."""

    name        = "send_file_to_telegram"
    description = (
        "Send a local file to the user's Telegram chat. "
        "Use this whenever the user asks you to send, share, deliver, or forward a file. "
        "Supports documents, videos, audio, and images. Max 50 MB."
    )
    permission  = PermissionClass.MUTATING
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to send",
            },
            "caption": {
                "type": "string",
                "description": "Optional caption / message to accompany the file",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, chat_id: int) -> None:
        self._chat_id = chat_id

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:  # noqa: A002
        file_path = Path(input["file_path"])
        caption   = input.get("caption", "")

        if not file_path.exists():
            return ToolResult.error(f"File not found: {file_path}")

        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > 50:
            return ToolResult.error(
                f"File is {size_mb:.1f} MB — Telegram's bot API limit is 50 MB. "
                "Consider compressing it first."
            )

        if _app is None or _event_loop is None:
            return ToolResult.error("Telegram bot not initialised yet.")

        ext = file_path.suffix.lower()

        async def _send():
            bot = _app.bot
            with open(file_path, "rb") as fh:
                if ext in _VIDEO_EXT:
                    await bot.send_video(
                        chat_id=self._chat_id, video=fh,
                        filename=file_path.name, caption=caption or None,
                    )
                elif ext in _AUDIO_EXT:
                    await bot.send_audio(
                        chat_id=self._chat_id, audio=fh,
                        filename=file_path.name, caption=caption or None,
                    )
                elif ext in _PHOTO_EXT:
                    await bot.send_photo(
                        chat_id=self._chat_id, photo=fh,
                        caption=caption or None,
                    )
                else:
                    await bot.send_document(
                        chat_id=self._chat_id, document=fh,
                        filename=file_path.name, caption=caption or None,
                    )

        try:
            future = asyncio.run_coroutine_threadsafe(_send(), _event_loop)
            future.result(timeout=120)
            return ToolResult.ok(
                f"Sent {file_path.name} ({size_mb:.1f} MB) to Telegram chat {self._chat_id}."
            )
        except Exception as exc:
            return ToolResult.error(f"Failed to send: {exc}")


# ── per-chat session ───────────────────────────────────────────────────────────

class ChatSession:
    def __init__(self, chat_id: int):
        import dataclasses
        # Telegram sessions are fully autonomous:
        # - bypass mode: no per-tool approval prompts (agent runs unattended)
        # - unrestricted: no workspace boundary (agent can read/write anywhere on the machine)
        tg_cfg = dataclasses.replace(_cfg, permission_mode="bypass")
        self.agent = build_agent(
            tg_cfg, Path.home(),
            extra_tools=[SendFileTool(chat_id)],
            unrestricted=True,
        )
        self.history: list[Message] = []
        self.cancel_event = threading.Event()
        self.lock = asyncio.Lock()
        self.running = False

    def reset(self):
        self.history = []
        self.cancel_event.clear()
        self.running = False


_sessions: dict[int, ChatSession] = {}


def _get_session(chat_id: int) -> ChatSession:
    if chat_id not in _sessions:
        log.info("New session for chat %d", chat_id)
        _sessions[chat_id] = ChatSession(chat_id)
    return _sessions[chat_id]


def _rebuild_all_sessions() -> None:
    """Recreate all agents so they pick up new config / keys."""
    global _cfg, _skills
    _cfg    = load_config(_WORK_DIR)
    _skills = load_skills(_WORK_DIR)
    _sessions.clear()
    log.info("All sessions rebuilt with updated config")


# ── telegram helpers ───────────────────────────────────────────────────────────

def _split(text: str, limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts or [""]


async def _send_or_edit(bot, chat_id: int, msg_id: int, text: str) -> None:
    parts = _split(text)
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=parts[0] or "✓")
    except Exception:
        pass
    for part in parts[1:]:
        await bot.send_message(chat_id=chat_id, text=part)


def _uid(update: Update) -> int:
    return update.effective_user.id if update.effective_user else 0


# ── command handlers ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not _is_allowed(uid):
        await update.message.reply_text(
            f"⛔ You are not authorised.\nSend your ID ({uid}) to the admin to be added."
        )
        return
    await update.message.reply_text(
        "*clims agent connected* — send any message and I'll handle it.\n\n"
        "*Commands:*\n"
        "/skills — list all auto-triggered skills\n"
        "/reset — clear conversation history\n"
        "/cancel — interrupt current response\n"
        "/myid — your Telegram user ID\n"
        + ("\n*Admin:*\n/adduser /removeuser /setkey /config" if _is_admin(uid) else ""),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    await update.message.reply_text(f"Your Telegram user ID: `{uid}`", parse_mode=ParseMode.MARKDOWN)


async def cmd_skills(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(_uid(update)):
        return
    if not _skills:
        await update.message.reply_text("No skills loaded.")
        return
    lines = ["*Loaded skills* (auto-triggered by your messages):\n"]
    for name, skill in sorted(_skills.items()):
        desc = skill.description.split("--")[0].replace("When the user wants to ", "").strip().rstrip(",")
        lines.append(f"• `/{name}` — {desc}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(_uid(update)):
        return
    sess = _get_session(update.effective_chat.id)
    if sess.running:
        await update.message.reply_text("⚠️ Response is running — /cancel it first.")
        return
    sess.reset()
    await update.message.reply_text("🔄 History cleared.")


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(_uid(update)):
        return
    sess = _get_session(update.effective_chat.id)
    if not sess.running:
        await update.message.reply_text("Nothing is running.")
        return
    sess.cancel_event.set()
    await update.message.reply_text("⏹ Cancelling…")


# ── admin commands ─────────────────────────────────────────────────────────────

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not _is_admin(uid):
        await update.message.reply_text("⛔ Admin only.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/adduser <telegram_user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        new_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ User ID must be a number.")
        return
    users = _allowed_users()
    if new_id in users:
        await update.message.reply_text(f"`{new_id}` is already allowed.", parse_mode=ParseMode.MARKDOWN)
        return
    users.append(new_id)
    _CREDS["telegram_allowed_users"] = users
    _save_creds(_CREDS)
    await update.message.reply_text(f"✅ Added `{new_id}`. They can now use the bot.", parse_mode=ParseMode.MARKDOWN)


async def cmd_removeuser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not _is_admin(uid):
        await update.message.reply_text("⛔ Admin only.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/removeuser <telegram_user_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        rem_id = int(args[0])
    except ValueError:
        await update.message.reply_text("⚠️ User ID must be a number.")
        return
    if rem_id == uid:
        await update.message.reply_text("⚠️ You cannot remove yourself (admin).")
        return
    users = _allowed_users()
    if rem_id not in users:
        await update.message.reply_text(f"`{rem_id}` is not in the allowed list.", parse_mode=ParseMode.MARKDOWN)
        return
    users.remove(rem_id)
    _CREDS["telegram_allowed_users"] = users
    _save_creds(_CREDS)
    _sessions.pop(rem_id, None)
    await update.message.reply_text(f"✅ Removed `{rem_id}`.", parse_mode=ParseMode.MARKDOWN)


async def cmd_setkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /setkey llm <provider> <api_key>    — change LLM provider + key
    /setkey llm <api_key>               — change key only (keep provider)
    /setkey google <key>                — Google / Gemini API key
    /setkey meta <token>                — Meta Ads access token
    """
    uid = _uid(update)
    if not _is_admin(uid):
        await update.message.reply_text("⛔ Admin only.")
        return
    args = ctx.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "*Usage:*\n"
            "`/setkey llm <provider> <api_key>` — e.g. deepseek, anthropic, openai, gemini\n"
            "`/setkey llm <api_key>` — keep current provider, update key only\n"
            "`/setkey google <key>`\n"
            "`/setkey meta <token>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    service = args[0].lower()

    if service == "llm":
        providers = set(_PROVIDER_DEFAULTS.keys())
        if len(args) == 3 and args[1].lower() in providers:
            provider, key = args[1].lower(), args[2]
        elif len(args) == 2:
            provider = _CREDS.get("llm_provider", "deepseek")
            key = args[1]
        else:
            await update.message.reply_text("⚠️ Usage: `/setkey llm [provider] <api_key>`", parse_mode=ParseMode.MARKDOWN)
            return
        _CREDS["llm_provider"] = provider
        _CREDS["llm_model"] = _CREDS.get("llm_model") or _PROVIDER_DEFAULTS.get(provider, "")
        _CREDS["llm_api_key"] = key
        _save_creds(_CREDS)
        _inject_env(_CREDS)
        _update_settings(provider, _CREDS.get("llm_model"))
        _rebuild_all_sessions()
        await update.message.reply_text(
            f"✅ LLM set to `{provider}` / `{_CREDS['llm_model']}`. Key updated. Sessions reset.",
            parse_mode=ParseMode.MARKDOWN,
        )

    elif service == "google":
        _CREDS["google_api_key"] = args[1]
        _save_creds(_CREDS)
        _inject_env(_CREDS)
        await update.message.reply_text("✅ Google API key updated.", parse_mode=ParseMode.MARKDOWN)

    elif service == "meta":
        _CREDS["meta_ads_token"] = args[1]
        _save_creds(_CREDS)
        _inject_env(_CREDS)
        await update.message.reply_text("✅ Meta Ads token updated.", parse_mode=ParseMode.MARKDOWN)

    else:
        await update.message.reply_text(f"⚠️ Unknown service `{service}`. Use: llm, google, meta", parse_mode=ParseMode.MARKDOWN)


async def cmd_config(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(_uid(update)):
        await update.message.reply_text("⛔ Admin only.")
        return
    users = _allowed_users()
    lines = [
        "*Current Configuration*\n",
        f"*LLM:* `{_CREDS.get('llm_provider', '?')}` / `{_CREDS.get('llm_model', '?')}`",
        f"*LLM key:* `{_mask(_CREDS.get('llm_api_key', ''))}`",
        f"*Google key:* `{_mask(_CREDS.get('google_api_key', ''))}`",
        f"*Meta token:* `{_mask(_CREDS.get('meta_ads_token', ''))}`",
        f"*Telegram token:* `{_mask(_CREDS.get('telegram_bot_token', ''))}`",
        f"*Allowed users ({len(users)}):* " + (", ".join(f"`{u}`" for u in users) or "none (open)"),
        f"*Workspace:* `{_WORK_DIR}`",
        f"*Skills:* {', '.join(sorted(_skills.keys())) or 'none'}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── /send command ─────────────────────────────────────────────────────────────

async def cmd_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Send a local file to the chat. Usage: /send <absolute_path> [caption]"""
    uid = _uid(update)
    if not _is_allowed(uid):
        await update.message.reply_text(f"⛔ Not authorised. Your ID: `{uid}`", parse_mode=ParseMode.MARKDOWN)
        return

    text = (update.message.text or "").strip()
    parts = text.split(None, 2)          # ["/send", path, optional_caption]
    if len(parts) < 2:
        await update.message.reply_text("Usage: `/send <file_path> [caption]`", parse_mode=ParseMode.MARKDOWN)
        return

    file_path = Path(parts[1])
    caption   = parts[2] if len(parts) > 2 else ""

    if not file_path.exists():
        await update.message.reply_text(f"❌ File not found: `{file_path}`", parse_mode=ParseMode.MARKDOWN)
        return

    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > 50:
        await update.message.reply_text(f"❌ File is {size_mb:.1f} MB — Telegram limit is 50 MB.")
        return

    await update.message.reply_text(f"📤 Sending `{file_path.name}` ({size_mb:.1f} MB)…", parse_mode=ParseMode.MARKDOWN)

    ext = file_path.suffix.lower()
    chat_id = update.effective_chat.id
    try:
        with open(file_path, "rb") as fh:
            if ext in _VIDEO_EXT:
                await ctx.bot.send_video(chat_id=chat_id, video=fh, filename=file_path.name, caption=caption or None)
            elif ext in _AUDIO_EXT:
                await ctx.bot.send_audio(chat_id=chat_id, audio=fh, filename=file_path.name, caption=caption or None)
            elif ext in _PHOTO_EXT:
                await ctx.bot.send_photo(chat_id=chat_id, photo=fh, caption=caption or None)
            else:
                await ctx.bot.send_document(chat_id=chat_id, document=fh, filename=file_path.name, caption=caption or None)
    except Exception as exc:
        await update.message.reply_text(f"❌ Failed: {exc}")


# ── main message handler ───────────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = _uid(update)
    text = (update.message.text or "").strip()
    if not text:
        return

    if not _is_allowed(uid):
        await update.message.reply_text(
            f"⛔ You are not authorised. Your ID is `{uid}` — send it to the admin.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    global _event_loop
    if _event_loop is None:
        _event_loop = asyncio.get_running_loop()

    chat_id = update.effective_chat.id
    sess = _get_session(chat_id)

    async with sess.lock:
        sess.cancel_event.clear()
        sess.running = True

        placeholder = await update.message.reply_text("⏳")
        loop = asyncio.get_running_loop()
        chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()

        sess.history.append(Message.user(text))

        def _run():
            def on_event(ev):
                if ev.type == "text_delta" and ev.text:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, ev.text)

            try:
                result = sess.agent.send(sess.history, on_event=on_event, cancel=sess.cancel_event)
                sess.history = result.messages
            except Exception as exc:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, f"\n\n❌ Error: {exc}")
            finally:
                loop.call_soon_threadsafe(chunk_queue.put_nowait, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        buffer    = ""
        last_edit = time.monotonic()
        last_type = time.monotonic()

        while True:
            try:
                chunk = await asyncio.wait_for(chunk_queue.get(), timeout=TYPING_INTERVAL)
            except asyncio.TimeoutError:
                now = time.monotonic()
                if now - last_type >= TYPING_INTERVAL:
                    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)
                    last_type = now
                continue

            if chunk is None:
                break

            buffer += chunk
            now = time.monotonic()
            if now - last_edit >= STREAM_EDIT_INTERVAL and buffer:
                try:
                    await ctx.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=placeholder.message_id,
                        text=buffer[-TELEGRAM_MAX_LEN:],
                    )
                    last_edit = now
                except Exception:
                    pass

        thread.join(timeout=5)

        if buffer.strip():
            await _send_or_edit(ctx.bot, chat_id, placeholder.message_id, buffer)
        elif sess.cancel_event.is_set():
            await ctx.bot.edit_message_text(chat_id=chat_id, message_id=placeholder.message_id, text="⏹ Cancelled.")
        else:
            await ctx.bot.edit_message_text(chat_id=chat_id, message_id=placeholder.message_id, text="✓ Done.")

        sess.running = False


# ── entry point ────────────────────────────────────────────────────────────────

def main():
    global _CREDS
    _CREDS = _bootstrap()   # load creds + inject env vars; exits with message if missing
    token = _CREDS.get("telegram_bot_token", "")
    if not token:
        sys.exit("No Telegram bot token found. Run the wizard again: delete .clims/credentials.json and restart.")

    users = _allowed_users()
    log.info("Starting clims Telegram bot")
    log.info("Workspace: %s", _WORK_DIR)
    log.info("LLM: %s / %s", _CREDS.get("llm_provider"), _CREDS.get("llm_model"))
    log.info("Skills loaded: %s", sorted(_skills.keys()))
    if users:
        log.info("Allowed users: %s  (admin: %s)", users, users[0])
    else:
        log.warning("No allowed users set — bot is open to anyone!")

    global _app

    app = Application.builder().token(token).build()
    _app = app

    # any user
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("myid",        cmd_myid))
    app.add_handler(CommandHandler("skills",      cmd_skills))
    app.add_handler(CommandHandler("reset",       cmd_reset))
    app.add_handler(CommandHandler("cancel",      cmd_cancel))
    app.add_handler(CommandHandler("send",        cmd_send))

    # admin only (enforced inside the handlers)
    app.add_handler(CommandHandler("adduser",     cmd_adduser))
    app.add_handler(CommandHandler("removeuser",  cmd_removeuser))
    app.add_handler(CommandHandler("setkey",      cmd_setkey))
    app.add_handler(CommandHandler("config",      cmd_config))

    # messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot running — press Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
