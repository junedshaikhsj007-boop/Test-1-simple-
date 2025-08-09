# main.py
import os
import asyncio
import logging
import threading
import time
import requests

from telethon import TelegramClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jak_bot")

# -------------------------
# Read config from environment (set these in Render)
# -------------------------
API_ID = os.environ.get("API_ID")            # must be int-like
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")      # your bot token (keep secret)
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1002324737561"))
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Jak_boi_bot")
NANOLINKS_API_KEY = os.environ.get("NANOLINKS_API_KEY", "")
NANOLINKS_API_URL = os.environ.get("NANOLINKS_API_URL", "https://nanolinks.in/api")
RESULTS_PER_PAGE = int(os.environ.get("RESULTS_PER_PAGE", "8"))

# basic validation
if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("Missing API_ID, API_HASH or BOT_TOKEN in environment. Exiting.")
    raise SystemExit("Set API_ID, API_HASH, BOT_TOKEN in environment variables before running.")

API_ID = int(API_ID)

# -------------------------
# Telethon client (used to read/search channel)
# -------------------------
telethon_session = os.environ.get("TELETHON_SESSION", "bot_session")
client = TelegramClient(telethon_session, API_ID, API_HASH)

def make_short_link(msg_id: int) -> str:
    """Use NanoLinks if configured, otherwise fallback to direct t.me link."""
    real_url = f"https://t.me/{BOT_USERNAME}?start=unlock_{msg_id}"
    if not NANOLINKS_API_KEY:
        return real_url
    try:
        params = {"api": NANOLINKS_API_KEY, "url": real_url}
        r = requests.get(NANOLINKS_API_URL, params=params, timeout=10)
        data = r.json()
        # NanoLinks may use different fields; try common ones
        short = data.get("shortenedUrl") or data.get("short_url") or data.get("url")
        return short or real_url
    except Exception as e:
        logger.warning("NanoLinks request failed: %s", e)
        return real_url

# -------------------------
# Bot handlers
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start and unlock links like ?start=unlock_<msg_id>"""
    args = context.args
    # handle unlock link
    if args and args[0].startswith("unlock_"):
        try:
            msg_id = int(args[0].replace("unlock_", ""))
            await context.bot.forward_message(
                chat_id=update.effective_chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )
        except Exception as e:
            logger.exception("Forward error: %s", e)
            await update.message.reply_text("⚠️ File not found or deleted.")
        return

    await update.message.reply_text("🔍 Send me a keyword to search my media library:")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search the configured channel for messages that include the query text."""
    if not update.message or not update.message.text:
        return
    query_text = update.message.text.strip()
    if not query_text:
        return

    results = []
    try:
        # Telethon client must be started already
        async for msg in client.iter_messages(CHANNEL_ID, search=query_text, limit=200):
            # safe text extraction
            msg_text = getattr(msg, "text", None) or getattr(msg, "message", None) or getattr(msg, "raw_text", "")
            if msg_text:
                preview = msg_text.split("\n")[0][:35] + ("..." if len(msg_text) > 35 else "")
            else:
                fname = getattr(getattr(msg, "file", None), "name", None)
                preview = (fname[:30] + "...") if fname else "Media File"
            results.append((msg.id, preview))
    except Exception as e:
        logger.exception("Search error: %s", e)
        await update.message.reply_text("🔍 Search failed. Try again later.")
        return

    if not results:
        await update.message.reply_text("❌ No results found.")
        return

    context.user_data["search_results"] = results
    context.user_data["current_page"] = 0
    context.user_data["query"] = query_text

    await send_results_page(update, context, page=0)

async def send_results_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    results = context.user_data.get("search_results", [])
    total_pages = (len(results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    context.user_data["current_page"] = page

    start_index = page * RESULTS_PER_PAGE
    end_index = start_index + RESULTS_PER_PAGE
    keyboard = []

    for msg_id, title in results[start_index:end_index]:
        keyboard.append([InlineKeyboardButton(title, callback_data=f"result_{msg_id}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅ Prev", callback_data="page_prev"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡", callback_data="page_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)
    query = context.user_data.get("query", "")

    if update.message:
        await update.message.reply_text(
            f"🔍 Found {len(results)} results for '{query}' (Page {page + 1}/{total_pages}):",
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            f"🔍 Found {len(results)} results for '{query}' (Page {page + 1}/{total_pages}):",
            reply_markup=reply_markup
        )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "page_next":
        await send_results_page(update, context, context.user_data["current_page"] + 1)
    elif data == "page_prev":
        await send_results_page(update, context, context.user_data["current_page"] - 1)
    elif data.startswith("result_"):
        msg_id = int(data.replace("result_", ""))
        short_link = make_short_link(msg_id)
        # edit to show link (user will click and get unlock flow)
        await query.edit_message_text(
            text=f"👉 [Click here to get your result]({short_link})\n\n(Wait for ads, you'll come back here automatically)",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

# -------------------------
# Telethon startup (as a bot)
# -------------------------
async def telethon_init():
    try:
        # Start Telethon using bot token (no interactive login)
        await client.start(bot_token=BOT_TOKEN)
        logger.info("Telethon client started (bot account).")
    except Exception as e:
        logger.exception("Failed to start Telethon client: %s", e)

# -------------------------
# Small web server (health & root) - useful if you use "Web Service"
# -------------------------
def run_web_server():
    # keep Flask optional and simple
    try:
        from flask import Flask
    except Exception:
        logger.warning("Flask not installed, skipping web server (fine for Background Worker).")
        return

    app = Flask(__name__)

    @app.route("/")
    def home():
        return f"{BOT_USERNAME} Bot is running!"

    @app.route("/health")
    def health():
        return "OK", 200

    port = int(os.environ.get("PORT", "8080"))
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    ).start()
    logger.info("Web server started on port %s", port)

# -------------------------
# Main
# -------------------------
def main():
    run_web_server()  # optional health endpoints (works on Render web services)
    loop = asyncio.get_event_loop()
    loop.create_task(telethon_init())

    # Telegram bot app (python-telegram-bot)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    logger.info("✅ Bot is running (polling). Press Ctrl+C to stop.")
    try:
        app.run_polling()
    except Exception as e:
        logger.exception("Bot exited with error: %s", e)

if __name__ == "__main__":
    main()
