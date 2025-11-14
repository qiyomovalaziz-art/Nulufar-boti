import os
import sqlite3
import requests
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === Ma'lumotlar bazasini yaratish ===
def init_db():
    conn = sqlite3.connect('exchange.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS currencies (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            sell_markup REAL DEFAULT 0.02,
            buy_markup REAL DEFAULT 0.02
        )
    ''')
    # Namuna valyutalar (agar bo'sh bo'lsa)
    c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES ('BTC', 'Bitcoin')")
    c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES ('ETH', 'Ethereum')")
    c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES ('USDT', 'Tether')")
    conn.commit()
    conn.close()

# === Bitget API orqali narxni olish ===
def get_bitget_price(symbol: str):
    # Bitget API: https://www.bitget.com/api-doc/spot/market/Get-Ticker
    pair = f"{symbol}USDT"
    try:
        url = f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={pair}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == '00000':
                price = float(data['data']['close'])
                return price
            else:
                print(f"Bitget API xato: {data.get('msg', 'Noma’lum')}")
        else:
            print(f"HTTP {resp.status_code} - Bitget API ishlamadi")
    except Exception as e:
        print(f"Bitget so‘rovda xato: {e}")
    return None

# === Admin panel: valyutaga foiz qo‘shish ===
@router.message(Command("set_markup"))
async def set_markup(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, symbol, sell_markup, buy_markup = message.text.split()
        sell_markup = float(sell_markup)
        buy_markup = float(buy_markup)
        conn = sqlite3.connect('exchange.db')
        c = conn.cursor()
        c.execute("UPDATE currencies SET sell_markup = ?, buy_markup = ? WHERE symbol = ?",
                  (sell_markup, buy_markup, symbol.upper()))
        if c.rowcount == 0:
            await message.answer(f"❌ {symbol} topilmadi!")
        else:
            await message.answer(f"✅ {symbol} uchun foizlar yangilandi:\nSotish: {sell_markup*100:.1f}%\nSotib olish: {buy_markup*100:.1f}%")
        conn.commit()
        conn.close()
    except Exception as e:
        await message.answer("UsageId: /set_markup BTC 0.03 0.02")

# === Valyutalar ro‘yxati ===
def get_currencies():
    conn = sqlite3.connect('exchange.db')
    c = conn.cursor()
    c.execute("SELECT symbol, name FROM currencies")
    rows = c.fetchall()
    conn.close()
    return rows

# === Asosiy menyu ===
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    currencies = get_currencies()
    for symbol, name in currencies:
        builder.button(text=f"{symbol} ({name})", callback_data=f"view_{symbol}")
    builder.adjust(2)
    await message.answer("🌐 Siz qaysi valyutani tanlaysiz?", reply_markup=builder.as_markup())

# === Valyutani ko‘rish ===
@router.callback_query(lambda c: c.data.startswith("view_"))
async def view_currency(callback: types.CallbackQuery):
    symbol = callback.data.split("_")[1]
    usd_price = get_bitget_price(symbol)
    if not usd_price:
        await callback.message.answer("❌ Narxni olib bo‘lmadi. Keyinroq urinib ko‘ring.")
        return

    # Foizlarni olish
    conn = sqlite3.connect('exchange.db')
    c = conn.cursor()
    c.execute("SELECT sell_markup, buy_markup FROM currencies WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()

    if not row:
        await callback.message.answer("❌ Valyuta topilmadi.")
        return

    sell_markup, buy_markup = row

    # Hisob-kitob:
    # Siz sotasiz → bot sotib oladi → bot past narxda sotib oladi = narx * (1 - buy_markup)
    # Siz sotib olasiz → bot sotasiz → bot yuqori narxda sotadi = narx * (1 + sell_markup)

    buy_price = usd_price * (1 - buy_markup)    # Siz sotasiz, bot sotib oladi
    sell_price = usd_price * (1 + sell_markup)  # Siz sotib olasiz, bot sotasiz

    text = (
        f"📈 <b>{symbol}</b> joriy narxi (USDT):\n"
        f"• Sotib olish (siz sotasiz): <code>{buy_price:,.2f}</code> USDT\n"
        f"• Sotish (siz sotib olasiz): <code>{sell_price:,.2f}</code> USDT\n\n"
        f"Foyda: {sell_markup*100:.1f}% (sotish), {buy_markup*100:.1f}% (sotib olish)"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Sotish", callback_data=f"sell_{symbol}")],
        [InlineKeyboardButton(text="📥 Sotib olish", callback_data=f"buy_{symbol}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# === Ariza (hali avtomatik tranzaksiya emas — faqat ko'rsatish) ===
@router.callback_query(lambda c: c.data.startswith(("sell_", "buy_")))
async def handle_order(callback: types.CallbackQuery):
    action, symbol = callback.data.split("_")
    usd_price = get_bitget_price(symbol)
    if not usd_price:
        await callback.answer("Narxni olib bo‘lmadi.", show_alert=True)
        return

    conn = sqlite3.connect('exchange.db')
    c = conn.cursor()
    c.execute("SELECT sell_markup, buy_markup FROM currencies WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()

    if not row:
        await callback.answer("Valyuta topilmadi.", show_alert=True)
        return

    sell_markup, buy_markup = row

    if action == "sell":
        final_price = usd_price * (1 - buy_markup)
        await callback.message.edit_text(
            f"✅ Siz {symbol} ni sotmoqchisiz.\n"
            f"Hisoblangan narx: <code>{final_price:,.2f}</code> USDT\n\n"
            f"👉 Eslatma: Hozircha bot faqat narxni ko‘rsatadi. Haqiqiy tranzaksiya uchun API kalitlaringiz kerak bo‘ladi."
        )
    else:
        final_price = usd_price * (1 + sell_markup)
        await callback.message.edit_text(
            f"✅ Siz {symbol} ni sotib olmoqchisiz.\n"
            f"Hisoblangan narx: <code>{final_price:,.2f}</code> USDT"
        )

# === Orqaga qaytish ===
@router.callback_query(lambda c: c.data == "back")
async def go_back(callback: types.CallbackQuery):
    await cmd_start(callback.message)

# === Asosiy ishga tushirish ===
async def main():
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
