import logging
import asyncio
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================= НАСТРОЙКИ =================
BOT_TOKEN = '9078968710:AAHhHvRy5nrASMCi0D11g4bc7QJtyqKCrBQ'
ADMIN_ID = 8738748123  # Твой ID в Телеграме (куда будут приходить уведомления)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1gc1ul4aCTc35EXGxml9oX05DHfRwqnVVsefxucLgv4M/edit?gid=0#gid=0"
# ============================================

# Настройка логов (чтобы видеть ошибки, если что-то упадет)
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Подключение к Google Таблицам
try:
    # Мы берем ключ из переменной окружения (на хостинге ты ее вставишь)
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise ValueError("Переменная GOOGLE_CREDENTIALS не найдена!")
        
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Открываем таблицу по ссылке
    sheet = client.open_by_url(SPREADSHEET_URL).sheet1
    print("✅ Успешное подключение к Google Таблицам!")
except Exception as e:
    print(f"❌ Ошибка подключения к Google: {e}")
    sheet = None

# Машина состояний (для пошагового заполнения)
class Form(StatesGroup):
    name = State()
    phone = State()
    comment = State()

# Клавиатура
start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📝 Оставить заявку")]],
    resize_keyboard=True
)

# ================= ХЕНДЛЕРЫ =================

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот для сбора заявок. Нажми на кнопку ниже, чтобы оставить заявку, и я свяжусь с тобой.",
        reply_markup=start_kb
    )

@dp.message(F.text == "📝 Оставить заявку")
async def start_form(message: types.Message, state: FSMContext):
    await state.set_state(Form.name)
    await message.answer("Как тебя зовут? (Напиши своё имя)", reply_markup=ReplyKeyboardRemove())

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.phone)
    await message.answer("Отлично! Теперь напиши свой номер телефона (или юзернейм в TG для связи).")

@dp.message(Form.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(Form.comment)
    await message.answer("И последнее: напиши свой вопрос или комментарий.")

@dp.message(Form.comment)
async def process_comment(message: types.Message, state: FSMContext):
    await state.update_data(comment=message.text)
    user_data = await state.get_data()
    
    # 1. Сохраняем в Google Таблицу
    if sheet:
        try:
            sheet.append_row([
                user_data['name'], 
                user_data['phone'], 
                user_data['comment'], 
                str(message.from_user.id), 
                message.from_user.username
            ])
            print("✅ Заявка добавлена в таблицу")
        except Exception as e:
            print(f"❌ Ошибка записи в Google: {e}")

    # 2. Отправляем уведомление админу (тебе)
    admin_text = (
        f"🔥 <b>НОВАЯ ЗАЯВКА!</b>\n\n"
        f"👤 Имя: {user_data['name']}\n"
        f"📞 Телефон: {user_data['phone']}\n"
        f"💬 Комментарий: {user_data['comment']}\n"
        f"🔗 Юзер: @{message.from_user.username} (ID: {message.from_user.id})"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        print(f"❌ Ошибка отправки админу: {e}")

    # 3. Благодарим клиента
    await message.answer(
        "✅ Спасибо! Твоя заявка принята. Я свяжусь с тобой в ближайшее время.",
        reply_markup=start_kb
    )
    await state.clear()

# Запуск
async def main():
    print("🚀 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
