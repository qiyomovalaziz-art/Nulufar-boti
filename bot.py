import os
import sqlite3
import requests
import asyncio
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import logging

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
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
    # Namuna valyutalar
    c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES ('BTC', 'Bitcoin')")
    c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES ('ETH', 'Ethereum')")
    c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES ('USDT', 'Tether')")
    conn.commit()
    conn.close()

# === Bitget API orqali narxni olish ===
def get_bitget_price(symbol: str):
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

# === Admin: valyutani qo'shish ===
@router.message(Command("add_currency"))
async def add_currency(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, symbol, name = message.text.split(maxsplit=2)
        symbol = symbol.upper()
        conn = sqlite3.connect('exchange.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO currencies (symbol, name) VALUES (?, ?)", (symbol, name))
        if c.rowcount == 0:
            await message.answer(f"❌ {symbol} allaqachon mavjud!")
        else:
            await message.answer(f"✅ {symbol} ({name}) qo‘shildi.")
        conn.commit()
        conn.close()
    except Exception as e:
        await message.answer("UsageId: /add_currency BTC Bitcoin")

# === Admin: foizni o'zgartirish ===
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
        await callback.message.edit_text("❌ Narxni olib bo‘lmadi. Keyinroq urinib ko‘ring.", reply_markup=None)
        return

    conn = sqlite3.connect('exchange.db')
    c = conn.cursor()
    c.execute("SELECT sell_markup, buy_markup FROM currencies WHERE symbol = ?", (symbol,))
    row = c.fetchone()
    conn.close()

    if not row:
        await callback.message.edit_text("❌ Valyuta topilmadi.", reply_markup=None)
        return

    sell_markup, buy_markup = row

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

# === Ariza: Sotish yoki sotib olish ===
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
        text = (
            f"✅ Siz {symbol} ni sotmoqchisiz.\n"
            f"Hisoblangan narx: <code>{final_price:,.2f}</code> USDT\n\n"
            f"👉 Eslatma: Haqiqiy tranzaksiya uchun Bitget Trade API kalitlari kerak."
        )
    else:
        final_price = usd_price * (1 + sell_markup)
        text = (
            f"✅ Siz {symbol} ni sotib olmoqchisiz.\n"
            f"Hisoblangan narx: <code>{final_price:,.2f}</code> USDT"
        )

    # Agar Bitget Trade API kalitlari kiritilgan bo'lsa — shu yerda tranzaksiya qilish mumkin
    if os.getenv("BITGET_API_KEY"):
        text += "\n\n⚡️ Haqiqiy tranzaksiya qilish uchun API kalitlaringiz tekshiriladi."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

# === Tasdiqlash / Bekor qilish ===
@router.callback_query(lambda c: c.data in ["confirm_order", "cancel_order"])
async def confirm_or_cancel(callback: types.CallbackQuery):
    if callback.data == "confirm_order":
        await callback.message.edit_text("✅ Arizangiz qabul qilindi. Admin bilan bog‘lanib davom eting.")
    else:
        await callback.message.edit_text("❌ Ariza bekor qilindi.")

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
