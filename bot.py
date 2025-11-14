import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === Sozlamalar ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

# Faqat Bitgetda 100% ishlaydigan valyutalar (2025)
SUPPORTED_SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "LTCUSDT", "BCHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"]

# Admin foizi (3%)
MARKUP_PERCENT = 3.0

# === Bitget API ===
def get_bitget_price(symbol: str):
    """Bitgetdan narxni xavfsiz olish"""
    try:
        url = f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={symbol}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get("code") == "00000" and "data" in data:
            ticker = data["data"]
            return {
                "buy": float(ticker["ask"]),   # Sotib olish narxi (siz sotasiz)
                "sell": float(ticker["bid"])   # Sotish narxi (siz sotib olasiz)
            }
    except Exception as e:
        logging.error(f"Bitget API xatosi ({symbol}): {e}")
    return None

# === Menyu ===
MAIN_MENU = [["💰 Sotib olish", "💳 Sotish"], ["📋 Buyurtmalar", "📊 Kurs"]]

# === Handlerlar ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💱 Obmen botiga xush kelibsiz!\n\nQuyidagi tugmalardan foydalaning:",
        reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    )

async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currencies = [s.replace("USDT", "") for s in SUPPORTED_SYMBOLS]
    buttons = [[cur] for cur in currencies]
    await update.message.reply_text(
        "Valyutani tanlang:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )

async def show_currency_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur = update.message.text.strip().upper()
    symbol = f"{cur}USDT"
    
    if symbol not in SUPPORTED_SYMBOLS:
        currencies = [s.replace("USDT", "") for s in SUPPORTED_SYMBOLS]
        await update.message.reply_text(f"❌ Mavjud valyutalar: {', '.join(currencies)}")
        return

    price = get_bitget_price(symbol)
    if not price:
        await update.message.reply_text("❌ Narxni olishda xatolik. Iltimos, keyinroq urinib ko'ring.")
        return

    buy_price = price["buy"] * (1 + MARKUP_PERCENT / 100)
    sell_price = price["sell"] * (1 - MARKUP_PERCENT / 100)

    msg = f"📈 <b>{cur}/USDT</b>\n\n"
    msg += f"🛒 <b>Sotib olish:</b> ${buy_price:,.4f}\n"
    msg += f"💳 <b>Sotish:</b> ${sell_price:,.4f}\n\n"
    msg += f"ℹ️ Foiz: {MARKUP_PERCENT}%"
    await update.message.reply_text(msg, parse_mode="HTML")

# Sotib olish / Sotish — hozircha kurs ko'rsatish
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_rates(update, context)

async def sell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_rates(update, context)

async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sizda hali buyurtma yo'q.")

# Barcha matnli xabarlarni boshqarish
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    currencies = [s.replace("USDT", "") for s in SUPPORTED_SYMBOLS]
    if text in currencies:
        await show_currency_price(update, context)
    else:
        await update.message.reply_text("Iltimos, menyudan foydalaning.", reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True))

# === Ishga tushirish ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not TELEGRAM_TOKEN:
        exit("❌ TELEGRAM_BOT_TOKEN .env faylida yo'q!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^💰 Sotib olish$"), buy_handler))
    app.add_handler(MessageHandler(filters.Regex("^💳 Sotish$"), sell_handler))
    app.add_handler(MessageHandler(filters.Regex("^📋 Buyurtmalar$"), orders_handler))
    app.add_handler(MessageHandler(filters.Regex("^📊 Kurs$"), show_rates))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    print("🚀 Bot ishga tushdi...")
    app.run_polling()
