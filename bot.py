import os
import json
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters

# === Sozlamalar ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))
ADMIN_CHAT_ID = AUTHORIZED_USER_ID

# Admin sozlamalari (haqiqiy loyihada DB kerak)
settings = {
    "markup_percent": 3.0,  # 3% foyda
    "currencies": ["BTC", "ETH", "USDT"]
}

# Bitget API
BASE_URL = "https://api.bitget.com"

def get_bitget_price(symbol: str) -> dict:
    """Bitgetdan sotib olish/sotish narxlarini olish"""
    try:
        url = f"{BASE_URL}/api/spot/v1/market/ticker?symbol={symbol}"
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("code") == "00000":
            ticker = data["data"]
            return {
                "buy": float(ticker["ask"]),   # Boshqalar sotayotgan narx (siz sotib olasiz)
                "sell": float(ticker["bid"])   # Boshqalar sotib olayotgan narx (siz sotasiz)
            }
    except Exception as e:
        logging.error(f"Bitget API xatosi: {e}")
    return {"buy": 0, "sell": 0}

# === Menyular ===
MAIN_MENU = [["💰 Sotib olish", "💳 Sotish"], ["📊 Kurslar"]]
ADMIN_MENU = [["⚙️ Foiz sozlash", "📢 Xabar yuborish"]]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    menu = ADMIN_MENU if user_id == ADMIN_CHAT_ID else MAIN_MENU
    await update.message.reply_text(
        "💱 Obmen botiga xush kelibsiz!" if user_id != ADMIN_CHAT_ID else "👨‍💻 Admin panel",
        reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True)
    )

# === Kurslarni ko'rsatish ===
async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📈 Joriy kurslar (Bitget):\n\n"
    for cur in settings["currencies"]:
        if cur == "USDT":
            msg += "USDT/USDT: 1.00\n"
        else:
            price = get_bitget_price(f"{cur}USDT")
            markup = settings["markup_percent"]
            buy_with_markup = price["buy"] * (1 + markup / 100)
            sell_with_markup = price["sell"] * (1 - markup / 100)
            msg += f"{cur}/USDT:\n"
            msg += f"  Sotib olish: ${buy_with_markup:,.2f}\n"
            msg += f"  Sotish: ${sell_with_markup:,.2f}\n\n"
    await update.message.reply_text(msg)

# === Sotib olish ===
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Valyuta nomini kiriting (masalan: BTC):")

async def sell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Valyuta nomini kiriting (masalan: BTC):")

# === Valyuta kiritish ===
async def handle_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    user_id = update.effective_user.id

    if text not in settings["currencies"]:
        await update.message.reply_text("❌ Noto'g'ri valyuta. Mavjud: " + ", ".join(settings["currencies"]))
        return

    # Qaysi rejimda ekanligini saqlash
    if context.user_data.get("mode") == "buy":
        price_data = get_bitget_price(f"{text}USDT")
        if price_data["buy"] == 0:
            await update.message.reply_text("❌ Narxni olishda xatolik.")
            return
        buy_price = price_data["buy"] * (1 + settings["markup_percent"] / 100)
        context.user_data.update({"currency": text, "price": buy_price, "type": "buy"})
        await update.message.reply_text(f"1 {text} = ${buy_price:,.2f} USDT\n\nMiqdorni kiriting (USDT yoki {text}):")
    elif context.user_data.get("mode") == "sell":
        price_data = get_bitget_price(f"{text}USDT")
        if price_data["sell"] == 0:
            await update.message.reply_text("❌ Narxni olishda xatolik.")
            return
        sell_price = price_data["sell"] * (1 - settings["markup_percent"] / 100)
        context.user_data.update({"currency": text, "price": sell_price, "type": "sell"})
        await update.message.reply_text(f"1 {text} = ${sell_price:,.2f} USDT\n\nMiqdorni kiriting ({text}):")
    else:
        await update.message.reply_text("Iltimos, avval sotib olish yoki sotishni tanlang.")

