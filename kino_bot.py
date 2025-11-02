import os
import json
from datetime import datetime
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from openai import OpenAI

# 🔐 .env dan yuklash
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Sizning Telegram ID’ingiz

client = OpenAI(api_key=OPENAI_API_KEY)

USERS_FILE = "users.json"


# 🔄 JSON bilan ishlash
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ✅ /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    user_id = user.id

    users = load_users()

    # Yangi foydalanuvchini qo‘shish
    if str(user_id) not in users:
        users[str(user_id)] = {
            "name": user_name,
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)

        # 🔔 Admin'ga xabar yuborish
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🆕 Yangi foydalanuvchi kirdi!\n👤 Ism: {user_name}\n🆔 ID: {user_id}"
        )

    await update.message.reply_text(
        f"Assalomu alaykum, {user_name}! 🤖\n"
        "Nulufarxon😍 Botga xush kelibsiz!\n"
        "Savol yozing yoki rasm yuboring — men yordam beraman ✍️📸"
    )


# ✅ Matnga javob berish
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sen foydalanuvchiga yordam beradigan aqlli yordamchi botsan."},
            {"role": "user", "content": user_msg}

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sen rasmlarni tahlil qilib tushuntirib beradigan yordamchisan."},
            {"role": "user", "content": [
                {"type": "text", "text": "Rasimda nimalar borligini tushuntirib bering."},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}
        ]
    )

    answer = response.choices[0].message.content
    await update.message.reply_text(answer)


# 🧑‍💼 /admin komandasi — tugmalar bilan
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return

    keyboard = [
        [InlineKeyboardButton("📋 Foydalanuvchilar ro‘yxati", callback_data="show_users")],
        [InlineKeyboardButton("📈 Statistikani ko‘rish", callback_data="show_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🧑‍💼 Admin panelga xush kelibsiz:", reply_markup=reply_markup)


# 📋 Tugma: foydalanuvchilar ro‘yxatini ko‘rsatish
async def show_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    users = load_users()
    total = len(users)

    if total == 0:
        await query.edit_message_text("👥 Hozircha hech kim botga kirmagan.")
        return

    text = f"📊 <b>Foydalanuvchilar ro‘yxati</b>\n\n"
    for i, (uid, info) in enumerate(users.items(), 1):
        text += f"{i}. {info['name']} — {info['joined_at']}\n"

    text += f"\n<b>Jami:</b> {total} ta foydalanuvchi 👥"
    await query.edit_message_text(text, parse_mode="HTML")


# 📈 Tugma: statistikani ko‘rsatish
async def show_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    users = load_users()
    if not users:
        await query.edit_message_text("📉 Hali hech kim botga kirmagan.")
        return

    # Sana bo‘yicha sanash
    dates = [datetime.strptime(u["joined_at"], "%Y-%m-%d %H:%M:%S").date() for u in users.values()]
    dates.sort()

    counts = {}
    for d in dates:
        counts[d] = counts.get(d, 0) + 1

    x = list(counts.keys())
    y = []
    total = 0
    for d in x:
        total += counts[d]
        y.append(total)

    plt.figure()
    plt.plot(x, y, marker="o")
    plt.title("📈 Bot foydalanuvchilari soni o‘sishi")
    plt.xlabel("Sana")
    plt.ylabel("Jami foydalanuvchilar")
    plt.grid(True)

    img_path = "stats.png"
    plt.savefig(img_path)
    plt.close()

    await context.bot.send_photo(chat_id=ADMIN_ID, photo=open(img_path, "rb"))


# ✅ Asosiy ishga tushirish
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    # Tugma bosilishi
    app.add_handler(CallbackQueryHandler(show_users_callback, pattern="show_users"))
    app.add_handler(CallbackQueryHandler(show_stats_callback, pattern="show_stats"))

    # Xabarlar
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
