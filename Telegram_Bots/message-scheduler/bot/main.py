import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from database import db
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверьте .env файл.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

class MessageForm(StatesGroup):
    text = State()
    image = State()

class ScheduleForm(StatesGroup):
    choose_message = State()
    choose_chat = State()
    choose_time = State()


def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✉️ Добавить сообщение"), KeyboardButton(text="📅 Запланировать отправку")],
            [KeyboardButton(text="📋 Мои сообщения"), KeyboardButton(text="👥 Список чатов")],
        ],
        resize_keyboard=True
    )
    return keyboard


def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


async def send_message_to_chat(chat_id: int, message_data: dict):
    """Отправляет сообщение в указанный чат"""
    try:
        if message_data['image_path'] and os.path.exists(message_data['image_path']):
            with open(message_data['image_path'], 'rb') as photo:
                await bot.send_photo(chat_id=chat_id, photo=photo, caption=message_data['text'])
        else:
            await bot.send_message(chat_id=chat_id, text=message_data['text'])
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки в чат {chat_id}: {e}")
        return False


def parse_time_input(time_str: str):
    """Парсит ввод времени пользователя"""
    try:
        # Пробуем разные форматы времени
        if re.match(r'^\d{1,2}:\d{2}$', time_str):
            # Формат "HH:MM"
            hours, minutes = map(int, time_str.split(':'))
            send_time = datetime.now().replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if send_time < datetime.now():
                send_time += timedelta(days=1)
            return send_time
        
        elif re.match(r'^\d+[mh]$', time_str.lower()):
            # Формат "15m" или "2h"
            value = int(time_str[:-1])
            unit = time_str[-1].lower()
            
            if unit == 'm':
                return datetime.now() + timedelta(minutes=value)
            elif unit == 'h':
                return datetime.now() + timedelta(hours=value)
        
        # Пробуем распарсить как полную дату
        try:
            return datetime.fromisoformat(time_str.replace(' ', 'T'))
        except:
            pass
            
    except ValueError:
        pass
    
    return None


async def check_scheduled_messages():
    """Проверяет и отправляет запланированные сообщения"""
    try:
        pending_messages = await db.get_pending_messages()
        
        for message in pending_messages:
            success = await send_message_to_chat(message['chat_id'], {
                'text': message['text'],
                'image_path': message['image_path']
            })
            
            if success:
                await db.mark_as_sent(message['id'])
                logger.info(f"Отправлено запланированное сообщение в {message['chat_title']}")
    
    except Exception as e:
        logger.error(f"Ошибка в задаче проверки расписания: {e}")


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этому боту.")
        return
    await message.answer("👨‍💻 Админ-панель бота для управления рассылкой", reply_markup=get_main_keyboard())

@dp.message(F.text == "✉️ Добавить сообщение")
async def add_message_command(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Введите текст сообщения:", reply_markup=get_cancel_keyboard())
    await state.set_state(MessageForm.text)

@dp.message(F.text == "❌ Отмена")
async def cancel_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_keyboard())

@dp.message(MessageForm.text)
async def process_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_command(message, state)
        return
        
    await state.update_data(text=message.text)
    await message.answer("Теперь отправьте изображение (если нужно), или нажмите /skip")
    await state.set_state(MessageForm.image)

