import asyncio
import signal
import logging
import json
from datetime import datetime
from aiogram import Bot
import os

logger = logging.getLogger(__name__)

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
            
            # 3. Останавливаем поллинг
            from aiogram.dispatcher.dispatcher import Dispatcher
            dispatcher = Dispatcher.get_current()
            if dispatcher:
                dispatcher.stop_polling()
                
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
        """Проверка здоровья бота (можно вызывать периодически)"""
        try:
            await self.bot.get_me()
            return True
        except Exception as e:
            logger.error(f"Проверка здоровья не пройдена: {e}")
            return False
