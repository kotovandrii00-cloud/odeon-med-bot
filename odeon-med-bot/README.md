# Odeon Med Bot

Telegram-бот для учёта лекарств в Google Sheets.

## Функции

- Добавление лекарства с фото
- Категории из листа `Категории`
- Поиск лекарства по названию
- Проверка срока годности
- Уведомление за 90 дней и меньше
- Списание просроченных лекарств в `Архив`

## Google Таблица

Создай Google Таблицу с листами:

- `Лекарства`
- `Категории`
- `Архив`

Бот сам создаст заголовки, если листы пустые.

## Railway Variables

Добавь в Railway → Variables:

```env
BOT_TOKEN=
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_JSON=
ADMIN_CHAT_ID=
TIMEZONE=Europe/Paris
NOTIFY_DAYS=90
DAILY_CHECK_HOUR=9
DAILY_CHECK_MINUTE=0
```

`GOOGLE_CREDENTIALS_JSON` — весь JSON service account в одну строку.

## Запуск локально

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Запуск на Railway

1. Создай GitHub repo.
2. Загрузи туда эти файлы.
3. Railway → New Project → Deploy from GitHub Repo.
4. Добавь Variables.
5. Deploy.
