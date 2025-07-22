from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import time
from telegram_client import telegram_service

app = FastAPI(
    title="Telegram API Gateway",
    description="API для доступа к Telegram через личный аккаунт",
    version="1.0.0"
)

# Модели данных для запросов
class SendMessageRequest(BaseModel):
    chat_id: int
    message: str

class JoinChatRequest(BaseModel):
    invite_link: str

# Модели ответов
class DialogResponse(BaseModel):
    id: int
    name: str
    type: str
    unread_count: int
    last_message_date: Optional[str] = None

class MessageResponse(BaseModel):
    id: int
    text: str
    date: str
    sender: str

class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None

# Вспомогательная функция для проверки авторизации
async def check_telegram_auth():
    """Проверяет подключение и авторизацию Telegram клиента"""
    if not telegram_service.client or not telegram_service.client.is_connected():
        raise HTTPException(status_code=503, detail="Telegram клиент не подключен")
    
    if not await telegram_service.client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Telegram сессия не авторизована")

@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения"""
    try:
        await telegram_service.start_client()
        print("✅ Telegram клиент успешно подключен")
    except ValueError as e:
        print(f"⚠️ Предупреждение: {e}")
        print("ℹ️ API будет доступно, но эндпоинты Telegram не будут работать до авторизации")
    except Exception as e:
        print(f"❌ Критическая ошибка подключения к Telegram: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """Событие завершения работы приложения"""
    try:
        await telegram_service.disconnect_client()
        print("✅ Telegram клиент отключен")
    except Exception as e:
        print(f"❌ Ошибка при отключении Telegram клиента: {e}")

@app.get("/")
async def root():
    """Корневой эндпоинт с информацией о API"""
    return {
        "message": "Telegram API Gateway",
        "version": "1.1.0",
        "features": [
            "✅ Кеширование диалогов (TTL 10 мин)",
            "⚡ Быстрые ответы из кеша",
            "📊 Логирование производительности",
            "🔄 Управление кешем"
        ],
        "endpoints": {
            "health": "GET /health - проверить статус сервиса и кеша",
            "dialogs": "GET /dialogs?limit=50&force_refresh=false - получить список чатов",
            "dialogs_refresh": "POST /dialogs/refresh - обновить кеш диалогов",
            "cache_info": "GET /dialogs/cache/info - информация о кеше",
            "cache_clear": "DELETE /dialogs/cache - очистить кеш",
            "messages": "GET /messages?chat_id=ID&limit=20 - получить сообщения",
            "send_message": "POST /sendMessage - отправить сообщение",
            "join_chat": "POST /joinChat - вступить в чат",
            "init_session": "POST /init-session - инициализировать сессию (только локально)"
        },
        "docs": "/docs - интерактивная документация API"
    }

@app.get("/dialogs", response_model=List[DialogResponse])
async def get_dialogs(
    limit: int = Query(50, description="Количество диалогов для получения", ge=1, le=200),
    force_refresh: bool = Query(False, description="Принудительно обновить кеш")
):
    """
    Получить список доступных чатов и каналов с кешированием
    
    Параметры:
    - limit: количество диалогов (по умолчанию 50, максимум 200)
    - force_refresh: принудительно обновить кеш (по умолчанию false)
    
    Возвращает список диалогов с информацией о:
    - ID чата
    - Названии  
    - Типе (user/group/channel/supergroup)
    - Количестве непрочитанных сообщений
    - Дате последнего сообщения
    """
    start_time = time.time()
    await check_telegram_auth()
    
    try:
        dialogs = await telegram_service.get_dialogs(limit=limit, force_refresh=force_refresh)
        duration = time.time() - start_time
        print(f"📊 API /dialogs: {len(dialogs)} диалогов за {duration:.2f}с (limit={limit}, refresh={force_refresh})")
        return dialogs
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ API /dialogs ошибка за {duration:.2f}с: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения диалогов: {str(e)}")

@app.get("/messages", response_model=List[MessageResponse])
async def get_messages(
    chat_id: int = Query(..., description="ID чата для получения сообщений"),
    limit: int = Query(20, description="Количество сообщений для получения", ge=1, le=100)
):
    """
    Получить последние сообщения из указанного чата
    
    Параметры:
    - chat_id: ID чата (обязательный)
    - limit: количество сообщений (по умолчанию 20, максимум 100)
    """
    start_time = time.time()
    await check_telegram_auth()
    
    try:
        messages = await telegram_service.get_messages(chat_id, limit)
        duration = time.time() - start_time
        print(f"📨 API /messages: {len(messages)} сообщений из чата {chat_id} за {duration:.2f}с")
        return messages
    except ValueError as e:
        duration = time.time() - start_time
        print(f"❌ API /messages ошибка 404 за {duration:.2f}с: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ API /messages ошибка за {duration:.2f}с: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения сообщений: {str(e)}")

@app.post("/sendMessage", response_model=StatusResponse)
async def send_message(request: SendMessageRequest):
    """
    Отправить сообщение от лица пользователя
    
    Тело запроса:
    - chat_id: ID чата для отправки сообщения
    - message: текст сообщения
    """
    await check_telegram_auth()
    try:
        result = await telegram_service.send_message(request.chat_id, request.message)
        return StatusResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки сообщения: {str(e)}")

@app.post("/joinChat", response_model=StatusResponse)
async def join_chat(request: JoinChatRequest):
    """
    Вступить в чат или канал по ссылке
    
    Тело запроса:
    - invite_link: ссылка приглашения или username канала (например, https://t.me/channel_name)
    
    Поддерживаемые форматы ссылок:
    - https://t.me/joinchat/HASH
    - https://t.me/channel_name
    - @channel_name
    """
    await check_telegram_auth()
    try:
        result = await telegram_service.join_chat(request.invite_link)
        return StatusResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка присоединения к чату: {str(e)}")

@app.post("/init-session")
async def init_session():
    """
    Инициализация сессии Telegram (только для локального использования)
    
    Этот эндпоинт поможет в случае, если сессия потеряна или повреждена.
    Работает только в среде с интерактивным терминалом.
    """
    try:
        # Отключаем текущий клиент, если он есть
        if telegram_service.client:
            await telegram_service.disconnect_client()
            telegram_service.client = None
        
        # Пытаемся создать новую сессию
        telegram_service.client = TelegramClient(
            telegram_service.session_name, 
            telegram_service.api_id, 
            telegram_service.api_hash
        )
        
        await telegram_service.client.start()
        return {"status": "success", "message": "Сессия успешно инициализирована"}
        
    except EOFError:
        raise HTTPException(
            status_code=400, 
            detail="Интерактивная авторизация невозможна в облачной среде. Используйте локальную среду."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка инициализации сессии: {str(e)}")

@app.post("/dialogs/refresh")
async def refresh_dialogs_cache():
    """
    Принудительно обновить кеш диалогов
    
    Полезно для получения актуального списка чатов без ожидания истечения TTL
    """
    start_time = time.time()
    await check_telegram_auth()
    
    try:
        # Очищаем кеш и получаем свежие данные
        telegram_service.clear_dialogs_cache()
        dialogs = await telegram_service.get_dialogs(limit=200, force_refresh=True)
        duration = time.time() - start_time
        
        cache_info = telegram_service.get_cache_info()
        print(f"🔄 Кеш обновлен: {len(dialogs)} диалогов за {duration:.2f}с")
        
        return {
            "status": "refreshed",
            "message": f"Кеш обновлен, загружено {len(dialogs)} диалогов",
            "duration_seconds": round(duration, 2),
            "cache_info": cache_info
        }
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ Ошибка обновления кеша за {duration:.2f}с: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обновления кеша: {str(e)}")

@app.get("/dialogs/cache/info")
async def get_cache_info():
    """
    Получить информацию о состоянии кеша диалогов
    
    Возвращает:
    - Статус кеша (empty/active/expired)
    - Количество диалогов в кеше
    - Возраст кеша в секундах
    - TTL кеша
    """
    cache_info = telegram_service.get_cache_info()
    return {
        "cache": cache_info,
        "timestamp": time.time()
    }

@app.delete("/dialogs/cache")
async def clear_cache():
    """Очистить кеш диалогов"""
    telegram_service.clear_dialogs_cache()
    return {
        "status": "cleared",
        "message": "Кеш диалогов очищен"
    }

@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    start_time = time.time()
    
    try:
        # Проверяем подключение к Telegram
        if telegram_service.client and telegram_service.client.is_connected():
            is_authorized = await telegram_service.client.is_user_authorized()
            cache_info = telegram_service.get_cache_info()
            duration = time.time() - start_time
            
            return {
                "status": "healthy", 
                "telegram": "connected",
                "authorized": is_authorized,
                "cache": cache_info,
                "response_time_seconds": round(duration, 3)
            }
        else:
            return {
                "status": "unhealthy", 
                "telegram": "disconnected",
                "authorized": False
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 