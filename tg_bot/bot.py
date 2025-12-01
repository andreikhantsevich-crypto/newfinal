import os
import asyncio
from typing import Any, Dict

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv


load_dotenv()


TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
ODOO_API_TOKEN = os.getenv("ODOO_API_TOKEN")
ODOO_BASE_URL = os.getenv("ODOO_BASE_URL", "http://localhost:8069")


if not TG_BOT_TOKEN:
    raise RuntimeError("Не задан TG_BOT_TOKEN в переменных окружения или .env")

if not ODOO_API_TOKEN:
    raise RuntimeError("Не задан ODOO_API_TOKEN в переменных окружения или .env")


bot = Bot(token=TG_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


async def call_odoo(path: str, telegram_user_id: int) -> Dict[str, Any]:
    """
    Вспомогательная функция для запросов в Odoo.

    Отправляет JSON:
    {
        "api_token": ODOO_API_TOKEN,
        "telegram_user_id": telegram_user_id
    }
    """

    # Нормализуем базовый URL (убираем завершающий / если есть)
    base = ODOO_BASE_URL.rstrip("/")
    url = f"{base}{path}"

    payload = {
        "api_token": ODOO_API_TOKEN,
        "telegram_user_id": telegram_user_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            # Odoo JSON endpoints часто возвращают ответ в формате JSON-RPC:
            # {"jsonrpc": "2.0", "id": null, "result": {...}}.
            # Для удобства сразу разворачиваем result.
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return data


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Стартовая команда.
    Сценарий из ТЗ:
    - Клиент заходит в бота
    - Бот по telegram_id ищет клиента в Odoo
    - Если клиент найден -> показываем инфо и доступные команды
    - Если нет -> просим обратиться к менеджеру и передаём его ID
    """
    telegram_id = message.from_user.id

    try:
        data = await call_odoo("/api/tg/balance", telegram_id)
    except Exception as e:  # noqa: BLE001
        await message.answer(
            "Произошла ошибка при соединении с системой. Попробуйте позже.\n"
            f"Техническая информация: {e}"
        )
        return

    if not data.get("success"):
        error = data.get("error")
        if error == "NOT_FOUND":
            await message.answer(
                "Ваш аккаунт ещё не привязан к системе.\n\n"
                "Попросите менеджера создать/открыть вашу карточку клиента в Odoo "
                "и вписать следующий Telegram User ID:\n"
                f"<code>{telegram_id}</code>\n\n"
                "После этого вы сможете пользоваться ботом."
            )
        elif error == "INVALID_TOKEN":
            await message.answer(
                "Бот не авторизован в системе (неверный API токен).\n"
                "Сообщите администратору."
            )
        else:
            await message.answer(
                "Не удалось получить данные из системы. Попробуйте позже.\n"
                f"Техническая информация: {data}"
            )
        return

    name = data.get("name") or "Клиент"
    balance = data.get("balance", 0.0)
    currency = data.get("currency", "")

    await message.answer(
        f"Здравствуйте, <b>{name}</b>!\n\n"
        f"Ваш текущий баланс: <b>{balance} {currency}</b>.\n\n"
        "Доступные команды:\n"
        "/balance — показать баланс\n"
        "/my_trainings — показать ближайшие тренировки\n"
        "/help — справка"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Краткая справка по командам."""
    await message.answer(
        "Доступные команды:\n"
        "/start — проверка привязки аккаунта и приветствие\n"
        "/balance — показать баланс\n"
        "/my_trainings — показать ближайшие тренировки"
    )


@dp.message(Command("balance"))
async def cmd_balance(message: Message) -> None:
    """Показываем баланс клиента, если аккаунт привязан."""
    telegram_id = message.from_user.id

    try:
        data = await call_odoo("/api/tg/balance", telegram_id)
    except Exception as e:  # noqa: BLE001
        await message.answer(
            "Произошла ошибка при соединении с системой. Попробуйте позже.\n"
            f"Техническая информация: {e}"
        )
        return

    if not data.get("success"):
        await message.answer(
            "Не удалось получить ваши данные.\n"
            "Возможно, ваш аккаунт ещё не привязан. Попробуйте /start."
        )
        return

    balance = data.get("balance", 0.0)
    currency = data.get("currency", "")
    await message.answer(f"Ваш текущий баланс: <b>{balance} {currency}</b>.")


@dp.message(Command("my_trainings"))
async def cmd_my_trainings(message: Message) -> None:
    """Показываем предстоящие тренировки клиента, если аккаунт привязан."""
    telegram_id = message.from_user.id

    try:
        data = await call_odoo("/api/tg/trainings", telegram_id)
    except Exception as e:  # noqa: BLE001
        await message.answer(
            "Произошла ошибка при соединении с системой. Попробуйте позже.\n"
            f"Техническая информация: {e}"
        )
        return

    if not data.get("success"):
        await message.answer(
            "Не удалось получить список тренировок.\n"
            "Возможно, ваш аккаунт ещё не привязан. Попробуйте /start."
        )
        return

    trainings = data.get("trainings") or []
    if not trainings:
        await message.answer("У вас нет предстоящих тренировок.")
        return

    lines: list[str] = []
    for t in trainings:
        date = t.get("date", "")
        time_start = t.get("time_start", "")
        time_end = t.get("time_end", "")
        center = t.get("sport_center", "")
        court = t.get("tennis_court", "")
        trainer = t.get("trainer", "")
        training_type = t.get("training_type", "")

        lines.append(
            f"📅 <b>{date}</b> {time_start}–{time_end}\n"
            f"🏟 {center} — {court}\n"
            f"👨‍🏫 Тренер: {trainer}\n"
            f"Тип: {training_type}\n"
        )

    await message.answer("\n".join(lines))


async def main() -> None:
    """Точка входа для запуска бота."""
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())


