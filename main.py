import json
import os
import asyncio
import logging
import sys
import signal
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
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

# ========== RESTART HANDLER (встроенный) ==========
class RestartHandler:
    def __init__(self, bot: Bot, config_file="bot_state.json"):
        self.bot = bot
        self.config_file = config_file
        self.shutting_down = False
        
    async def save_bot_state(self):
        """Сохраняет состояние бота перед остановкой"""
        try:
            state = {
                "last_update": datetime.now().isoformat(),
                "restart_count": self.load_state().get("restart_count", 0) + 1,
                "shutdown_reason": "graceful" if not self.shutting_down else "interrupted"
            }
            
            with open(self.config_file, "w") as f:
                json.dump(state, f, indent=2)
                
            logger.info(f"Состояние бота сохранено: {state}")
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}")
    
    def load_state(self):
        """Загружает состояние бота"""
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"restart_count": 0, "last_update": None}
    
    async def graceful_shutdown(self, signal_received=None):
        """Корректная остановка бота"""
        if self.shutting_down:
            return
            
        self.shutting_down = True
        logger.info(f"Получен сигнал {signal_received}. Начинаю graceful shutdown...")
        
        try:
            # 1. Уведомляем админа (если есть)
            admin_id = os.getenv("ADMIN_ID")
            if admin_id:
                try:
                    await self.bot.send_message(
                        admin_id,
                        f"🔴 Бот останавливается...\n"
                        f"Причина: {signal_received or 'manual shutdown'}\n"
                        f"Время: {datetime.now().strftime('%H:%M:%S')}"
                    )
                except:
                    pass
            
            # 2. Сохраняем состояние
            await self.save_bot_state()
            
            logger.info("Graceful shutdown завершен")
            
        except Exception as e:
            logger.error(f"Ошибка при graceful shutdown: {e}")
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        # Для Unix систем
        try:
            loop = asyncio.get_running_loop()
            
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self.graceful_shutdown(s.name))
                )
                
            logger.info("Обработчики сигналов установлены")
        except (ImportError, NotImplementedError):
            # Для Windows или других систем
            logger.warning("Сигналы не поддерживаются в этой системе")
    
    async def check_health(self):
        """Проверка здоровья бота"""
        try:
            await self.bot.get_me()
            return True
        except Exception as e:
            logger.error(f"Проверка здоровья не пройдена: {e}")
            return False

