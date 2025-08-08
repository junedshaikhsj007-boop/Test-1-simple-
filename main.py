import asyncio
from telethon import TelegramClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- Telegram API (full) ---
api_id = 23646229
api_hash = "965d89616074f8bc757fccb4c68326be"
client = TelegramClient("session", api_id, api_hash)

# --- Telegram Bot ---
BOT_TOKEN = "8214904903:AAEb9qoSzBzd3Sr6jbJ4IHO_9ClkZLp3ZFo"
CHANNEL_ID = -1002324737561
BOT_USERNAME = "Juned_boi_bot"

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].startswith("unlock_"):
        try:
            msg_id = int(args[0].replace("unlock_", ""))
            # FORWARD THE ORIGINAL MESSAGE USING BOT API
            await context.bot.forward_message(
                chat_id=update.message.chat_id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )
        except Exception as e:
            print(f"Forward error: {e}")
            await update.message.reply_text("⚠️ Failed to retrieve file. It might have expired or been deleted.")
        return

    await update.message.reply_text("🔍 Send me a keyword to search my media library:")

# --- Search Handler ---
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip().lower()
    if not query:
        return

    results = []
    try:
        async with client:
            async for msg in client.iter_messages(CHANNEL_ID, search=query, limit=15):
                # Create preview text for button
                if msg.text:
                    preview = msg.text.split('\n')[0][:35] + "..." if len(msg.text) > 35 else msg.text
                else:
                    preview = f"{msg.file.name[:30]}..." if msg.file else "Media File"
                
                results.append((msg.id, preview))
    except Exception as e:
        print(f"Search error: {e}")
        await update.message.reply_text("🔎 Search failed. Please try again later.")
        return

    if not results:
        await update.message.reply_text("❌ No results found. Try different keywords.")
        return

    # Create inline buttons
    keyboard = []
    for mid, text in results:
        keyboard.append([InlineKeyboardButton(text, callback_data=str(mid))])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🔍 Found {len(results)} results for '{query}':",
        reply_markup=reply_markup
    )

# --- Button Click Handler ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg_id = query.data

    # Generate direct unlock link
    unlock_link = f"https://t.me/{BOT_USERNAME}?start=unlock_{msg_id}"
    
    await query.edit_message_text(
        text=f"✅ Click below to get your file:\n"
             f"➡️ {unlock_link}\n\n"
             "⚠️ Link valid for 24 hours | Auto-deletes after download",
        disable_web_page_preview=True
    )

# --- Start Telethon Client ---
async def telethon_init():
    await client.start()
    print("Telethon client started")

# --- Main Application ---
def main():
    # Start Telethon in background
    loop = asyncio.get_event_loop()
    loop.create_task(telethon_init())

    # Setup bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
￼Enter
