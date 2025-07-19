# 🚀 Быстрый старт

## 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

## 2. Настройка переменных окружения
Создайте файл `.env`:
```env
API_ID=your_api_id
API_HASH=your_api_hash
SESSION_NAME=telegram_session
```

> Получите API_ID и API_HASH на https://my.telegram.org/auth

## 3. Запуск приложения
```bash
python3 main.py
```

При первом запуске потребуется:
- Ввести номер телефона
- Ввести код из Telegram
- При необходимости ввести пароль 2FA

## 4. Проверка работы
Откройте в браузере: http://localhost:8000/docs

## 5. Тестирование API

### Получить список чатов:
```bash
curl http://localhost:8000/dialogs
```

### Проверить статус:
```bash
curl http://localhost:8000/health
```

## Развертывание на Railway

1. Создайте проект на Railway
2. Подключите репозиторий
3. Установите переменные окружения в настройках Railway:
   - `API_ID`
   - `API_HASH`
   - `SESSION_NAME`
4. Railway автоматически развернет приложение 