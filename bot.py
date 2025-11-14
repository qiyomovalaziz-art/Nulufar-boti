import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 🔑 Bot tokeningizni qo'ying
BOT_TOKEN = "SIZNING_BOT_TOKENINGIZ"

# ExchangeRate API (bepul, ro'yxatdan o'tish shart emas)
EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/{}"

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# /start buyrug'i
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men valyuta almashish botiman.\n\n"
        "Misol: `100 USD to UZS` yoki `50 EUR to USD`\n"
        "Yordam uchun /help buyrug'idan foydalaning."
    )

# /help buyrug'i
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Format:\n<miqdor> <valyuta1> to <valyuta2>\n\n"
        "Misol:\n100 USD to UZS\n50 EUR to RUB\n\n"
        "Qo'llab-quvvatlanadigan valyutalar: USD, EUR, RUB, UZS, GBP, JPY, KZT va boshqalar."
    )

# Xabarlarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    try:
        # Format: "100 USD TO UZS"
        if " TO " not in text:
            raise ValueError("Noto'g'ri format. '100 USD to UZS' kabi yozing.")

        amount_part, to_part = text.split(" TO ")
        amount = float(amount_part.split()[0])
        from_currency = amount_part.split()[1]
        to_currency = to_part.strip()

        # API orqali kursni olish
        response = requests.get(EXCHANGE_API_URL.format(from_currency))
        if response.status_code != 200:
            raise ValueError("Valyuta topilmadi yoki xatolik yuz berdi.")

        data = response.json()
        rates = data.get("rates", {})

        if to_currency not in rates:
            raise ValueError(f"{to_currency} valyutasi qo'llab-quvvatlanmaydi.")

        converted = amount * rates[to_currency]
        result = f"{amount:,.2f} {from_currency} = {converted:,.2f} {to_currency}"
        await update.message.reply_text(result)

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}\nYordam uchun /help")

# Asosiy funksiya
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
