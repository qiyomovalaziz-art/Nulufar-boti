import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup,
    InlineKeyboardButton, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# === Sozlamalar ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_USER_ID = int(os.getenv("AUTHORIZED_USER_ID", "0"))
ADMIN_CHAT_ID = AUTHORIZED_USER_ID  # Admin — siz

# Foydalanuvchi ma'lumotlarini saqlash (real loyihada — DB kerak!)
user_data = {}
orders = {}
currencies = ["BTC", "ETH", "USDT"]
bank_cards = {
    "BTC": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "USDT": "TJq9cFh9QvKJz1G8y6xQ5W8a7b9c0d1e2f"
}

# === Menyular ===
MAIN_MENU = [["💰 Sotib olish", "💳 Sotish"], ["📋 Buyurtmalar", "📊 Valyuta kurslari"]]
ADMIN_MENU = [["➕ Valyuta qo'shish", "➖ Valyuta o'chirish"], ["💳 Karta sozlash", "📤 Xabar yuborish"], ["📋 Buyurtmalar"]]

# === Yordamchi funksiyalar ===
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_CHAT_ID

def save_order(user_id: int, order_type: str, data: dict):
    order_id = f"ORD{len(orders)+1:04}"
    orders[order_id] = {
        "user_id": user_id,
        "type": order_type,
        "data": data,
        "status": "pending",
        "timestamp": datetime.now().isoformat()
    }
    return order_id

def get_user_name(update: Update) -> str:
    user = update.effective_user
    return user.full_name or user.username or f"User{user.id}"

# === Asosiy menyu ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        text = "👨‍💻 Admin panel\nFoydalanuvchi menyusi uchun /user"
    else:
        text = "💱 Obmen botiga xush kelibsiz!"
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(ADMIN_MENU if is_admin(user_id) else MAIN_MENU, resize_keyboard=True)
    )

async def user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            "Foydalanuvchi menyusi:",
            reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        )

# === Valyuta kurslari (Bitget API orqali) ===
async def show_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "📈 Joriy kurslar (taxminan):\n\n"
    for cur in currencies:
        if cur == "USDT":
            msg += f"USDT/USDT: 1.00 🔁\n"
        else:
            # Haqiqiy API chaqiruvi kerak, lekin hozircha statik
            buy = 60000 + (1000 if cur == "BTC" else 3000)
            sell = buy * 0.995
            msg += f"{cur}/USDT:\n  Sotib olish: ${buy:,.0f}\n  Sotish: ${sell:,.0f}\n\n"
    await update.message.reply_text(msg)

# === Sotib olish ===
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Qaysi valyutani sotib olmoqchisiz?",
        reply_markup=ReplyKeyboardMarkup([[cur] for cur in currencies], resize_keyboard=True)
    )
    return

# === Sotish ===
async def sell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Qaysi valyutani sotmoqchisiz?",
        reply_markup=ReplyKeyboardMarkup([[cur] for cur in currencies], resize_keyboard=True)
    )

# === Buyurtmalar ===
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_orders = [v for k, v in orders.items() if v["user_id"] == user_id]
    if not user_orders:
        await update.message.reply_text("Sizda hali buyurtma yo'q.")
        return
    msg = "📋 Sizning buyurtmalaringiz:\n\n"
    for ord in user_orders:
        msg += f"🆔 {ord['data'].get('order_id', 'Noma’lum')}\n"
        msg += f"📤 {ord['type']} | {ord['data'].get('currency', '?')} {ord['data'].get('amount', '?')}\n"
        msg += f"📊 {ord['status']}\n\n"
    await update.message.reply_text(msg)

