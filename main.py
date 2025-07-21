from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
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
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health - проверить статус сервиса и авторизации",
            "init_session": "POST /init-session - инициализировать сессию (только локально)",
            "dialogs": "GET /dialogs - получить список чатов",
            "messages": "GET /messages?chat_id=ID&limit=20 - получить сообщения",
            "send_message": "POST /sendMessage - отправить сообщение",
            "join_chat": "POST /joinChat - вступить в чат"
        },
        "docs": "/docs - интерактивная документация API"
    }

@app.get("/dialogs", response_model=List[DialogResponse])
async def get_dialogs():
    """
    Получить список всех доступных чатов и каналов
    
    Возвращает список диалогов с информацией о:
    - ID чата
    - Названии
    - Типе (user/group/channel/supergroup)
    - Количестве непрочитанных сообщений
    """
    await check_telegram_auth()
    try:
        dialogs = await telegram_service.get_dialogs()
        return dialogs
    except Exception as e:
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
    await check_telegram_auth()
    try:
        messages = await telegram_service.get_messages(chat_id, limit)
        return messages
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
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

@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    try:
        # Проверяем подключение к Telegram
        if telegram_service.client and telegram_service.client.is_connected():
            is_authorized = await telegram_service.client.is_user_authorized()
            return {
                "status": "healthy", 
                "telegram": "connected",
                "authorized": is_authorized
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