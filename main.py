import asyncio
import requests
import time
import threading
from telethon import TelegramClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- Telegram API ---
api_id = 22467314
api_hash = "08181401f6807cdc954f6c7d8231dfcf"
client = TelegramClient("session", api_id, api_hash)

# --- Bot ---
BOT_TOKEN = "7962211786:AAHBZIxnb6oJr2W3KXQs74x31kn2KDpIJGE"
CHANNEL_ID = -1002324737561
BOT_USERNAME = "Jak_boi_bot"

# --- NanoLinks API ---
NANOLINKS_API_KEY = "3d2e0094ca3b5a3876561c5773ce59a35c2e3493"
NANOLINKS_API_URL = "https://nanolinks.in/api"

# --- UptimeRobot Config ---
UPTIME_ROBOT_API_KEY = "u3062007-45b2fb20c53821a6b2ed4eaf"
UPTIME_ROBOT_MONITOR_URL = "https://replit.com/@junedshaikhsj00/Jak-boi-bot"
UPTIME_ROBOT_INTERVAL = 300  # 5 minutes

# --- Constants ---
RESULTS_PER_PAGE = 8

def make_short_link(msg_id: int) -> str:
    real_url = f"https://t.me/{BOT_USERNAME}?start=unlock_{msg_id}"
    try:
        params = {"api": NANOLINKS_API_KEY, "url": real_url}
        r = requests.get(NANOLINKS_API_URL, params=params, timeout=10)
        data = r.json()
        short = data.get("shortenedUrl")
        return short if short else real_url
    except Exception as e:
        print(f"NanoLinks error: {e}")
        return real_url

def start_uptime_robot_monitor():
    monitor_exists = False
    monitors = requests.post(
        "https://api.uptimerobot.com/v2/getMonitors",
        data={"api_key": UPTIME_ROBOT_API_KEY, "format": "json", "logs": "0"}
    ).json()

    if monitors.get("stat") == "ok":
        for monitor in monitors.get("monitors", []):
            if monitor.get("url") == UPTIME_ROBOT_MONITOR_URL:
                monitor_exists = True
                print(f"Monitor already exists: {monitor.get('id')}")
                break

    if not monitor_exists:
        response = requests.post(
            "https://api.uptimerobot.com/v2/newMonitor",
            data={
                "api_key": UPTIME_ROBOT_API_KEY,
                "format": "json",
                "type": "1",
                "url": UPTIME_ROBOT_MONITOR_URL,
                "friendly_name": f"{BOT_USERNAME} Telegram Bot",
                "interval": str(UPTIME_ROBOT_INTERVAL)
            }
        )
        print("Monitor created:", response.json())

    def ping_server():
        while True:
            try:
                requests.get(UPTIME_ROBOT_MONITOR_URL, timeout=10)
                print(f"Pinged at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                print(f"Ping error: {e}")
            time.sleep(UPTIME_ROBOT_INTERVAL - 30)

    threading.Thread(target=ping_server, daemon=True).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].startswith("unlock_"):
        try:
            msg_id = int(args[0].replace("unlock_", ""))
            await context.bot.forward_message(
                chat_id=update.message.chat_id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )
        except Exception as e:
            print(f"Forward error: {e}")
            await update.message.reply_text("⚠️ File not found or deleted.")
        return
    await update.message.reply_text("🔍 Send me a keyword to search my media library:")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip().lower()
    if not query_text:
        return

    results = []
    try:
        async with client:
            async for msg in client.iter_messages(CHANNEL_ID, search=query_text, limit=100):
                if msg.text:
                    preview = msg.text.split('\n')[0][:35] + "..." if len(msg.text) > 35 else msg.text
                else:
                    preview = f"{msg.file.name[:30]}..." if msg.file and msg.file.name else "Media File"
                results.append((msg.id, preview))
    except Exception as e:
        print(f"Search error: {e}")
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
        await query.edit_message_text(
            text=f"👉 [Click here to get your result]({short_link})\n\n(Wait for ads, you'll come back here automatically)",
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

async def telethon_init():
    await client.start()
    print("Telethon client started")

def run_web_server():
    from flask import Flask
    app = Flask(__name__)

    @app.route('/')
    def home():
        return f"{BOT_USERNAME} Bot is running!"

    @app.route('/health')
    def health():
        return "OK", 200

    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False),
        daemon=True
    ).start()
    print("Web server started")

def main():
    run_web_server()
    start_uptime_robot_monitor()
    loop = asyncio.get_event_loop()
    loop.create_task(telethon_init())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
