import os
import hmac
import hashlib
import time
import base64
import json
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

# API sozlamalari
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

BASE_URL = "https://api.bitget.com"

# Bitget API uchun so'rov yuborish funksiyasi
def sign_request(timestamp, method, path, query_string="", body=""):
    pre_hash = timestamp + method.upper() + path
    if query_string:
        pre_hash += "?" + query_string
    if body:
        pre_hash += body
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        pre_hash.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode('utf-8')

def bitget_request(method, path, params=None, body=None):
    timestamp = str(int(time.time() * 1000))
    query_string = ""
    body_str = json.dumps(body) if body else ""
    
    if method.upper() == "GET" and params:
        from urllib.parse import urlencode
        query_string = urlencode(params)
    
    signature = sign_request(timestamp, method, path, query_string, body_str)
    
    headers = {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }
    
    url = BASE_URL + path
    if method.upper() == "GET":
        if query_string:
            url += "?" + query_string
        response = requests.get(url, headers=headers)
    else:
        response = requests.post(url, headers=headers, data=body_str)
    
    return response.json()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom! Men Bitget orqali kriptovalyuta sotib olish/sotish botiman.\nFoydalanish: /buy BTC 0.001 yoki /sell ETH 0.1")

# /buy
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        symbol = context.args[0].upper()
        size = context.args[1]
        # SPOT bozori uchun `symbol` formati `BTCUSDT`
        # Agar foydalanuvchi faqat `BTC` bersa, `USDT` qo'shamiz (yoki boshqa quote)
        if "USD" not in symbol and "USDT" not in symbol:
            symbol += "USDT"
        
        # Order yuborish
        order_data = {
            "symbol": symbol,
            "side": "buy",
            "orderType": "market",
            "size": size
        }
        res = bitget_request("POST", "/api/spot/v1/trade/orders", body=order_data)
        if res.get("code") == "00000":
            await update.message.reply_text(f"✅ Sotib olish bajarildi!\nSymbol: {symbol}\nMiqdor: {size}")
        else:
            await update.message.reply_text(f"❌ Xatolik: {res.get('msg', 'Noma’lum xato')}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)}")

# /sell
async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        symbol = context.args[0].upper()
        size = context.args[1]
        if "USD" not in symbol and "USDT" not in symbol:
            symbol += "USDT"
        
        order_data = {
            "symbol": symbol,
            "side": "sell",
            "orderType": "market",
            "size": size
        }
        res = bitget_request("POST", "/api/spot/v1/trade/orders", body=order_data)
        if res.get("code") == "00000":
            await update.message.reply_text(f"✅ Sotish bajarildi!\nSymbol: {symbol}\nMiqdor: {size}")
        else:
            await update.message.reply_text(f"❌ Xatolik: {res.get('msg', 'Noma’lum xato')}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Xatolik: {str(e)}")

# Asosiy
if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    print("Bot ishga tushdi...")
    app.run_polling()
