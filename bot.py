import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))

# Faqat Bitgetda mavjud valyutalar (2025-yil holatiga ko'ra)
SUPPORTED_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "XRPUSDT", "LTCUSDT", "DOGEUSDT",
    "SOLUSDT", "ADAUSDT", "MATICUSDT", "AVAXUSDT", "LINKUSDT"
]

def get_bitget_price(symbol: str):
    """Bitgetdan narxni xavfsiz olish"""
    try:
        url = f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={symbol}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Muvaffaqiyatli javobmi?
        if data.get("code") == "00000" and "data" in data:
            ticker = data["data"]
            return {
                "symbol": symbol,
                "buy": float(ticker["ask"]),   # Boshqalar sotayotgan narx
                "sell": float(ticker["bid"])   # Boshqalar sotib olayotgan narx
            }
        else:
            logging.error(f"API xato: {data.get('msg', 'Noma’lum')}")
            return None
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        return None

# Menyu
MAIN_MENU = [["💰 Sotib olish", "💳 Sotish"], ["📋 Buyurtmalar", "📊 Kurs"]]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💱 Obmen botiga xush kelibsiz!",
        reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    )

async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Faqat valyuta nomlari (BTC, ETH...)
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
        await update.message.reply_text(
            f"❌ {cur} qo'llab-quvvatlanmaydi.\nMavjud: {', '.join(currencies)}"
        )
        return

    price = get_bitget_price(symbol)
    if not price:
        await update.message.reply_text(
            f"❌ {cur} uchun narxni olishda xatolik. Iltimos, keyinroq qayta urinib ko'ring."
        )
        return

    # Admin foiz (3%)
    markup_percent = 3.0
    buy_price = price["buy"] * (1 + markup_percent / 100)
    sell_price = price["sell"] * (1 - markup_percent / 100)

    msg = f"📈 <b>{cur}/USDT</b>\n\n"
    msg += f"🛒 <b>Sotib olish:</b> ${buy_price:,.4f}\n"
    msg += f"💳 <b>Sotish:</b> ${sell_price:,.4f}\n\n"
    msg += f"ℹ️ Foiz: {markup_percent}%"
    await update.message.reply_text(msg, parse_mode="HTML")

# Boshqa handlerlar (sotib olish, sotish...)
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_rates(update, context)

async def sell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_rates(update, context)

async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sizda hali buyurtma yo'q.")

# Asosiy matn handleri
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text in [s.replace("USDT", "") for s in SUPPORTED_SYMBOLS]:
        await show_currency_price(update, context)
    else:
        await update.message.reply_text("Iltimos, menyudan foydalaning.")

# Ishga tushirish
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not TELEGRAM_TOKEN:
        exit("❌ TELEGRAM_BOT_TOKEN yo'q!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^💰 Sotib olish$"), buy_handler))
    app.add_handler(MessageHandler(filters.Regex("^💳 Sotish$"), sell_handler))
    app.add_handler(MessageHandler(filters.Regex("^📋 Buyurtmalar$"), orders_handler))
    app.add_handler(MessageHandler(filters.Regex("^📊 Kurs$"), show_rates))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    print("🚀 Bot ishga tushdi...")
    app.run_polling()
