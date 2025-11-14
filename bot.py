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

# Log sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# O'zgaruvchilarni yuklash
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID")

# ID ni tekshirish
try:
    AUTHORIZED_USER_ID = int(AUTHORIZED_USER_ID) if AUTHORIZED_USER_ID else None
except:
    AUTHORIZED_USER_ID = None

BASE_URL = "https://api.bitget.com"

def is_authorized(update: Update) -> bool:
    if AUTHORIZED_USER_ID is None:
        return True
    return update.effective_user.id == AUTHORIZED_USER_ID

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
    except:
        return {"code": "99999", "msg": "Javob JSON emas"}

# Komandalar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⚠️ Sizga ruxsat yo‘q!")
        return
    await update.message.reply_text("✅ Salom! Foydalanish: /buy BTC 0.001 yoki /sell ETH 0.1")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⚠️ Sizga ruxsat yo‘q!")
        return
    try:
        if len(context.args) != 2:
            await update.message.reply_text("UsageId: /buy <symbol> <miqdor>")
            return
        symbol = context.args[0].upper().replace("USDT", "") + "USDT"
        size = context.args[1]
        res = bitget_request("POST", "/api/spot/v1/trade/orders", body={
            "symbol": symbol,
            "side": "buy",
            "orderType": "market",
            "size": size
        })
        if res.get("code") == "00000":
            await update.message.reply_text(f"✅ Sotib olish bajarildi!\n{symbol} — {size}")
        else:
            await update.message.reply_text(f"❌ Xatolik: {res.get('msg', 'Noma’lum')}")
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)}")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⚠️ Sizga ruxsat yo‘q!")
        return
    try:
        if len(context.args) != 2:
            await update.message.reply_text("UsageId: /sell <symbol> <miqdor>")
            return
        symbol = context.args[0].upper().replace("USDT", "") + "USDT"
        size = context.args[1]
        res = bitget_request("POST", "/api/spot/v1/trade/orders", body={
            "symbol": symbol,
            "side": "sell",
            "orderType": "market",
            "size": size
        })
        if res.get("code") == "00000":
            await update.message.reply_text(f"✅ Sotish bajarildi!\n{symbol} — {size}")
        else:
            await update.message.reply_text(f"❌ Xatolik: {res.get('msg', 'Noma’lum')}")
    except Exception as e:
        logger.error(f"Xato: {e}")
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)}")

# Ishga tushirish
if __name__ == "__main__":
    required = ["TELEGRAM_BOT_TOKEN", "BITGET_API_KEY", "BITGET_SECRET_KEY", "BITGET_PASSPHRASE"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        logger.error(f"Xatolik: .env da yo'q: {', '.join(missing)}")
        exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    logger.info("🚀 Bot ishga tushdi...")
    app.run_polling()
