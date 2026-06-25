# odeon-med-bot

Telegram-бот на Python для учёта лекарств через Google Sheets и хранения фото в Google Drive.

## Что умеет бот

- добавляет лекарство с фото упаковки;
- хранит каждую упаковку отдельной строкой;
- ищет лекарства по названию или ID;
- списывает использованное количество;
- переносит лекарства в архив вместо удаления;
- проверяет сроки годности вручную и ежедневно в 08:00 Europe/Paris;
- ведёт историю всех действий.

## Структура Google Таблицы

`setup_sheet.py` автоматически создаёт листы:

- `Лекарства`
- `Категории`
- `История`
- `Архив`
- `Пользователи`

ID текущей таблицы:

```text
1Q9yBOi0ExBe93BZDASV4G_KpEcZESIF-RJTmpPGFki4
```

ID папки Google Drive для фото:

```text
1iZx4pr4B7tBxtDOvUHPh4aKqCQf_-bQa
```

## 1. Создать Telegram-бота через BotFather

1. Откройте Telegram и найдите `@BotFather`.
2. Отправьте `/newbot`.
3. Укажите имя бота и username.
4. Скопируйте токен и сохраните его в переменную `BOT_TOKEN`.

## 2. Подключить Google Sheets API и Google Drive API

1. Откройте [Google Cloud Console](https://console.cloud.google.com/).
2. Создайте новый проект или выберите существующий.
3. Откройте `APIs & Services` → `Library`.
4. Включите `Google Sheets API`.
5. Включите `Google Drive API`.

## 3. Создать Service Account

1. В Google Cloud Console откройте `IAM & Admin` → `Service Accounts`.
2. Нажмите `Create service account`.
3. Создайте ключ: `Keys` → `Add key` → `Create new key` → `JSON`.
4. Скачанный JSON используйте как значение `GOOGLE_CREDENTIALS_JSON`.

`GOOGLE_CREDENTIALS_JSON` можно передать одним из способов:

- полный JSON в одну строку;
- base64 от JSON-файла;
- локальный путь к JSON-файлу при запуске на своём компьютере.

## 4. Дать service account доступ к таблице

1. Откройте JSON-ключ service account.
2. Найдите поле `client_email`.
3. Откройте Google Таблицу.
4. Нажмите `Share`.
5. Добавьте `client_email` с правами `Editor`.

То же самое сделайте для папки Google Drive с фото: добавьте `client_email` с правами `Editor`.

## 5. Получить GOOGLE_SHEET_ID

ID таблицы находится в ссылке:

```text
https://docs.google.com/spreadsheets/d/GOOGLE_SHEET_ID/edit
```

Для этого проекта уже указан:

```text
GOOGLE_SHEET_ID=1Q9yBOi0ExBe93BZDASV4G_KpEcZESIF-RJTmpPGFki4
```

## 6. Получить GOOGLE_DRIVE_FOLDER_ID

ID папки находится в ссылке:

```text
https://drive.google.com/drive/folders/GOOGLE_DRIVE_FOLDER_ID
```

Для этого проекта уже указан:

```text
GOOGLE_DRIVE_FOLDER_ID=1iZx4pr4B7tBxtDOvUHPh4aKqCQf_-bQa
```

## 7. Запуск локально

Установите Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=123456:telegram-token
GOOGLE_SHEET_ID=1Q9yBOi0ExBe93BZDASV4G_KpEcZESIF-RJTmpPGFki4
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
GOOGLE_DRIVE_FOLDER_ID=1iZx4pr4B7tBxtDOvUHPh4aKqCQf_-bQa
ADMIN_CHAT_ID=123456789
TIMEZONE=Europe/Paris
```

Создайте листы и заголовки:

```bash
python setup_sheet.py
```

Запустите бота:

```bash
python main.py
```

## 8. Деплой на Railway

1. Создайте репозиторий `odeon-med-bot` на GitHub.
2. Загрузите в него этот проект.
3. Откройте [Railway](https://railway.app/).
4. Нажмите `New Project` → `Deploy from GitHub repo`.
5. Выберите репозиторий `kotovandrii00-cloud/odeon-med-bot`.
6. Railway увидит `Procfile` и запустит worker-команду:

```text
python main.py
```

## 9. Railway Variables

Добавьте в Railway → `Variables`:

```env
BOT_TOKEN=
GOOGLE_SHEET_ID=1Q9yBOi0ExBe93BZDASV4G_KpEcZESIF-RJTmpPGFki4
GOOGLE_CREDENTIALS_JSON=
GOOGLE_DRIVE_FOLDER_ID=1iZx4pr4B7tBxtDOvUHPh4aKqCQf_-bQa
ADMIN_CHAT_ID=
TIMEZONE=Europe/Paris
```

`ADMIN_CHAT_ID` — ваш Telegram ID. Если нужно отправлять уведомления нескольким администраторам, укажите ID через запятую.

## Роли

- `admin` — полный доступ: добавление, поиск, списание, архив, проверка сроков.
- `user` — поиск, проверка сроков, списание использованных лекарств.

Первый вход пользователя создаёт строку в листе `Пользователи`. Если Telegram ID совпадает с `ADMIN_CHAT_ID`, роль будет `admin`.

