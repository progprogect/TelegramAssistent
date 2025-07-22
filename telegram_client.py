import os
import asyncio
import time
from typing import List, Dict, Any, Optional
from telethon import TelegramClient, types, errors
from telethon.tl.types import User, Chat, Channel
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class TelegramService:
    def __init__(self):
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.session_name = os.getenv('SESSION_NAME', 'telegram_session')
        self.client = None
        
        # Кеширование диалогов
        self._dialogs_cache = None
        self._dialogs_cache_time = 0
        self._cache_ttl = 600  # 10 минут
        
        if not self.api_id or not self.api_hash:
            raise ValueError("API_ID и API_HASH должны быть установлены в переменных окружения")
        
        # Восстанавливаем сессию из base64 если она есть (для облачного развертывания)
        self._restore_session_from_env()
    
    def _restore_session_from_env(self):
        """Восстанавливает файл сессии из переменной окружения SESSION_FILE_BASE64"""
        session_base64 = os.getenv('SESSION_FILE_BASE64')
        session_file_path = f"{self.session_name}.session"
        
        if session_base64 and not os.path.exists(session_file_path):
            try:
                import base64
                import gzip
                
                # Декодируем base64
                compressed_data = base64.b64decode(session_base64)
                
                # Пытаемся распаковать (если данные сжаты)
                try:
                    session_data = gzip.decompress(compressed_data)
                    print("✅ Сессия восстановлена из сжатой переменной окружения")
                except gzip.BadGzipFile:
                    # Если не получилось распаковать, значит данные не сжаты
                    session_data = compressed_data
                    print("✅ Сессия восстановлена из переменной окружения")
                
                # Записываем файл сессии
                with open(session_file_path, 'wb') as f:
                    f.write(session_data)
                    
            except Exception as e:
                print(f"❌ Ошибка восстановления сессии: {e}")
        elif os.path.exists(session_file_path):
            print("ℹ️ Используется существующий файл сессии")
        else:
            print("ℹ️ Файл сессии не найден, потребуется авторизация")
    
    async def start_client(self):
        """Инициализация и подключение клиента Telegram"""
        if self.client is None:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        
        if not self.client.is_connected():
            try:
                # Подключаемся без авторизации (только если сессия уже существует)
                await self.client.connect()
                
                # Проверяем, авторизованы ли мы
                if not await self.client.is_user_authorized():
                    raise ValueError(
                        "Сессия не найдена или недействительна. "
                        "Для первоначальной настройки запустите приложение локально "
                        "и пройдите авторизацию, затем загрузите файл сессии на Railway."
                    )
                
            except Exception as e:
                if "Сессия не найдена" in str(e):
                    raise e
                else:
                    # Если возникла другая ошибка, пытаемся стандартную авторизацию
                    # (это сработает только в локальной среде)
                    try:
                        await self.client.start()
                    except EOFError:
                        raise ValueError(
                            "Невозможно выполнить интерактивную авторизацию в облачной среде. "
                            "Пожалуйста, выполните авторизацию локально и загрузите файл сессии."
                        )
        
        return self.client
    
    async def disconnect_client(self):
        """Отключение клиента"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
    
    async def get_dialogs(self, limit: int = 50, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Получить список диалогов (чатов, каналов, групп) с кешированием
        
        Args:
            limit: Максимальное количество диалогов (по умолчанию 50, максимум 200)
            force_refresh: Принудительно обновить кеш
        """
        start_time = time.time()
        
        # Ограничиваем лимит
        limit = min(max(limit, 1), 200)
        
        # Проверяем кеш
        current_time = time.time()
        if (not force_refresh and 
            self._dialogs_cache is not None and 
            current_time - self._dialogs_cache_time < self._cache_ttl):
            
            cached_result = self._dialogs_cache[:limit]
            print(f"📋 Диалоги получены из кеша за {time.time() - start_time:.2f}с (лимит: {limit})")
            return cached_result
        
        await self.start_client()
        
        print(f"🔄 Обновляем кеш диалогов...")
        dialogs = []
        count = 0
        
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            
            # Пропускаем архивные диалоги без сообщений
            if hasattr(dialog, 'archived') and dialog.archived:
                continue
                
            # Определяем тип чата
            if isinstance(entity, User):
                chat_type = "user"
            elif isinstance(entity, Chat):
                chat_type = "group"
            elif isinstance(entity, Channel):
                if entity.broadcast:
                    chat_type = "channel"
                else:
                    chat_type = "supergroup"
            else:
                chat_type = "unknown"
            
            dialogs.append({
                "id": entity.id,
                "name": dialog.title or f"User {entity.id}",
                "type": chat_type,
                "unread_count": dialog.unread_count,
                "last_message_date": dialog.date.isoformat() if dialog.date else None
            })
            
            count += 1
            # Ограничиваем загрузку для кеша (максимум 200)
            if count >= 200:
                break
        
        # Сохраняем в кеш
        self._dialogs_cache = dialogs
        self._dialogs_cache_time = current_time
        
        result = dialogs[:limit]
        duration = time.time() - start_time
        print(f"✅ Загружено {len(dialogs)} диалогов в кеш за {duration:.2f}с (возвращено: {len(result)})")
        
        return result
    
    def clear_dialogs_cache(self):
        """Очистить кеш диалогов"""
        self._dialogs_cache = None
        self._dialogs_cache_time = 0
        print("🗑️ Кеш диалогов очищен")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Получить информацию о состоянии кеша"""
        if self._dialogs_cache is None:
            return {"status": "empty", "dialogs_count": 0, "age_seconds": 0}
        
        age = time.time() - self._dialogs_cache_time
        return {
            "status": "active" if age < self._cache_ttl else "expired",
            "dialogs_count": len(self._dialogs_cache),
            "age_seconds": int(age),
            "ttl_seconds": self._cache_ttl
        }
    
    async def get_messages(self, chat_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Получить сообщения из указанного чата"""
        await self.start_client()
        
        try:
            entity = await self.client.get_entity(chat_id)
        except ValueError:
            raise ValueError(f"Чат с ID {chat_id} не найден")
        
        messages = []
        async for message in self.client.iter_messages(entity, limit=limit):
            if message.text:
                messages.append({
                    "id": message.id,
                    "text": message.text,
                    "date": message.date.isoformat(),
                    "sender": await self._get_sender_name(message)
                })
        
        return messages
    
    async def send_message(self, chat_id: int, message: str) -> Dict[str, str]:
        """Отправить сообщение в указанный чат"""
        await self.start_client()
        
        try:
            entity = await self.client.get_entity(chat_id)
            await self.client.send_message(entity, message)
            return {"status": "ok", "message": "Сообщение отправлено успешно"}
        except ValueError:
            raise ValueError(f"Чат с ID {chat_id} не найден")
        except Exception as e:
            raise Exception(f"Ошибка при отправке сообщения: {str(e)}")
    
    async def join_chat(self, invite_link: str) -> Dict[str, str]:
        """Присоединиться к чату или каналу по ссылке"""
        await self.start_client()
        
        try:
            # Попытка присоединиться по ссылке
            result = await self.client(types.functions.messages.ImportChatInviteRequest(
                hash=invite_link.split('/')[-1]
            ))
            return {"status": "joined", "message": "Успешно присоединились к чату"}
        except errors.InviteHashExpiredError:
            raise ValueError("Ссылка приглашения истекла")
        except errors.InviteHashInvalidError:
            raise ValueError("Неверная ссылка приглашения")
        except errors.UserAlreadyParticipantError:
            return {"status": "already_joined", "message": "Вы уже состоите в этом чате"}
        except Exception as e:
            # Попытка присоединиться по username
            try:
                if 't.me/' in invite_link:
                    username = invite_link.split('/')[-1]
                    if username.startswith('@'):
                        username = username[1:]
                    
                    entity = await self.client.get_entity(username)
                    await self.client(types.functions.channels.JoinChannelRequest(entity))
                    return {"status": "joined", "message": "Успешно присоединились к каналу"}
                else:
                    raise Exception(f"Ошибка при присоединении к чату: {str(e)}")
            except Exception as inner_e:
                raise Exception(f"Ошибка при присоединении к чату: {str(inner_e)}")
    
    async def _get_sender_name(self, message) -> str:
        """Получить имя отправителя сообщения"""
        if message.sender:
            if hasattr(message.sender, 'first_name'):
                name = message.sender.first_name
                if hasattr(message.sender, 'last_name') and message.sender.last_name:
                    name += f" {message.sender.last_name}"
                return name
            elif hasattr(message.sender, 'title'):
                return message.sender.title
            else:
                return f"User {message.sender_id}"
        return "Unknown"

# Глобальный экземпляр сервиса
telegram_service = TelegramService() 