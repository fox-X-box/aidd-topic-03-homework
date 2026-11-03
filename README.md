# investing

## Локальный запуск без Docker/PostgreSQL/Redis (рекомендуется для разработки)

```bash
# 1. Создать и активировать виртуальное окружение (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Проверить конфигурацию Django
USE_SQLITE=true python manage.py check

# 4. Применить миграции (SQLite)
USE_SQLITE=true python manage.py migrate

# 5. Запустить сервер
USE_SQLITE=true python manage.py runserver 127.0.0.1:8000
```

Приложение доступно по адресу http://127.0.0.1:8000/

## Запуск тестов

```bash
source .venv/bin/activate
USE_SQLITE=true python manage.py test
```

## Окружение

- `USE_SQLITE=true` — использовать SQLite и выполнять задачи Celery синхронно (без Redis-брокера).
- `DJANGO_SECRET_KEY` — секретный ключ Django (по умолчанию небезопасное значение для разработки).
- `TINKOFF_TOKEN` — токен Tinkoff Invest API (по умолчанию пустой; рыночные данные недоступны).

## Рыночные данные (Tinkoff Invest)

Приложение запускается и работает без установленного SDK `tinkoff-investments` и без токена:
- котировки и график недоступны, на страницах выводится сообщение об этом;
- фоновая задача обновления цен пропускает акции и сохраняет старые цены в БД.

При установке реального SDK и задании `TINKOFF_TOKEN` функции `dashboard/services/market_data.py` и `dashboard/services/graph.py` начнут использовать настоящий API Tinkoff Invest.

## PostgreSQL (Docker, продакшен)

```bash
# Установить драйвер PostgreSQL отдельно (не в requirements.txt):
pip install psycopg2-binary

docker-compose -f docker-compose.yml up   # PostgreSQL + Redis
python manage.py migrate
python manage.py add_shares               # первоначальная загрузка списка акций
celery -A config beat                     # Celery Beat
celery -A config worker -l info           # Celery Worker
```

TINKOFF_TOKEN задаётся через окружение (читается в config/settings.py): `export TINKOFF_TOKEN="..."`

## API

- `/api/v1/shares/` — работа с акциями (CRUD, фильтрация, поиск, сортировка, пагинация).

## Наблюдения

После входа откройте «Наблюдения» (/observations/). Если справочник пуст, добавьте акцию через страницу /create. В списке наблюдений выберите акцию и задайте положительную цель с точностью до копейки. Цель можно изменить, а наблюдение удалить. Список и история уведомлений доступны только владельцу.

Миграция 0008 создаёт таблицы Observation и Notification. После получения котировки задача update_last_price в одной транзакции обновляет цену, проверяет цели и сохраняет уведомления. Первое достижение или превышение цели создаёт запись с временем, целевой и фактической ценой. Следующая запись возможна после падения ниже цели. Изменённая цель проверяется заново при следующей котировке. Пропуск котировки сохраняет прежнее состояние.

Для локальной проверки без внешнего API запустите тесты из раздела выше. В тестовом сценарии цель 100 и последовательность цен 99 → 100 → 101 → 98 → 100 дают два уведомления. Для автоматического получения реальных котировок нужны SDK, токен и запущенные Beat и Worker.
