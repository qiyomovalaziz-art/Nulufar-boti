import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F

# 🔧 Sozlamalar
BOT_TOKEN = "8069725986:AAG4VIEV_O8snJVb-OqCraWOKXPpaKvy05A"
OMDB_API_KEY = "OMDB_API_KALITINGIZNI_BUYERGA_QOYING"

# 🔹 Log yozish
logging.basicConfig(level=logging.INFO)

# 🔹 Bot va dispatcher yaratish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# /start komandasi
@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("🎬 Salom! Men kino botman.\nFilm nomini yozing, men sizga ma’lumot topib beraman.")

# Foydalanuvchi film nomini yuborganda
@dp.message(F.text)
async def get_movie_info(message: Message):
    film_nomi = message.text.strip()
    url = f"http://www.omdbapi.com/?t={film_nomi}&apikey={OMDB_API_KEY}&plot=short&r=json"

    response = requests.get(url)
    data = response.json()

    if data.get("Response") == "True":
        title = data.get("Title", "Noma’lum")
        year = data.get("Year", "—")
        genre = data.get("Genre", "—")
        plot = data.get("Plot", "—")
        poster = data.get("Poster", "")

        text = f"🎥 <b>{title}</b> ({year})\n🎭 Janr: {genre}\n📝 Syujet: {plot}"

        if poster != "N/A":
            await message.answer_photo(photo=poster, caption=text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Film topilmadi. Iltimos, nomini to‘g‘ri yozing.")

# 🔹 Botni ishga tushirish
if __name__ == "__main__":
    import asyncio
    async def main():
        await dp.start_polling(bot)
    asyncio.run(main())
