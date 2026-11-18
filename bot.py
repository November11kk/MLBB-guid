import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from google import genai
from google.genai import types as genai_types

# Ключи подтянутся автоматически из настроек хостинга
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

user_chats = {}

# Характер бота (можешь поменять текст внутри кавычек на свой)
SYSTEM_INSTRUCTION = (
    "Ты дружелюбный, умный и полезный ИИ-ассистент в Telegram. "
    "Отвечай понятно, по делу и помогай пользователю решать любые задачи."
)

def get_user_chat(user_id: int):
    if user_id not in user_chats:
        user_chats[user_id] = client.aio.chats.create(
            model="gemini-3.8-flash",
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            )
        )
    return user_chats[user_id]

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я твой личный ИИ-помощник на базе Gemini.\n"
        "Задавай любой вопрос — я помню контекст нашей беседы.\n\n"
        "Команда /clear очистит историю диалога."
    )

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_chats.pop(message.from_user.id, None)
    await message.answer("Память очищена! Начинаем с чистого листа.")

@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        await message.answer("Пока я понимаю только текстовые сообщения.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        chat = get_user_chat(message.from_user.id)
        response = await chat.send_message(message.text)
        
        text = response.text or "Не удалось сгенерировать ответ."
        for i in range(0, len(text), 4096):
            await message.answer(text[i:i + 4096])
            
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# Заглушка веб-сервера, чтобы бесплатный хостинг Render не выключал бота
async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
