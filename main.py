import json
import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.enums import ParseMode

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Токен из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в переменных окружения!")
    raise ValueError("Установите BOT_TOKEN в переменных окружения")

def load_data():
    """Загрузка данных из JSON файла"""
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл data.json не найден!")
        return {}
    except json.JSONDecodeError:
        logger.error("Ошибка в формате data.json!")
        return {}

data = load_data()

# Основная клавиатура для личных чатов
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆘 Экстренно")],
        [KeyboardButton(text="⚡ Электросети"), KeyboardButton(text="🗑️ Коммуналка")],
        [KeyboardButton(text="🏠 Администрация"), KeyboardButton(text="📌 Правила")],
        [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="📞 Все контакты")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите раздел..."
)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ========== ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ ТЕКСТА ==========
def get_emergency_text():
    """Возвращает текст экстренных служб"""
    if not data.get("emergency_phones"):
        return "⚠️ Информация временно недоступна"
    
    text = "<b>🆘 ЭКСТРЕННЫЕ СЛУЖБЫ</b>\n\n"
    
    # Короткие номера
    text += "<b>Короткие номера (работают с мобильных):</b>\n"
    for num, desc in data.get("emergency", {}).items():
        text += f"<code>{num}</code> — {desc}\n"
    
    text += "\n<b>Подробные контакты:</b>\n"
    
    # Детализированные контакты
    for service in data.get("emergency_phones", []):
        text += f"\n<b>{service['service']}:</b>\n"
        for phone in service['phones']:
            text += f"• {phone}\n"
    
    text += "\n<i>📢 Сохраните эти номера! В экстренной ситуации звоните сразу.</i>"
    return text

def get_electricity_text():
    """Возвращает текст по электричеству"""
    if not data.get("electricity"):
        return "⚠️ Информация временно недоступна"
    
    text = "<b>⚡ ЭЛЕКТРОСНАБЖЕНИЕ</b>\n\n"
    text += "<i>Контакты энергетических компаний:</i>\n\n"
    
    for i, company in enumerate(data.get("electricity", []), 1):
        text += f"<b>{i}. {company['company']}</b>\n"
        text += f"   <i>{company['description']}</i>\n"
        text += f"   📞 {company['phone']}\n"
        
        if company.get('type'):
            text += f"   🏷️ Тип: {company['type']}\n"
        
        text += "\n"
    
    text += "<i>Для отключений света сначала звоните в центр обслуживания клиентов (8-800-220-02-20)</i>"
    return text

def get_utilities_text():
    """Возвращает текст по коммуналке"""
    if not data.get("utilities"):
        return "⚠️ Информация временно недоступна"
    
    text = "<b>🗑️ КОММУНАЛЬНЫЕ УСЛУГИ</b>\n\n"
    
    # Вывоз мусора
    garbage = data.get("utilities", {}).get("garbage", {})
    if garbage:
        text += f"<b>Вывоз мусора (ТКО):</b>\n"
        text += f"🏢 <b>{garbage['company']}</b>\n"
        text += f"📝 {garbage['service']}\n"
        text += f"📞 {garbage['phone']}\n"
        
        if garbage.get('hours'):
            text += f"⏰ {garbage['hours']}\n"
    
    # Вода (если есть)
    water_info = data.get("water", {})
    if water_info.get("dispatcher"):
        text += "\n<b>💧 Водоснабжение:</b>\n"
        text += f"📞 Диспетчер: {water_info['dispatcher']}\n"
    
    if water_info.get("note"):
        text += f"\n<i>{water_info['note']}</i>"
    
    return text

def get_admin_text():
    """Возвращает текст администрации"""
    if not data.get("administration"):
        return "⚠️ Информация временно недоступна"
    
    a = data["administration"]
    text = (
        f"<b>🏠 АДМИНИСТРАЦИЯ ДЕРЕВНИ</b>\n\n"
        f"<b>Должность:</b> {a.get('position', 'Староста')}\n"
        f"<b>Контактное лицо:</b> {a.get('name', 'уточняется')}\n"
    )
    
    if a.get('phone') and a['phone'] != "уточняется":
        text += f"<b>Телефон:</b> {a['phone']}\n"
    
    if a.get('hours'):
        text += f"<b>Часы приёма:</b> {a['hours']}\n"
    
    if a.get('email'):
        text += f"<b>Email:</b> {a['email']}\n"
    
    if a.get('note'):
        text += f"\n<i>{a['note']}</i>"
    
    return text

def get_rules_text():
    """Возвращает текст правил"""
    if not data.get("rules"):
        return "⚠️ Информация временно недоступна"
    
    rules_text = "\n".join(data["rules"])
    return rules_text