# ========== ОБРАБОТЧИК НЕОБРАБОТАННЫХ ИСКЛЮЧЕНИЙ ==========
def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    """Глобальный обработчик непойманных исключений"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
        
    logger.critical("Необработанное исключение:", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Попытка уведомить админа
    try:
        admin_id = os.getenv("ADMIN_ID")
        if admin_id and "BOT_TOKEN" in os.environ:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            bot_temp = Bot(token=os.getenv("BOT_TOKEN"))
            loop.run_until_complete(
                bot_temp.send_message(
                    admin_id,
                    f"💥 Критическая ошибка бота:\n{exc_type.__name__}: {exc_value}"
                )
            )
            loop.run_until_complete(bot_temp.session.close())
    except:
        pass

sys.excepthook = handle_unhandled_exception

# ========== ОСНОВНОЙ КОД БОТА ==========

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
    """Возвращает текст по вывозу ТКО"""
    if not data.get("utilities"):
        return "⚠️ Информация временно недоступна"
    
    text = "<b>🗑️ ВЫВОЗ ТКО (ТВЕРДЫХ КОММУНАЛЬНЫХ ОТХОДОВ)</b>\n\n"
    
    # Вывоз мусора
    garbage = data.get("utilities", {}).get("garbage", {})
    if garbage:
        text += f"<b>Компания по вывозу ТКО:</b>\n"
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
    
    # График вывоза ТКО
    text += "\n\n<b>📅 График вывоза ТКО:</b>\n"
    text += "🔗 https://lb.rosttech.online/for-clients/tech-zones/8/Levoberezhnaya\n\n"
    text += "<i>💡 Перейдите по ссылке для просмотра актуального графика вывоза отходов</i>"
    
    return text

def get_admin_text():
    """Возвращает текст главы муниципального образования"""
    text = (
        "<b>🏛️ ГЛАВА МУНИЦИПАЛЬНОГО ОБРАЗОВАНИЯ</b>\n\n"
        "<b>Экель Виктор Юрьевич</b>\n"
        "Глава Никольского сельсовета\n\n"
        "<b>Телефон:</b> +7 (39133) 28-0-19\n\n"
        "<b>Адрес:</b>\n"
        "663024, Красноярский Край, Емельяновский район,\n"
        "с. Никольское, ул. Советская 75а\n\n"
        "<b>Email:</b> s-sovet@mail.ru\n\n"
        "<b>Сайт:</b> https://nikolskij-r04.gosweb.gosuslugi.ru"
    )
    return text

def get_bus_schedule_text():
    """Возвращает текст расписания автобуса"""
    text = (
        "<b>🚌 РАСПИСАНИЕ АВТОБУСА</b>\n\n"
        "<b>Емельяново - Вечерницы</b>\n\n"
        "📅 Актуальное расписание можно посмотреть на сайте:\n"
        "🔗 https://krasavtovokzal.ru/raspisanie/kya/emelyanovo/kya/vechernicy\n\n"
        "<i>💡 Перейдите по ссылке для просмотра актуального расписания и тарифов</i>"
    )
    return text

def get_clinic_text():
    """Возвращает текст амбулатории"""
    text = (
        "<b>🏥 НИКОЛЬСКАЯ ВРАЧЕБНАЯ АМБУЛАТОРИЯ</b>\n\n"
        "<b>Контакты отделения:</b>\n\n"
        "<b>Адрес отделения:</b>\n"
        "Емельяновский район, с. Никольское, ул. Советская, 75 «А»\n\n"
        "<b>Телефон отделения:</b>\n"
        "8 (391) 205‒25‒03 доб. 210\n\n"
        "<b>Сайт:</b>\n"
        "🔗 https://emelrb.gosuslugi.ru/informatsiya-dlya-patsientov/otdeleniya/nikolskaya-vrachebnaya-ambulatoriya.html\n\n"
        "<i>💡 Перейдите по ссылке для получения дополнительной информации о работе амбулатории</i>"
    )
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
    
    # Вывоз ТКО
    text += "\n<b>🗑️ Вывоз ТКО:</b>\n"
    garbage = data.get("utilities", {}).get("garbage", {})
    if garbage:
        text += f"\n• <b>{garbage['company']}</b>\n"
        text += f"  {garbage['phone']} - {garbage['service']}\n"
    
    # График вывоза ТКО
    text += "\n• <b>График вывоза ТКО:</b>\n"
    text += "  https://lb.rosttech.online/for-clients/tech-zones/8/Levoberezhnaya\n"
    
    # Глава муниципального образования
    text += "\n<b>🏛️ Глава муниципального образования:</b>\n"
    text += "\n• <b>Экель Виктор Юрьевич</b>\n"
    text += "  +7 (39133) 28-0-19\n"
    
    # Амбулатория
    text += "\n<b>🏥 Никольская врачебная амбулатория:</b>\n"
    text += "\n• <b>Адрес:</b> с. Никольское, ул. Советская, 75 «А»\n"
    text += "• <b>Телефон:</b> 8 (391) 205‒25‒03 доб. 210\n"
    text += "• <b>Сайт:</b> https://emelrb.gosuslugi.ru/informatsiya-dlya-patsientov/otdeleniya/nikolskaya-vrachebnaya-ambulatoriya.html\n"
    
    # Расписание автобуса
    text += "\n<b>🚌 Расписание автобуса:</b>\n"
    text += "\n• <b>Емельяново - Вечерницы</b>\n"
    text += "  https://krasavtovokzal.ru/raspisanie/kya/emelyanovo/kya/vechernicy\n"
    
    text += "\n<i>💡 Для быстрого доступа используйте соответствующие разделы меню</i>"
    return text

def get_help_text():
    """Возвращает текст помощи"""
    help_text = (
        "<b>ℹ️ Помощь по боту:</b>\n\n"
        "• <b>🆘 Экстренно</b> — все экстренные службы с номерами\n"
        "• <b>⚡ Электросети</b> — электроснабжение (3 организации)\n"
        "• <b>🗑️ Вывоз ТКО</b> — твердые коммунальные отходы\n"
        "• <b>🏛️ Администрация</b> — глава муниципального образования\n"
        "• <b>🏥 Амбулатория</b> — Никольская врачебная амбулатория\n"
        "• <b>🚌 Расписание автобуса</b> — маршрут Емельяново - Вечерницы\n"
        "• <b>📌 Правила</b> — правила сообщества\n"
        "• <b>📞 Все контакты</b> — полный список телефонов\n\n"
        "<i>Для срочных вызовов используйте короткие номера:</i>\n"
        "<code>101</code> — пожарные\n"
        "<code>102</code> — полиция\n"
        "<code>103</code> — скорая\n"
        "<code>112</code> — ЕДДС (любая экстренная ситуация)"
    )
    return help_text

# ========== INLINE КЛАВИАТУРЫ ДЛЯ ВСЕХ ЧАТОВ ==========
def get_main_menu_keyboard():
    """Основная клавиатура меню для всех чатов"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🆘 Экстренно", callback_data="menu_emergency"),
                InlineKeyboardButton(text="⚡ Электричество", callback_data="menu_electricity")
            ],
            [
                InlineKeyboardButton(text="🗑️ Вывоз ТКО", callback_data="menu_garbage"),
                InlineKeyboardButton(text="🏛️ Администрация", callback_data="menu_admin")
            ],
            [
                InlineKeyboardButton(text="🏥 Амбулатория", callback_data="menu_clinic"),
                InlineKeyboardButton(text="🚌 Расписание автобуса", callback_data="menu_bus")
            ],
            [
                InlineKeyboardButton(text="📌 Правила", callback_data="menu_rules"),
                InlineKeyboardButton(text="📞 Все контакты", callback_data="menu_contacts")
            ],
            [
                InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help"),
                InlineKeyboardButton(text="↩️ Свернуть меню", callback_data="menu_close")
            ]
        ]
    )

