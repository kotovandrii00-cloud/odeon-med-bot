# Odeon Med Bot

Telegram-бот для учёта лекарств в Google Sheets.

## Возможности

- Добавление лекарства по шагам
- Фото упаковки
- Категории из листа `Категории`
- Поиск по названию
- Проверка сроков годности
- Ежедневное уведомление за 90 дней до окончания срока
- Статусы: годно / скоро истекает / просрочено
- Архив списанных лекарств

## Структура Google Таблицы

Создайте Google Таблицу с тремя листами:

1. `Лекарства`
2. `Категории`
3. `Архив`

В листе `Лекарства` и `Архив` бот сам создаст заголовки:

```text
ID | Фото | Название | Категория | Срок годности | Количество | Место | Группа | Статус | Добавил | Дата добавления
```

В листе `Категории` можно указать категории в колонке A, начиная со второй строки.

## Переменные окружения

В Railway → Variables добавьте:

```env
BOT_TOKEN=ваш_токен_бота
GOOGLE_SHEET_ID=id_google_таблицы
GOOGLE_CREDENTIALS_JSON={...json сервисного аккаунта...}
ADMIN_CHAT_ID=ваш_telegram_chat_id
TIMEZONE=Europe/Paris
REMIND_DAYS=90
DAILY_CHECK_HOUR=9
```

## Как получить GOOGLE_SHEET_ID

Откройте Google Таблицу. В ссылке будет так:

```text
https://docs.google.com/spreadsheets/d/GOOGLE_SHEET_ID/edit
```

Скопируйте часть между `/d/` и `/edit`.

## Как подключить Google Sheets

1. Зайдите в Google Cloud Console.
2. Создайте проект.
3. Включите API:
   - Google Sheets API
   - Google Drive API
4. Создайте Service Account.
5. Создайте JSON key.
6. Скопируйте весь JSON в Railway переменную `GOOGLE_CREDENTIALS_JSON`.
7. В JSON найдите email сервисного аккаунта, например:

```text
service-account@project.iam.gserviceaccount.com
```

8. Откройте Google Таблицу → Share → добавьте этот email как Editor.

## Запуск на Railway

1. Создайте GitHub репозиторий.
2. Загрузите эти файлы.
3. Railway → New Project → Deploy from GitHub Repo.
4. Выберите репозиторий.
5. Добавьте Variables.
6. Railway сам запустит команду из `Procfile`:

```text
worker: python main.py
```

## Локальный запуск

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Для локального запуска можно установить переменные через `.env`, но текущий код читает их из окружения. На Railway это работает сразу.

## Важная логика

Просроченные лекарства не удаляются автоматически. Они получают статус `❌ Просрочено`.
Чтобы убрать препарат из активной базы, нужно найти его через поиск и нажать `Списать в архив`.