def get_all_contacts_text():
    """Возвращает текст всех контактов"""
    text = "<b>📞 ПОЛНЫЙ СПИСОК КОНТАКТОВ</b>\n\n"
    
    # Экстренные службы
    text += "<b>🆘 Экстренные службы:</b>\n"
    for service in data.get("emergency_phones", []):
        text += f"\n<b>{service['service']}</b>\n"
        for phone in service['phones']:
            text += f"• {phone}\n"
    
    # Электричество
    text += "\n<b>⚡ Электроснабжение:</b>\n"
    for company in data.get("electricity", []):
        text += f"\n• <b>{company['company']}</b>\n"
        text += f"  {company['phone']}\n"
    
    # Коммуналка
    text += "\n<b>🗑️ Коммунальные услуги:</b>\n"
    garbage = data.get("utilities", {}).get("garbage", {})
    if garbage:
        text += f"\n• <b>{garbage['company']}</b>\n"
        text += f"  {garbage['phone']} - {garbage['service']}\n"
    
    text += "\n<i>💡 Для быстрого доступа используйте соответствующие разделы меню</i>"
    return text

def get_help_text():
    """Возвращает текст помощи"""
    help_text = (
        "<b>ℹ️ Помощь по боту:</b>\n\n"
        "• <b>🆘 Экстренно</b> — все экстренные службы с номерами\n"
        "• <b>⚡ Электросети</b> — электроснабжение (3 организации)\n"
        "• <b>🗑️ Коммуналка</b> — вывоз мусора и коммунальные услуги\n"
        "• <b>🏠 Администрация</b> — контакты старосты\n"
        "• <b>📌 Правила</b> — правила сообщества\n"
        "• <b>📞 Все контакты</b> — полный список телефонов\n\n"
        "<i>Для срочных вызовов используйте короткие номера:</i>\n"
        "<code>101</code> — пожарные\n"
        "<code>102</code> — полиция\n"
        "<code>103</code> — скорая\n"
        "<code>112</code> — ЕДДС (любая экстренная ситуация)"
    )
    return help_text