@dp.message(Command("skip"), MessageForm.image)
async def skip_image(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    message_id = await db.add_message(user_data['text'])
    await message.answer(f"✅ Сообщение #{message_id} добавлено!", reply_markup=get_main_keyboard())
    await state.clear()

@dp.message(F.photo, MessageForm.image)
async def process_image(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    # Скачиваем изображение
    image_dir = "images"
    os.makedirs(image_dir, exist_ok=True)
    image_path = f"{image_dir}/{message.photo[-1].file_id}.jpg"
    await bot.download(message.photo[-1], destination=image_path)
    
    message_id = await db.add_message(user_data['text'], image_path)
    await message.answer(f"✅ Сообщение #{message_id} с изображением добавлено!", reply_markup=get_main_keyboard())
    await state.clear()

@dp.message(F.text == "📋 Мои сообщения")
async def show_messages(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    messages = await db.get_all_messages()
    if not messages:
        await message.answer("📭 У вас пока нет сохраненных сообщений.")
        return
    
    text = "📋 Ваши сообщения:\n\n"
    for msg in messages:
        text += f"#{msg['id']} - {msg['text'][:50]}...\n"
        text += f"Создано: {msg['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await message.answer(text)

@dp.message(F.text == "👥 Список чатов")
async def show_chats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    chats = await db.get_all_chats()
    if not chats:
        await message.answer("👥 Бот еще не добавлен ни в один чат.")
        return
    
    text = "👥 Чаты для рассылки:\n\n"
    for chat in chats:
        text += f"• {chat['title']} (ID: {chat['chat_id']})\n"
    
    await message.answer(text)

@dp.message(F.text == "📅 Запланировать отправку")
async def start_scheduling(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    messages = await db.get_all_messages()
    if not messages:
        await message.answer("❌ Сначала добавьте хотя бы одно сообщение.")
        return
    
    chats = await db.get_all_chats()
    if not chats:
        await message.answer("❌ Бот не добавлен ни в один чат.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for msg in messages:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"#{msg['id']}: {msg['text'][:30]}...",
                callback_data=f"choose_msg:{msg['id']}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])
    
    await message.answer("📝 Выберите сообщение для отправки:", reply_markup=keyboard)
    await state.set_state(ScheduleForm.choose_message)

@dp.callback_query(F.data.startswith("choose_msg:"), ScheduleForm.choose_message)
async def choose_message_callback(callback: types.CallbackQuery, state: FSMContext):
    message_id = int(callback.data.split(":")[1])
    await state.update_data(message_id=message_id)
    
    chats = await db.get_all_chats()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for chat in chats:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=chat['title'],
                callback_data=f"choose_chat:{chat['chat_id']}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])
    
    await callback.message.edit_text("👥 Выберите чат для отправки:", reply_markup=keyboard)
    await state.set_state(ScheduleForm.choose_chat)
    await callback.answer()

@dp.callback_query(F.data.startswith("choose_chat:"), ScheduleForm.choose_chat)
async def choose_chat_callback(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    
    await callback.message.edit_text(
        "⏰ Введите время отправки:\n\n"
        "Примеры:\n"
        "• 15:30 - сегодня в 15:30 (если время прошло, то завтра)\n"
        "• 30m - через 30 минут\n"
        "• 2h - через 2 часа\n"
        "• 2024-01-15 18:00 - конкретная дата и время",
        reply_markup=None
    )
    await state.set_state(ScheduleForm.choose_time)
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()

@dp.message(ScheduleForm.choose_time)
async def process_time_input(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_command(message, state)
        return
    
    send_time = parse_time_input(message.text)
    if not send_time:
        await message.answer("❌ Неверный формат времени. Попробуйте еще раз:")
        return
    
    user_data = await state.get_data()
    message_data = await db.get_message_by_id(user_data['message_id'])
    chats = await db.get_all_chats()
    chat_title = next((chat['title'] for chat in chats if chat['chat_id'] == user_data['chat_id']), "Неизвестный чат")
    
    schedule_id = await db.add_scheduled_message(
        user_data['message_id'],
        user_data['chat_id'],
        send_time
    )
    
    scheduler.add_job(
        send_message_to_chat,
        trigger=DateTrigger(run_date=send_time),
        args=[user_data['chat_id'], message_data],
        id=f"msg_{schedule_id}"
    )
    
    await message.answer(
        f"✅ Сообщение запланировано!\n\n"
        f"📝 Сообщение: #{user_data['message_id']}\n"
        f"👥 Чат: {chat_title}\n"
        f"⏰ Время: {send_time.strftime('%d.%m.%Y %H:%M')}",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


@dp.message(F.chat.type.in_({"group", "supergroup"}), F.new_chat_members)
async def on_bot_added_to_chat(message: types.Message):
    for user in message.new_chat_members:
        if user.id == (await bot.get_me()).id:
            chat_id = message.chat.id
            title = message.chat.title
            await db.add_chat(chat_id, title)
            await message.answer(f"✅ Чат '{title}' добавлен для рассылки!")
            logger.info(f"Бот добавлен в чат: {title} ({chat_id})")


async def on_startup():
    await db.create_pool()
    logger.info("Database pool created")

    scheduler.add_job(
        check_scheduled_messages,
        'interval',
        minutes=1,
        next_run_time=datetime.now() + timedelta(seconds=10)
    )
    scheduler.start()
    logger.info("Планировщик запущен")

async def on_shutdown():
    if db.pool:
        await db.pool.close()
    await bot.session.close()


async def main():
    await on_startup()
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())