# === Miqdor kiritish ===
async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        cur = context.user_data["currency"]
        price = context.user_data["price"]
        order_type = context.user_data["type"]

        if order_type == "buy":
            # Foydalanuvchi USDT miqdorini kiritadi yoki BTC
            # Oddiy: BTC miqdori kiritilsin
            btc_amount = amount
            usdt_total = btc_amount * price
            await update.message.reply_text(
                f"✅ Sotib olish:\n{btc_amount} {cur} = {usdt_total:,.2f} USDT\n\n"
                f"To'lov qilish uchun USDT hamyoningizni yuboring:"
            )
            context.user_data["final_amount"] = btc_amount
            context.user_data["step"] = "wallet"
        else:
            # Sotish: BTC miqdori kiritiladi
            btc_amount = amount
            usdt_total = btc_amount * price
            await update.message.reply_text(
                f"✅ Sotish:\n{btc_amount} {cur} = {usdt_total:,.2f} USDT\n\n"
                f"USDT hamyoningizni yuboring:"
            )
            context.user_data["final_amount"] = btc_amount
            context.user_data["step"] = "wallet"
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri miqdor. Raqam kiriting.")

# === Hamyon manzili ===
async def handle_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text
    cur = context.user_data["currency"]
    amount = context.user_data["final_amount"]
    order_type = context.user_data["type"]

    # Admin uchun xabar
    user = update.effective_user
    admin_text = (
        f"🆕 Yangi buyurtma!\n"
        f"👤 {user.full_name} (ID: {user.id})\n"
        f"📥 {order_type.upper()} {amount} {cur}\n"
        f"👛 Hamyon: {wallet}"
    )
    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{user.id}_{order_type}_{cur}_{amount}")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{user.id}")]
    ])
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, reply_markup=btns)
    await update.message.reply_text("✅ Buyurtma yuborildi! Admin tez orada ko'rib chiqadi.")
    context.user_data.clear()

# === Admin sozlamalari ===
async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Foizni kiriting (masalan: 3.5):")
    context.user_data["admin_action"] = "set_markup"

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("admin_action") == "set_markup":
        try:
            percent = float(update.message.text)
            settings["markup_percent"] = percent
            await update.message.reply_text(f"✅ Foiz {percent}% ga sozlandi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
        except:
            await update.message.reply_text("❌ Noto'g'ri qiymat.")
        del context.user_data["admin_action"]

# === Tasdiqlash/Bekor qilish ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("confirm_"):
        parts = data.split("_")
        user_id = int(parts[1])
        order_type = parts[2]
        cur = parts[3]
        amount = parts[4]
        await context.bot.send_message(chat_id=user_id, text=f"✅ Sizning {amount} {cur} {order_type} buyurtmangiz bajarildi!")
        await query.edit_message_text("✅ Buyurtma bajarildi.")
    elif data.startswith("cancel_"):
        user_id = int(data.split("_")[1])
        await context.bot.send_message(chat_id=user_id, text="❌ Buyurtma bekor qilindi.")
        await query.edit_message_text("❌ Bekor qilindi.")

# === Asosiy qism ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN .env faylida yo'q!")
        exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^💰 Sotib olish$"), lambda u, c: c.user_data.update({"mode": "buy"}) or buy_handler(u, c)))
    app.add_handler(MessageHandler(filters.Regex("^💳 Sotish$"), lambda u, c: c.user_data.update({"mode": "sell"}) or sell_handler(u, c)))
    app.add_handler(MessageHandler(filters.Regex("^📊 Kurslar$"), show_rates))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Foiz sozlash$"), admin_settings))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(chat_id=ADMIN_CHAT_ID), handle_admin_message))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.Chat(chat_id=ADMIN_CHAT_ID)), handle_currency))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Miqdor va hamyon uchun alohida handler
    app.add_handler(MessageHandler(
        filters.TEXT & (~filters.Regex("^💰|^💳|^📊|^⚙️")) & (~filters.Chat(chat_id=ADMIN_CHAT_ID)),
        handle_amount if "step" not in {} else handle_wallet  # Soddalashtirish uchun, realda state kerak
    ))

    print("🚀 Obmen bot ishga tushdi...")
    app.run_polling()
