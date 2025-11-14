import os
import hmac
import hashlib
import time
import base64
import json
import requests
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Loglarni sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# .env faylini yuklash
load_dotenv()

# Telegram va Bitget sozlamalari
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

# Faqat sizga ruxsat berilgan bo'lsin
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID")

# ID ni tekshirish va int ga aylantirish
try:
    AUTHORIZED_USER_ID = int(AUTHORIZED_USER_ID) if AUTHORIZED_USER_ID else None
except (ValueError, TypeError):
    AUTHORIZED_USER_ID = None

BASE_URL = "https://api.bitget.com"

# Foydalanuvchi ruxsati
def is_authorized(update: Update) -> bool:
    if AUTHORIZED_USER_ID is None:
        return True  # Agar AUTHORIZED_USER_ID yo'q bo'lsa, hamma uchun ochiq
    return update.effective_user.id == AUTHORIZED_USER_ID

# Bitget API so'rovini imzolash
def sign_request(timestamp: str, method: str, path: str, query_string: str = "", body: str = "") -> str:
    pre_hash = timestamp + method.upper() + path
    if query_string:
        pre_hash += "?" + query_string
    if body:
        pre_hash += body
    signature = hmac.new(
        BITGET_SECRET_KEY.encode('utf-8'),
        pre_hash.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode('utf-8')

# Umumiy Bitget API so'rovi
def bitget_request(method: str, path: str, params=None, body=None) -> dict:
    timestamp = str(int(time.time() * 1000))
    query_string = ""
    body_str = json.dumps(body) if body else ""
    
    if method.upper() == "GET" and params:
        from urllib.parse import urlencode
        query_string = urlencode(params)
    
    signature = sign_request(timestamp, method, path, query_string, body_str)
    
    headers = {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": BITGET_PASSPHRASE,
        "Content-Type": "application/json"
    }
    
    url = BASE_URL + path
    if method.upper() == "GET":
        if query_string:
            url += "?" + query_string
        response = requests.get(url, headers=headers, timeout=10)
    else:
        response = requests.post(url, headers=headers, data=body_str, timeout=10)
    
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"code": "99999", "msg": "Javob JSON formatida emas"}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⚠️ Sizga ruxsat yo‘q!")
        return
    await update.message.reply_text(
        "✅ Salom! Men Bitget orqali kriptovalyuta sotib olish/sotish botiman.\n\n"
        "Foydalanish:\n"
        "/buy BTC 0.001\n"
        "/sell ETH 0.1\n\n"
        "Diqqat: Summa — USDT bozorida miqdor (masalan, BTC miqdori)."
    )

# /buy
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⚠️ Sizga ruxsat yo‘q!")
        return
    try:
        if len(context.args) != 2:
            await update.message.reply_text("UsageId: /buy <symbol> <miqdor>\nMisol: /buy BTC 0.001")
            return
        symbol = context.args[0].upper().replace("USDT", "")
        size = context.args[1]
        full_symbol = symbol + "USDT"

        order_data = {
            "symbol": full_symbol,
            "side": "buy",
            "orderType": "market",
            "size": size
        }
        res = bitget_request("POST", "/api/spot/v1/trade/orders", body=order_data)
        if res.get("code") == "00000":
            await update.message.reply_text(f"✅ Sotib olish bajarildi!\nSymbol: {full_symbol}\nMiqdor: {size}")
        else:
            await update.message.reply_text(f"❌ Xatolik: {res.get('msg', 'Noma’lum xato')}")
    except Exception as e:
        logger.error(f"Xatolik /buy da: {e}")
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)}")

# /sell
async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⚠️ Sizga ruxsat yo‘q!")
        return
    try:
        if len(context.args) != 2:
            await update.message.reply_text("UsageId: /sell <symbol> <miqdor>\nMisol: /sell BTC 0.001")
            return
        symbol = context.args[0].upper().replace("USDT", "")
        size = context.args[1]
        full_symbol = symbol + "USDT"

        order_data = {
            "symbol": full_symbol,
            "side": "sell",
            "orderType": "market",
            "size": size
        }
        res = bitget_request("POST", "/api/spot/v1/trade/orders", body=order_data)
        if res.get("code") == "00000":
            await update.message.reply_text(f"✅ Sotish bajarildi!\nSymbol: {full_symbol}\nMiqdor: {size}")
        else:
            await update.message.reply_text(f"❌ Xatolik: {res.get('msg', 'Noma’lum xato')}")
    except Exception as e:
        logger.error(f"Xatolik /sell da: {e}")
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)}")

# Asosiy
if __name__ == "__main__":
    # Majburiy o'zgaruvchilarni tekshirish
    required_vars = ["TELEGRAM_BOT_TOKEN", "BITGET_API_KEY", "BITGET_SECRET_KEY", "BITGET_PASSPHRASE"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        logger.error(f"❌ .env faylida quyidagi majburiy o'zgaruvchilar yo'q: {', '.join(missing)}")
        exit(1)
    
    if AUTHORIZED_USER_ID is None:
        logger.warning("⚠️ AUTHORIZED_USER_ID sozlanmagan — bot hamma uchun ochiq!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    
    logger.info("🚀 Bot ishga tushdi...")
    app.run_polling()
