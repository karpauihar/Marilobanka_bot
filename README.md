# Telegram-бот маникюрного клуба

Бот оформляет доступ в закрытый Telegram-канал. Сейчас проект работает в демонстрационном режиме: интерфейс доступен, но оплата отключена до добавления реквизитов Robokassa. Без подтверждённой оплаты бот не создаёт ссылку на канал.

## Возможности

- приветствие и тестовый интерфейс маникюрного клуба;
- безопасный режим без оплаты при незаполненной Robokassa;
- SQLite-база пользователей и заказов;
- проверка callback-подписи Robokassa;
- одноразовые ссылки в закрытый канал после подтверждённой оплаты;
- отдельные файл логов и PM2-процесс с автоматическим перезапуском.

## Локальный запуск

```bash
python3 -m venv bot_tg/.venv
bot_tg/.venv/bin/pip install -r bot_tg/requirements.txt
cp .env.example .env
# заполните как минимум TOKEN
cd bot_tg
.venv/bin/python main.py
```

Приложение ищет `.env` сначала в корне проекта, затем в `bot_tg/`. Реальный `.env` не отслеживается Git.

Проверка:

```bash
cd bot_tg
.venv/bin/python -m unittest discover -s tests -v
```

## Подключение закрытого канала

1. Создайте закрытый Telegram-канал.
2. Добавьте бота администратором и разрешите ему создавать пригласительные ссылки.
3. Укажите числовой ID канала в `ACCESS_CHAT_ID` (обычно начинается с `-100`).
4. Перезапустите процесс бота.

Наличие ID канала само по себе не открывает доступ: ссылка выдаётся только пользователю с подтверждённым платёжным заказом.

## Подключение Robokassa

Заполните `MERCHANT_LOGIN`, `PASSWORD_1`, `PASSWORD_2`, `SERVER_URL` и `COST`. Все пять значений должны быть заданы одновременно. Для боевого магазина оставьте `ROBOKASSA_TEST=0`.

В кабинете Robokassa настройте:

- Result URL: `https://ВАШ_ДОМЕН/bots/marilobanka/robokassa/result`, метод POST;
- Success URL: `https://ВАШ_ДОМЕН/bots/marilobanka/payment/success`, метод GET;
- Fail URL: `https://ВАШ_ДОМЕН/bots/marilobanka/payment/fail`, метод GET.

Для приёма callback нужно отдельно запустить `web:create_app()` через Gunicorn и добавить изолированный location в Nginx. До появления реальных реквизитов web-процесс на сервере намеренно не запускается.

## Развёртывание на сервере

Проект разворачивается отдельно от других ботов. PM2-конфигурация находится в `deploy/ecosystem.config.js`, имя процесса — `marilobanka-bot`.

```bash
cd /var/www/h219734/data/apps/Marilobanka_bot
python3 -m venv bot_tg/.venv
bot_tg/.venv/bin/pip install -r bot_tg/requirements.txt
export PATH=/usr/lib/ispnodejs/bin:$PATH
pm2 start deploy/ecosystem.config.js
pm2 save
pm2 status marilobanka-bot
```

Секретный `.env` хранится только на рабочей машине и сервере и никогда не отправляется в GitHub.
