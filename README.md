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
USE_SQLITE=true python manage.py test dashboard.tests
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
docker-compose -f docker-compose.yml up   # PostgreSQL + Redis
python manage.py add_shares               # первоначальная загрузка списка акций
celery -A config beat                     # Celery Beat
celery -A config worker -l info           # Celery Worker
```

TINKOFF_TOKEN указывается в `config/settings.py`.

## API

- `/api/v1/shares/` — работа с акциями (CRUD, фильтрация, поиск, сортировка, пагинация).
