# 🚂 Развертывание на Railway

## Проблема авторизации в облачной среде

Railway и другие облачные платформы не поддерживают интерактивный ввод данных через терминал. Поэтому для работы Telegram API необходимо предварительно создать файл сессии локально.

## 📋 Пошаговая инструкция

### 1. Локальная подготовка сессии

**Создайте `.env` файл локально:**
```env
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=telegram_session
```

**Установите зависимости:**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

**Запустите инициализацию сессии:**
```bash
python main.py
```

При первом запуске:
1. Введите ваш номер телефона: `+1234567890`
2. Введите код из Telegram
3. Введите пароль 2FA (если включен)

**Результат:** Создастся файл `telegram_session.session`

### 2. Подготовка к деплою

**Остановите локальный сервер** (Ctrl+C)

**Создайте временный скрипт для кодирования сессии:**
```python
# encode_session.py
import base64

with open('telegram_session.session', 'rb') as f:
    session_data = f.read()
    encoded = base64.b64encode(session_data).decode('utf-8')
    print(f"SESSION_FILE_BASE64={encoded}")
```

**Запустите скрипт:**
```bash
python encode_session.py
```

**Скопируйте** полученную строку `SESSION_FILE_BASE64=...`

### 3. Настройка Railway

**Зайдите в панель Railway:**
1. Откройте ваш проект
2. Перейдите в Variables
3. Добавьте переменные:

```
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=telegram_session
SESSION_FILE_BASE64=вставьте_закодированную_строку_сессии
```

### 4. Обновление кода для Railway

Добавьте в `telegram_client.py` в метод `__init__` после загрузки переменных:

```python
# Восстанавливаем сессию из base64 если она есть
session_base64 = os.getenv('SESSION_FILE_BASE64')
if session_base64 and not os.path.exists(f"{self.session_name}.session"):
    try:
        import base64
        session_data = base64.b64decode(session_base64)
        with open(f"{self.session_name}.session", 'wb') as f:
            f.write(session_data)
        print("✅ Сессия восстановлена из переменной окружения")
    except Exception as e:
        print(f"❌ Ошибка восстановления сессии: {e}")
```

### 5. Деплой

**Закоммитьте изменения:**
```bash
git add .
git commit -m "Add session restore from environment variable"
git push origin main
```

Railway автоматически пересоберет и запустит приложение.

## ✅ Проверка работы

**Проверьте статус:**
```bash
curl https://your-app.railway.app/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "telegram": "connected", 
  "authorized": true
}
```

**Протестируйте API:**
```bash
curl https://your-app.railway.app/dialogs
```

## 🔧 Устранение проблем

### Если сессия не восстанавливается:

1. **Проверьте переменные** в Railway Dashboard
2. **Пересоздайте сессию** локально:
   ```bash
   rm -f *.session
   python main.py
   # Повторите кодирование и загрузку
   ```

### Если получаете 401 ошибку:

```json
{"detail": "Telegram сессия не авторизована"}
```

**Решение:** Пересоздайте сессию локально и обновите `SESSION_FILE_BASE64`

### Если получаете 503 ошибку:

```json
{"detail": "Telegram клиент не подключен"}
```

**Решение:** Проверьте логи Railway на наличие ошибок подключения

## 📱 Альтернативный способ - Telegram Bot API

Если проблемы с пользовательской сессией продолжаются, рассмотрите использование Bot API:

1. Создайте бота через @BotFather
2. Получите Bot Token
3. Используйте Bot API вместо MTProto

**Преимущества Bot API:**
- Не требует интерактивной авторизации
- Стабильная работа в облачных средах
- Проще в развертывании

**Недостатки:**
- Ограниченная функциональность
- Невозможность читать сообщения в приватных чатах без приглашения бота

## 🆘 Поддержка

Если проблемы остаются, проверьте:
1. Логи в Railway Dashboard
2. Валидность API ключей на https://my.telegram.org
3. Размер файла сессии (должен быть несколько KB) 