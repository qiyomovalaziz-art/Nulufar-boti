import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))
ADMIN_CHAT_ID = AUTHORIZED_USER_ID

# Sozlamalar (real loyihada DB kerak)
settings = {
    "markup_percent": 3.0,
    "currencies": ["BTC", "ETH"]
}

BASE_URL = "https://api.bitget.com"

def get_bitget_price(symbol: str):
    try:
        res = requests.get(f"{BASE_URL}/api/spot/v1/market/ticker?symbol={symbol}USDT", timeout=5)
        data = res.json()
        if data.get("code") == "00000":
            ticker = data["data"]
            return {"buy": float(ticker["ask"]), "sell": float(ticker["bid"])}
    except Exception as e:
        logging.error(f"API xatosi: {e}")
    return {"buy": 0, "sell": 0}

# Menyular
USER_MENU = [["📊 Kurs"]]
ADMIN_MENU = [["➕ Valyuta qo'shish", "⚙️ Foiz sozlash"], ["📤 Xabar yuborish"]]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_CHAT_ID:
        await update.message.reply_text("👨‍💻 Admin panel", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
    else:
        await update.message.reply_text("💱 Obmen botiga xush kelibsiz!", reply_markup=ReplyKeyboardMarkup(USER_MENU, resize_keyboard=True))

# === Foydalanuvchi: Valyuta kiritsa ===
async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text in settings["currencies"]:
        price = get_bitget_price(text)
        if price["buy"] == 0:
            await update.message.reply_text("❌ Narxni olishda xatolik.")
            return
        
        markup = settings["markup_percent"]
        buy_price = price["buy"] * (1 + markup / 100)
        sell_price = price["sell"] * (1 - markup / 100)
        
        msg = f"📈 {text}/USDT\n\n"
        msg += f"🛒 Sotib olish: ${buy_price:,.2f}\n"
        msg += f"💳 Sotish: ${sell_price:,.2f}\n\n"
        msg += f"ℹ️ Foiz: {markup}%"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(f"❌ Noto'g'ri valyuta. Mavjud: {', '.join(settings['currencies'])}")

# === Kurs menyusi ===
async def show_rates_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not settings["currencies"]:
        await update.message.reply_text("Valyuta yo'q.")
        return
    buttons = [[cur] for cur in settings["currencies"]]
    await update.message.reply_text("Valyutani tanlang:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

# === Admin: Valyuta qo'shish ===
async def add_currency_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Valyuta nomini kiriting (masalan: LTC):")
    context.user_data["action"] = "add_currency"

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()
    
    # Valyuta qo'shish
    if context.user_data.get("action") == "add_currency":
        if len(text) < 2:
            await update.message.reply_text("❌ Noto'g'ri valyuta nomi.")
            return
        # Bitgetda mavjudligini tekshirish
        price = get_bitget_price(text)
        if price["buy"] == 0:
            await update.message.reply_text(f"❌ {text} Bitgetda topilmadi.")
            return
        if text not in settings["currencies"]:
            settings["currencies"].append(text)
            await update.message.reply_text(f"✅ {text} qo'shildi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
        else:
            await update.message.reply_text(f"⚠️ {text} allaqachon mavjud.")
        del context.user_data["action"]
    
    # Foiz sozlash
    elif context.user_data.get("action") == "set_markup":
        try:
            percent = float(text)
            settings["markup_percent"] = percent
            await update.message.reply_text(f"✅ Foiz {percent}% ga sozlandi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
        except:
            await update.message.reply_text("❌ Raqam kiriting.")
        del context.user_data["action"]
    
    # Xabar yuborish
    elif context.user_data.get("action") == "broadcast":
        # Haqiqiy loyihada barcha foydalanuvchi ID lar DB dan olinadi
        await update.message.reply_text("✅ Xabar yuborildi (demo).")
        del context.user_data["action"]

# === Admin: Foiz sozlash ===
async def set_markup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Foizni kiriting (masalan: 3.5):")
    context.user_data["action"] = "set_markup"

# === Admin: Xabar yuborish ===
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Xabarni yozing:")
    context.user_data["action"] = "broadcast"

# === Asosiy qism ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN yo'q!")
        exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Umumiy handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📊 Kurs$"), show_rates_menu))
    
    # Admin handlerlari
    app.add_handler(MessageHandler(filters.Regex("^➕ Valyuta qo'shish$"), add_currency_start))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Foiz sozlash$"), set_markup_start))
    app.add_handler(MessageHandler(filters.Regex("^📤 Xabar yuborish$"), broadcast_start))
    app.add_handler(MessageHandler(filters.Chat(chat_id=ADMIN_CHAT_ID) & filters.TEXT, admin_text_handler))
    
    # Foydalanuvchi handleri (valyuta nomi)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.Chat(chat_id=ADMIN_CHAT_ID)), handle_user_text))

    print("🚀 Bot ishga tushdi...")
    app.run_polling()
