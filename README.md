# Telegram-бот «Домашний уход за стопами»

Бот оформляет оплату информационного гайда и выдаёт покупателю одноразовую
ссылку в закрытый Telegram-канал. Архитектура разделена на два независимых
процесса, использующих одну SQLite-базу:

- `marilobanka-bot` — Telegram polling и выдача доступа;
- `marilobanka-web` — callback и страницы возврата Robokassa.

Без полного набора платёжных и налоговых настроек бот остаётся в безопасном
демонстрационном режиме и не создаёт платёжные ссылки.

## Локальный запуск

```bash
python3 -m venv bot_tg/.venv
bot_tg/.venv/bin/pip install -r bot_tg/requirements.txt
cp .env.example .env
cd bot_tg
.venv/bin/python main.py
```

Web-процесс:

```bash
cd bot_tg
.venv/bin/gunicorn --bind 127.0.0.1:18082 --workers 1 --threads 4 \
  'web:create_app()'
```

Тесты:

```bash
cd bot_tg
.venv/bin/python -m unittest discover -s tests -v
```

## Telegram-канал

Для приветственного поста используются `WELCOME_CHAT_ID` и
`WELCOME_MESSAGE_ID`. Для выдачи доступа используется `ACCESS_CHAT_ID`, а
`ACCESS_CHANNEL_URL` ведёт уже вступившего покупателя к нужному посту канала. Бот
должен быть администратором канала и иметь право создавать пригласительные
ссылки. Ссылка не создаётся до подтверждения оплаты серверным callback.

Актуальный текст оферты хранится в `docs/public_offer.md`, а в Telegram
в первую очередь копируется готовое сообщение из `OFFER_CHAT_ID` и
`OFFER_MESSAGE_ID`. Если Telegram не позволил его скопировать, бот отправляет
резервную PDF-версию из `OFFER_FILE_PATH`. Перед публикацией новой
редакции DOCX и PDF нужно пересобрать и перезапустить `marilobanka-bot`:

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/python scripts/generate_offer.py
```

## Robokassa

Проект использует отдельный префикс `/bots/marilobanka`:

- Result URL: `https://karpau.by/bots/marilobanka/robokassa/result`, POST;
- Success URL: `https://karpau.by/bots/marilobanka/robokassa/success`, GET;
- Fail URL: `https://karpau.by/bots/marilobanka/robokassa/fail`, GET.

Старые адреса `/payment/success` и `/payment/fail` сохранены как совместимые
алиасы, но в кабинете Robokassa следует указывать адреса выше.

Алгоритм подписи — MD5, он должен совпадать с техническими настройками
магазина Robokassa. Приложение автоматически выбирает пару паролей:

- `ROBOKASSA_TEST=1`: `PASS_TEST_1` и `PASS_TEST_2`;
- `ROBOKASSA_TEST=0`: `PASS_1` и `PASS_2`.

`PASS_3` зарезервирован для API Robokassa, которым требуется третий пароль, и
не участвует в обычном платеже или Result URL.

`InvId` не использует короткую последовательность `1, 2, 3`: номер начинается
не ниже `1000000000000` и формируется по времени в миллисекундах с проверкой
последнего номера в базе. У Marilobanka отдельный `MERCHANT_LOGIN`, поэтому её
заказы не пересекаются с заказами `yuliana_tg_bot`.

Result URL проверяет подпись `OutSum:InvId:Пароль#2`, сумму заказа и отвечает
`OK{InvId}`. Success URL не меняет статус заказа.

## Фискализация

Для рабочего магазина используется `FISCALIZATION_MODE=receipt`: приложение
передаёт Robokassa подписанный параметр `Receipt` с номенклатурой. В личном
кабинете Robokassa должно быть выбрано текущее решение «Робочеки СМЗ», а в
«Мой налог» — выданы полномочия Robokassa и НКО «Платежи и Расчёты». Тогда
Robokassa использует номенклатуру платежа, регистрирует доход НПД и отправляет
чек покупателю и в ФНС.

Для текущего продукта передаётся одна позиция:

```dotenv
FISCALIZATION_MODE=receipt
RECEIPT_SNO=
RECEIPT_TAX=none
RECEIPT_PAYMENT_METHOD=full_payment
RECEIPT_PAYMENT_OBJECT=service
RECEIPT_ITEM_NAME=Гайд «Домашний уход за стопами»
```

`RECEIPT_SNO` намеренно оставлен пустым: в допустимых значениях Robokassa для
`Receipt` нет системы налогообложения НПД. Налоговый режим определяется
подключёнными «Робочеками СМЗ» и полномочиями в «Мой налог».

`Receipt` кодируется и включается в подпись платежа по формуле
`MerchantLogin:OutSum:InvId:Receipt:Пароль#1`.

Настройки `full_payment`, `service` и `none` совпадают с работающей схемой
проекта `yuliana_tg_bot`: доступ выдаётся сразу после подтверждения платежа,
предмет расчёта оформляется как услуга, НДС не применяется.

## Сервер

PM2-конфигурация находится в `deploy/ecosystem.config.js`. Процессы работают
отдельно от других сервисов. Web-процесс слушает только локальный адрес
`127.0.0.1:18082`; публичный маршрут должен проксироваться отдельно.

```bash
export PATH=/usr/lib/ispnodejs/bin:$PATH
pm2 startOrReload deploy/ecosystem.config.js
pm2 save
pm2 status marilobanka-bot marilobanka-web
```

Секретный `.env` хранится только локально и на сервере с правами `600` и не
отслеживается Git.