# ========== КЛАВИАТУРЫ ==========
def get_inline_menu_group():
    """Inline-клавиатура для групп с приватными ответами"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆘 Экстренно", callback_data="private_emergency"),
                InlineKeyboardButton(text="⚡ Электричество", callback_data="private_electricity")
            ],
            [
                InlineKeyboardButton(text="🗑️ Мусор", callback_data="private_garbage"),
                InlineKeyboardButton(text="📞 Контакты", callback_data="private_contacts")
            ],
            [
                InlineKeyboardButton(text="📌 Правила", callback_data="private_rules"),
                InlineKeyboardButton(text="🏠 Администрация", callback_data="private_admin")
            ],
            [
                InlineKeyboardButton(text="❓ Помощь", callback_data="private_help"),
                InlineKeyboardButton(text="💬 Написать в личку", url="https://t.me/vechernitsy_bot")
            ]
        ]
    )

# ========== ОБРАБОТЧИКИ ==========
@dp.message(CommandStart())
async def smart_start(message: types.Message):
    """Умный старт с определением типа чата"""
    if message.chat.type == "private":
        # Личный чат - используем ReplyKeyboard
        welcome_text = (
            "👋 <b>Добро пожаловать в помощник деревни Вечерницы!</b>\n\n"
            "Я здесь, чтобы помочь с важными контактами и информацией.\n"
            "<i>Используйте меню ниже для быстрого доступа к нужным службам</i>"
        )
        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"Новый пользователь в личке: {message.from_user.full_name}")
        
        # Отправляем инструкцию для работы в группе
        group_help = (
            "\n\n📌 <b>Как работать в группе:</b>\n"
            "1. Добавьте меня в группу\n"
            "2. Напишите /start\n"
            "3. Нажимайте кнопки - ответы будут приходить сюда, в личку!"
        )
        await message.answer(group_help, parse_mode=ParseMode.HTML)
    else:
        # Группа - используем InlineKeyboard
        welcome_text = (
            "👋 <b>Помощник деревни Вечерницы</b>\n\n"
            "Нажмите кнопку ниже - информация придет в ваши <b>личные сообщения</b>!\n"
            "<i>Если не получается, сначала напишите боту в личку</i>"
        )
        await message.answer(welcome_text, reply_markup=get_inline_menu_group())

# ========== ОБРАБОТЧИКИ КНОПОК В ЛИЧКЕ ==========
@dp.message(lambda m: m.text == "🆘 Экстренно")
async def emergency_handler(message: types.Message):
    """Экстренные службы в личке"""
    await message.answer(get_emergency_text(), parse_mode=ParseMode.HTML)

@dp.message(lambda m: m.text == "⚡ Электросети")
async def electricity_handler(message: types.Message):
    """Электричество в личке"""
    await message.answer(get_electricity_text(), parse_mode=ParseMode.HTML)

@dp.message(lambda m: m.text == "🗑️ Коммуналка")
async def utilities_handler(message: types.Message):
    """Коммуналка в личке"""
    await message.answer(get_utilities_text(), parse_mode=ParseMode.HTML)

@dp.message(lambda m: m.text == "🏠 Администрация")
async def admin_handler(message: types.Message):
    """Администрация в личке"""
    await message.answer(get_admin_text(), parse_mode=ParseMode.HTML)

@dp.message(lambda m: m.text == "📌 Правила")
async def rules_handler(message: types.Message):
    """Правила в личке"""
    await message.answer(get_rules_text(), parse_mode=ParseMode.HTML)

@dp.message(lambda m: m.text == "📞 Все контакты")
async def all_contacts_handler(message: types.Message):
    """Все контакты в личке"""
    await message.answer(get_all_contacts_text(), parse_mode=ParseMode.HTML)

@dp.message(Command("help"))
@dp.message(lambda m: m.text == "❓ Помощь")
async def help_command(message: types.Message):
    """Помощь в личке"""
    await message.answer(get_help_text(), parse_mode=ParseMode.HTML)

# ========== ОБРАБОТЧИКИ PRIVATE КНОПОК (ДЛЯ ГРУПП) ==========
@dp.callback_query(F.data.startswith("private_"))
async def handle_private_buttons(callback: types.CallbackQuery):
    """Обработка кнопок в группах - отправка в личные сообщения"""
    command = callback.data.replace("private_", "")
    
    # Словарь соответствий команд функциям
    command_functions = {
        "emergency": get_emergency_text,
        "electricity": get_electricity_text,
        "garbage": get_utilities_text,
        "contacts": get_all_contacts_text,
        "rules": get_rules_text,
        "admin": get_admin_text,
        "help": get_help_text,
    }
    
    if command in command_functions:
        try:
            # Пытаемся отправить в личные сообщения пользователя
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=command_functions[command](),
                parse_mode=ParseMode.HTML
            )
            
            # Подтверждаем успешную отправку
            await callback.answer(
                "✅ Информация отправлена в ваши личные сообщения!",
                show_alert=True
            )
            
            logger.info(f"Приватный ответ отправлен пользователю {callback.from_user.full_name} (ID: {callback.from_user.id})")
            
        except Exception as e:
            # Если не удалось отправить (пользователь не начинал диалог)
            logger.warning(f"Не удалось отправить приватный ответ: {e}")
            
            await callback.answer(
                "⚠️ Чтобы получать информацию приватно, сначала напишите мне в личку!\n\n"
                "1. Перейдите в @vechernitsy_bot\n"
                "2. Нажмите START\n"
                "3. Вернитесь в группу и попробуйте снова",
                show_alert=True
            )
    else:
        await callback.answer("❌ Команда не найдена", show_alert=False)

# ========== ОБРАБОТЧИК КОМАНДЫ /register ==========
@dp.message(Command("register"))
async def register_command(message: types.Message):
    """Регистрация для получения приватных ответов"""
    if message.chat.type == "private":
        await message.answer(
            "✅ Вы успешно зарегистрированы!\n\n"
            "Теперь вы можете:\n"
            "• Получать приватные ответы в группе\n"
            "• Использовать кнопочное меню\n"
            "• Быстро получать все контакты\n\n"
            "<i>Вернитесь в группу и нажмите любую кнопку бота</i>",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Пользователь зарегистрирован: {message.from_user.full_name}")
    else:
        # Показываем инструкцию в группе
        instruction = (
            "📝 <b>Как получить приватные ответы:</b>\n\n"
            "1. Напишите мне в личку: @vechernitsy_bot\n"
            "2. Нажмите START\n"
            "3. Вернитесь в эту группу\n"
            "4. Нажмите любую кнопку бота\n\n"
            "<i>Ответы будут приходить в ваши личные сообщения</i>"
        )
        await message.answer(instruction, parse_mode=ParseMode.HTML)

# ========== ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ ==========
@dp.message()
async def unknown_message(message: types.Message):
    """Обработка неизвестных сообщений"""
    if message.chat.type == "private":
        await message.answer(
            "Используйте меню ниже для доступа к информации 😊\n"
            "Или команду /help для справки",
            reply_markup=keyboard
        )
    else:
        # В группе игнорируем или можно предложить меню
        if message.text and ("бот" in message.text.lower() or "вечерницы" in message.text.lower()):
            await message.answer(
                "👋 Напишите /start чтобы открыть меню помощника!\n"
                "<i>Все ответы приходят в личные сообщения</i>",
                parse_mode=ParseMode.HTML
            )

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========
async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота с приватными ответами...")
    
    try:
        # Проверка подключения
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")
        
        # Запуск поллинга
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())