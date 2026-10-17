import asyncio
import logging
import sqlite3
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = "8692224611:AAE3_C-TmfYHynw-g3v09kV2yg28sZNGD_c"

GAMES = {
    "Genshin Impact": "e202102251931481",
    "Honkai: Star Rail": "e202303301540311",
    "Zenless Zone Zero": "e202406031448091"
}

def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            ltuid TEXT NOT NULL,
            ltoken TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_user_tokens(user_id: int, ltuid: str, ltoken: str):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, ltuid, ltoken)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET ltuid=excluded.ltuid, ltoken=excluded.ltoken
    """, (user_id, ltuid, ltoken))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, ltuid, ltoken FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows

async def perform_checkin(ltuid: str, ltoken: str) -> str:
    headers = {
        "Cookie": f"ltuid_v2={ltuid}; ltoken_v2={ltoken};",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://act.hoyolab.com/",
        "Origin": "https://act.hoyolab.com"
    }

    results = []
    async with httpx.AsyncClient() as client:
        for game_name, act_id in GAMES.items():
            url = "https://sg-public-api.hoyolab.com/event/luna/os/sign"
            payload = {"act_id": act_id}
            try:
                response = await client.post(url, json=payload, headers=headers)
                data = response.json()
                retcode = data.get("retcode")
                msg = data.get("message", "")

                if retcode == 0:
                    results.append(f"✅ {game_name}: Успешно отмечено!")
                elif retcode == -5003:
                    results.append(f"ℹ️ {game_name}: Уже отмечено сегодня.")
                else:
                    results.append(f"❌ {game_name}: Ошибка ({retcode}) - {msg}")
            except Exception as e:
                results.append(f"⚠️ {game_name}: Ошибка сети ({e})")

    return "\n".join(results)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для авто-отметок в HoYoLAB.\n\n"
        "Отправь свои куки командой:\n"
        "/setcookie <ltuid_v2> <ltoken_v2>\n\n"
        "Проверить отметку: /checkin",
        parse_mode="Markdown"
    )

@dp.message(Command("setcookie"))
async def cmd_setcookie(message: types.Message):
    args = message.text.split()[1:]
    if len(args) != 2:
        await message.answer("Ошибка! Формат: /setcookie <ltuid_v2> <ltoken_v2>", parse_mode="Markdown")
        return

    ltuid, ltoken = args[0], args[1]
    save_user_tokens(message.from_user.id, ltuid, ltoken)
    await message.answer("✅ Ваши токены сохранены! Бот будет автоматически отмечаться каждый день в 00:05.")

@dp.message(Command("checkin"))
async def cmd_checkin(message: types.Message):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ltuid, ltoken FROM users WHERE user_id = ?", (message.from_user.id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await message.answer("Сначала сохраните куки через /setcookie <ltuid_v2> <ltoken_v2>.", parse_mode="Markdown")
        return

    await message.answer("⏳ Выполняю отметку...")
    res = await perform_checkin(row[0], row[1])
    await message.answer(res)

async def daily_auto_checkin():
    users = get_all_users()
    for user_id, ltuid, ltoken in users:
        res = await perform_checkin(ltuid, ltoken)
        try:
            await bot.send_message(user_id, f"📅 Ежедневная отметка:\n\n{res}", parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение {user_id}: {e}")

async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_auto_checkin, "cron", hour=0, minute=5)
    scheduler.start()

    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())