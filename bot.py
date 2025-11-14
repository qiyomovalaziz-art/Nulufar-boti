import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

# Sozlamalar
settings = {
    "markup_percent": 3.0,
    "supported_currencies": ["BTC", "ETH", "XRP", "LTC", "DOGE", "SOL", "ADA", "MATIC", "SHIB", "TON"]
}

BASE_URL = "https://api.bitget.com"

def get_bitget_price(symbol: str):
    """Bitgetdan narxni olish (xavfsiz)"""
    try:
        full_symbol = f"{symbol}USDT"
        url = f"{BASE_URL}/api/spot/v1/market/ticker?symbol={full_symbol}"
        response = requests.get(url, timeout=6)
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

# Menyular
MAIN_MENU = [["💰 Sotib olish", "💳 Sotish"], ["📋 Buyurtmalar", "📊 Kurs"]]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💱 Obmen botiga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan foydalaning:",
        reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    )

# === Kurs menyusi ===
async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[cur] for cur in settings["supported_currencies"]]
    await update.message.reply_text(
        "Valyutani tanlang:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )

# === Valyuta narxini ko'rsatish ===
async def show_currency_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip().upper()
    if symbol not in settings["supported_currencies"]:
        await update.message.reply_text(
            f"❌ {symbol} qo'llab-quvvatlanmaydi.\nMavjud valyutalar: {', '.join(settings['supported_currencies'])}"
        )
        return

    price_data = get_bitget_price(symbol)
    if not price_data:
        await update.message.reply_text(
            f"❌ {symbol} uchun narxni olishda xatolik. Iltimos, keyinroq qayta urinib ko'ring."
        )
        return

    markup = settings["markup_percent"]
    # Sotib olish (foydalanuvchi BTC sotib oladi → biz USDT olamiz)
    buy_price = price_data["buy"] * (1 + markup / 100)
    # Sotish (foydalanuvchi BTC sotadi → biz USDT beramiz)
    sell_price = price_data["sell"] * (1 - markup / 100)

    msg = f"📈 <b>{symbol}/USDT</b>\n\n"
    msg += f"🛒 <b>Sotib olish:</b> ${buy_price:,.4f}\n"
    msg += f"💳 <b>Sotish:</b> ${sell_price:,.4f}\n\n"
    msg += f"ℹ️ Foiz: {markup}%"
    await update.message.reply_text(msg, parse_mode="HTML")

# === Sotib olish / Sotish — hozircha faqat yo'nalish ===
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Valyutani tanlang:", reply_markup=ReplyKeyboardMarkup([[cur] for cur in settings["supported_currencies"]], resize_keyboard=True))
    context.user_data["mode"] = "buy"

async def sell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Valyutani tanlang:", reply_markup=ReplyKeyboardMarkup([[cur] for cur in settings["supported_currencies"]], resize_keyboard=True))
    context.user_data["mode"] = "sell"

async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sizda hali buyurtma yo'q.")

# === Asosiy matn handleri (valyutani tanlaganda) ===
async def handle_currency_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text not in settings["supported_currencies"]:
        await update.message.reply_text("Iltimos, menyudan valyutani tanlang.")
        return

    mode = context.user_data.get("mode")
    if mode in ["buy", "sell"]:
        # Keyingi qadam: miqdor so'rash (kelajakda)
        await update.message.reply_text(f"Qancha {text} {'sotib olmoqchisiz' if mode == 'buy' else 'sotmoqchisiz'}? (miqdorni kiriting)")
        context.user_data["currency"] = text
    else:
        # Oddiy narx ko'rsatish
        await show_currency_price(update, context)

# === Asosiy ishga tushirish ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN .env faylida yo'q!")
        exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^💰 Sotib olish$"), buy_handler))
    app.add_handler(MessageHandler(filters.Regex("^💳 Sotish$"), sell_handler))
    app.add_handler(MessageHandler(filters.Regex("^📋 Buyurtmalar$"), orders_handler))
    app.add_handler(MessageHandler(filters.Regex("^📊 Kurs$"), show_rates))
    app.add_handler(MessageHandler(filters.TEXT, handle_currency_selection))

    print("🚀 Bot ishga tushdi...")
    app.run_polling()