# === Xabar boshqaruvi ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user_name = get_user_name(update)

    # Admin panel
    if is_admin(user_id):
        if text == "➕ Valyuta qo'shish":
            await update.message.reply_text("Yangi valyuta nomini yuboring (masalan: LTC):")
            context.user_data["action"] = "add_currency"
        elif text == "➖ Valyuta o'chirish":
            await update.message.reply_text("O'chirish uchun valyutani tanlang:", reply_markup=ReplyKeyboardMarkup([[cur] for cur in currencies], resize_keyboard=True))
            context.user_data["action"] = "remove_currency"
        elif text == "💳 Karta sozlash":
            await update.message.reply_text("Valyutani tanlang:", reply_markup=ReplyKeyboardMarkup([[cur] for cur in currencies], resize_keyboard=True))
            context.user_data["action"] = "set_card"
        elif text == "📤 Xabar yuborish":
            await update.message.reply_text("Barcha foydalanuvchilarga yuborish uchun xabarni yozing:")
            context.user_data["action"] = "broadcast"
        elif text == "📋 Buyurtmalar":
            if not orders:
                await update.message.reply_text("Buyurtma yo'q.")
            else:
                for oid, ord in orders.items():
                    if ord["status"] == "pending":
                        user = await context.bot.get_chat(ord["user_id"])
                        btns = InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{oid}"),
                             InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{oid}")]
                        ])
                        await update.message.reply_text(
                            f"🆔 {oid}\n"
                            f"👤 {user.full_name or user.username} (ID: {ord['user_id']})\n"
                            f"📥 {ord['type']} → {ord['data'].get('currency', '?')} {ord['data'].get('amount', '?')}\n"
                            f"📄 Chek: {ord['data'].get('receipt', 'Yuborilmagan')}",
                            reply_markup=btns
                        )
        elif context.user_data.get("action") == "add_currency":
            currencies.append(text.upper())
            del context.user_data["action"]
            await update.message.reply_text(f"{text.upper()} qo'shildi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
        elif context.user_data.get("action") == "remove_currency":
            if text in currencies:
                currencies.remove(text)
                await update.message.reply_text(f"{text} o'chirildi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
            del context.user_data["action"]
        elif context.user_data.get("action") == "set_card":
            context.user_data["card_currency"] = text
            await update.message.reply_text(f"{text} uchun karta raqamini yuboring:")
            context.user_data["action"] = "set_card_number"
        elif context.user_data.get("action") == "set_card_number":
            bank_cards[context.user_data["card_currency"]] = text
            del context.user_data["action"]
            del context.user_data["card_currency"]
            await update.message.reply_text("Karta saqlandi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
        elif context.user_data.get("action") == "broadcast":
            for oid in orders:
                try:
                    await context.bot.send_message(chat_id=orders[oid]["user_id"], text=f"📢 Admin xabari:\n\n{text}")
                except:
                    pass
            del context.user_data["action"]
            await update.message.reply_text("Xabar yuborildi!", reply_markup=ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True))
        return

    # Oddiy foydalanuvchi
    if text in currencies:
        context.user_data["currency"] = text
        await update.message.reply_text("Miqdorni yuboring:")
        return

    if "currency" in context.user_data and "amount" not in context.user_data:
        context.user_data["amount"] = text
        cur = context.user_data["currency"]
        if context.user_data.get("mode") == "sell":
            await update.message.reply_text(f"{cur} hamyon manzilingizni yuboring:")
            context.user_data["step"] = "wallet"
        else:
            card = bank_cards.get(cur, "Karta yo'q")
            await update.message.reply_text(
                f"💳 To'lov karta:\n<code>{card}</code>\n\n"
                f"Chek sifatida to'lov tasdiqlash rasmini yuboring:",
                parse_mode="HTML"
            )
            context.user_data["step"] = "receipt"
        return

    if context.user_data.get("step") == "wallet":
        context.user_data["wallet"] = text
        await update.message.reply_text("Karta raqamingizni yuboring:")
        context.user_data["step"] = "card"
        return

    if context.user_data.get("step") == "card":
        context.user_data["user_card"] = text
        await update.message.reply_text("Chek sifatida to'lov tasdiqlash rasmini yuboring:")
        context.user_data["step"] = "receipt"
        return

    if context.user_data.get("step") == "receipt":
        # Buyurtma saqlash
        mode = context.user_data.get("mode", "buy")
        order_id = save_order(
            user_id,
            mode,
            {
                "currency": context.user_data["currency"],
                "amount": context.user_data["amount"],
                "wallet": context.user_data.get("wallet", ""),
                "user_card": context.user_data.get("user_card", ""),
                "receipt": "Rasm yoki matn yuborildi"
            }
        )
        context.user_data["order_id"] = order_id

        # Admin uchun xabar
        receipt_info = "Rasm yoki matn yuborildi"
        admin_text = (
            f"🆕 Yangi buyurtma!\n"
            f"🆔 {order_id}\n"
            f"👤 {user_name} (ID: {user_id})\n"
            f"📱 Telefon: {update.effective_user.id}\n"
            f"📥 {mode.capitalize()} → {context.user_data['currency']} {context.user_data['amount']}\n"
            f"📄 Chek: {receipt_info}"
        )

        # Adminga tugmalar bilan yuborish
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
             InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{order_id}")]
        ])

        try:
            if update.message.photo:
                photo = update.message.photo[-1].file_id
                await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo, caption=admin_text, reply_markup=btns)
            else:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, reply_markup=btns)
        except Exception as e:
            logging.error(f"Admin xabar xatosi: {e}")

        await update.message.reply_text("✅ Buyurtmangiz qabul qilindi! Admin tez orada ko'rib chiqadi.", reply_markup=ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True))
        context.user_data.clear()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, order_id = query.data.split("_", 1)

    if order_id not in orders:
        await query.edit_message_text("❌ Buyurtma topilmadi.")
        return

    order = orders[order_id]
    user_id = order["user_id"]

    if action == "confirm":
        orders[order_id]["status"] = "confirmed"
        cur = order["data"]["currency"]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Sizning buyurtmangiz tasdiqlandi!\n\nSizga {cur} o'tkazildi."
        )
        await query.edit_message_text(f"✅ {order_id} tasdiqlandi.")

    elif action == "cancel":
        orders[order_id]["status"] = "cancelled"
        await context.bot.send_message(chat_id=user_id, text="❌ Buyurtmangiz bekor qilindi.")
        await query.edit_message_text(f"❌ {order_id} bekor qilindi.")

# === Asosiy ishga tushirish ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN .env faylida yo'q!")
        exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("user", user_menu))
    app.add_handler(MessageHandler(filters.Regex("^💰 Sotib olish$"), lambda u, c: setattr(c.user_data, 'mode', 'buy') or buy_handler(u, c)))
    app.add_handler(MessageHandler(filters.Regex("^💳 Sotish$"), lambda u, c: setattr(c.user_data, 'mode', 'sell') or sell_handler(u, c)))
    app.add_handler(MessageHandler(filters.Regex("^📋 Buyurtmalar$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^📊 Valyuta kurslari$"), show_rates))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Obmen bot ishga tushdi...")
    app.run_polling()