def get_welcome_keyboard():
    """Приветственная клавиатура для первого сообщения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Открыть меню", callback_data="menu_show"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help")
            ]
        ]
    )

def get_back_to_menu_keyboard():
    """Клавиатура для возврата в меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Вернуться в меню", callback_data="menu_show")
            ]
        ]
    )

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(CommandStart())
async def start_command(message: types.Message):
    """Команда /start - единая для всех чатов"""
    if message.chat.type == "private":
        # В личном чате
        welcome_text = (
            "👋 <b>Добро пожаловать в помощник деревни Вечерницы!</b>\n\n"
            "Я здесь, чтобы помочь с важными контактами и информацией.\n\n"
            "💡 <b>Как пользоваться:</b>\n"
            "1. Нажмите кнопку '📋 Открыть меню' ниже\n"
            "2. Выберите нужный раздел\n"
            "3. Информация придет прямо сюда\n\n"
            "<i>В группе информация будет приходить в ЛИЧНЫЕ СООБЩЕНИЯ</i>"
        )
        await message.answer(welcome_text, reply_markup=get_welcome_keyboard())
        logger.info(f"Новый пользователь в личке: {message.from_user.full_name}")
    else:
        # В группе
        welcome_text = (
            "👋 <b>Помощник деревни Вечерницы</b>\n\n"
            "Я помогу вам получить важные контакты и информацию.\n\n"
            "💡 <b>Как пользоваться:</b>\n"
            "1. Нажмите кнопку '📋 Открыть меню' ниже\n"
            "2. Выберите нужный раздел\n"
            "3. <b>Информация придет в ваши ЛИЧНЫЕ СООБЩЕНИЯ!</b>\n\n"
            "<i>Если не получается, сначала напишите боту в личку: @vechernitsy_bot</i>"
        )
        await message.answer(welcome_text, reply_markup=get_welcome_keyboard())

@dp.message(Command("menu"))
async def menu_command(message: types.Message):
    """Команда /menu - показывает главное меню"""
    menu_text = "📋 <b>Главное меню помощника</b>\n\nВыберите нужный раздел:"
    
    # В личке сразу показываем информацию
    if message.chat.type == "private":
        await message.answer(menu_text, reply_markup=get_main_menu_keyboard())
    else:
        # В группе напоминаем про приватные сообщения
        menu_text += "\n\n<i>📱 Информация будет отправлена в ваши ЛИЧНЫЕ СООБЩЕНИЯ</i>"
        await message.answer(menu_text, reply_markup=get_main_menu_keyboard())

@dp.message(Command("help"))
async def help_command_handler(message: types.Message):
    """Команда /help"""
    await message.answer(get_help_text(), parse_mode=ParseMode.HTML, reply_markup=get_back_to_menu_keyboard())

# ========== ОБРАБОТЧИКИ CALLBACK КНОПОК ==========
@dp.callback_query(F.data == "menu_show")
async def show_menu_handler(callback: CallbackQuery):
    """Показать главное меню"""
    if callback.message.chat.type == "private":
        menu_text = "📋 <b>Главное меню помощника</b>\n\nВыберите нужный раздел:"
    else:
        menu_text = "📋 <b>Главное меню помощника</b>\n\nВыберите нужный раздел:\n\n<i>📱 Информация будет отправлена в ваши ЛИЧНЫЕ СООБЩЕНИЯ</i>"
    
    await callback.message.edit_text(menu_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "menu_close")
async def close_menu_handler(callback: CallbackQuery):
    """Свернуть меню"""
    await callback.message.edit_text("Меню свернуто. Используйте /menu чтобы открыть снова.")
    await callback.answer("Меню свернуто")

