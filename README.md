# EngTrain Bot - Telegram English Learning Bot

Объединенный репозиторий для Telegram бота и WebApp для изучения английского языка.

## 🏗️ Структура проекта

```
english-ai-bot/
├── bot/                    # Python backend (Telegram Bot)
│   ├── english_bot_super_webhook.py
│   ├── requirements.txt
│   └── ...
├── webapp/                 # HTML/CSS/JS frontend (Telegram WebApp)
│   ├── index.html
│   ├── style.css
│   ├── grammar.html
│   ├── vocabulary.html
│   ├── practice.html
│   ├── games.html
│   └── full-version.html
├── README.md
└── railway.json
```

## 🚀 Деплой на Railway

### 1. Подготовка
- Убедитесь, что у вас есть аккаунт на [Railway](https://railway.app)
- Создайте новый проект

### 2. Настройка переменных окружения
В Railway добавьте следующие переменные:
```
TELEGRAM_API_TOKEN=your_bot_token_here
RAILWAY_PUBLIC_URL=https://your-app-name.railway.app
```

### 3. Деплой
1. Подключите этот репозиторий к Railway
2. Railway автоматически определит Python приложение
3. Приложение будет доступно по адресу: `https://your-app-name.railway.app`

## 🌐 WebApp

WebApp доступен по адресу: `https://your-app-name.railway.app/webapp/`

### Страницы WebApp:
- **Главная** (`/webapp/`) - выбор разделов
- **Грамматика** (`/webapp/grammar.html`) - грамматические упражнения
- **Словарь** (`/webapp/vocabulary.html`) - словарный запас
- **Практика** (`/webapp/practice.html`) - упражнения
- **Игры** (`/webapp/games.html`) - обучающие игры
- **Полная версия** (`/webapp/full-version.html`) - информация о премиум

## 🤖 Telegram Bot

Бот обрабатывает:
- Команды меню
- WebApp данные
- Интерактивные кнопки
- Тесты и упражнения

### Команды бота:
- `/start` - запуск бота
- `/grammar` - грамматика
- `/vocabulary` - словарь
- `/exercises` - упражнения
- `/games` - игры
- `/settings` - настройки

## 📝 Обновления

### Добавление новых страниц WebApp:
1. Создайте HTML файл в папке `webapp/`
2. Добавьте ссылку в `index.html`
3. Обновите стили в `style.css` при необходимости

### Обновление бота:
1. Измените код в `english_bot_super_webhook.py`
2. Добавьте новые обработчики при необходимости
3. Обновите данные в JSON файлах

## 🔧 Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск локально
python english_bot_super_webhook.py
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи в Railway
2. Убедитесь, что все переменные окружения настроены
3. Проверьте, что WebApp URL правильно настроен в боте