@dp.callback_query(F.data.startswith("menu_"))
async def handle_menu_buttons(callback: CallbackQuery):
    """Обработка кнопок меню"""
    command = callback.data.replace("menu_", "")
    
    # Словарь соответствий команд функциям
    command_functions = {
        "emergency": get_emergency_text,
        "electricity": get_electricity_text,
        "garbage": get_utilities_text,
        "contacts": get_all_contacts_text,
        "rules": get_rules_text,
        "admin": get_admin_text,
        "bus": get_bus_schedule_text,
        "clinic": get_clinic_text,
        "help": get_help_text,
    }
    
    if command in command_functions:
        # В личном чате отправляем прямо здесь
        if callback.message.chat.type == "private":
            await callback.message.edit_text(
                command_functions[command](),
                parse_mode=ParseMode.HTML,
                reply_markup=get_back_to_menu_keyboard()
            )
            await callback.answer()
            
        else:
            # В группе отправляем в личные сообщения
            try:
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text=command_functions[command](),
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_back_to_menu_keyboard()
                )
                
                # Подтверждение в группе (видно только нажавшему)
                await callback.answer(
                    "✅ Информация отправлена в ваши личные сообщения!",
                    show_alert=False
                )
                
                logger.info(f"Приватный ответ отправлен пользователю {callback.from_user.full_name}")
                
            except Exception as e:
                logger.warning(f"Не удалось отправить приватный ответ: {e}")
                
                await callback.answer(
                    "⚠️ Чтобы получить информацию, сначала напишите мне в личку!\n\n"
                    "1. Перейдите в @vechernitsy_bot\n"
                    "2. Нажмите START\n"
                    "3. Вернитесь и нажмите кнопку снова",
                    show_alert=True
                )
    else:
        await callback.answer("❌ Команда не найдена", show_alert=False)

# ========== ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ ==========
@dp.message()
async def unknown_message(message: types.Message):
    """Обработка неизвестных сообщений"""
    if message.chat.type == "private":
        # В личке предлагаем меню
        if not message.text.startswith("/"):
            await message.answer(
                "Используйте команду /menu для открытия меню или /help для справки.",
                reply_markup=get_welcome_keyboard()
            )
    else:
        # В группе реагируем только на упоминания
        if message.text and ("бот" in message.text.lower() or "вечерницы" in message.text.lower()):
            await message.answer(
                "👋 Напишите /menu чтобы открыть меню помощника!\n"
                "<i>Вся информация будет отправлена в ваши личные сообщения</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=get_welcome_keyboard()
            )

# ========== ГЛАВНАЯ ФУНКЦИЯ С АВТОРЕСТАРТОМ ==========
async def main():
    """Основная функция запуска бота с авторестартом"""
    logger.info("Запуск бота с системой авторестарта...")
    
    # Инициализация RestartHandler
    restart_handler = RestartHandler(bot)
    state = restart_handler.load_state()
    
    logger.info(f"Состояние бота: перезапуск #{state.get('restart_count', 0)}")
    
    # Уведомление админа о старте
    admin_id = os.getenv("ADMIN_ID")
    if admin_id:
        try:
            await bot.send_message(
                admin_id,
                f"🟢 Бот запущен!\n"
                f"Перезапуск #{state.get('restart_count', 0)}\n"
                f"Последний запуск: {state.get('last_update', 'неизвестно')}"
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа: {e}")
    
    try:
        # Настройка обработчиков сигналов
        restart_handler.setup_signal_handlers()
        
        # Проверка подключения
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")
        
        # Запуск поллинга с обработкой ошибок
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False  # Сами обрабатываем сигналы
        )
        
    except asyncio.CancelledError:
        logger.info("Поллинг отменен")
    except Exception as e:
        logger.error(f"Критическая ошибка в основном цикле: {e}")
        
        # Сохраняем состояние при ошибке
        await restart_handler.save_bot_state()
        
        # Пробуем перезапуститься через 30 секунд
        logger.info("Попытка перезапуска через 30 секунд...")
        await asyncio.sleep(30)
        
        # Рекурсивный перезапуск (максимум 5 раз подряд)
        restart_count = state.get("restart_count", 0)
        if restart_count < 5:
            await main()
        else:
            logger.error("Достигнут лимит перезапусков (5). Требуется ручное вмешательство.")
            if admin_id:
                try:
                    await bot.send_message(
                        admin_id,
                        "🚨 Достигнут лимит перезапусков бота! Требуется ручное вмешательство."
                    )
                except:
                    pass
    finally:
        if not restart_handler.shutting_down:
            await restart_handler.graceful_shutdown("program_exit")
        await bot.session.close()

if __name__ == "__main__":
    # Добавляем переменную окружения ADMIN_ID в .env файл для уведомлений
    # ADMIN_ID=ваш_telegram_id
    asyncio.run(main())