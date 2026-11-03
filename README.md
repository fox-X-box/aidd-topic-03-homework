# Investing Demo

## Локальный запуск

Требуется Python 3.9 или новее. Для локальной разработки по умолчанию используется SQLite, поэтому PostgreSQL не обязателен.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

Главная страница: <http://127.0.0.1:8000/>. REST API: <http://127.0.0.1:8000/api/v1/shares/>.

У локальной конфигурации есть ключ и `DEBUG` только для разработки. Для другого окружения задайте `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` и `DJANGO_ALLOWED_HOSTS`.

## PostgreSQL

Чтобы использовать описанный в `docker-compose.yml` PostgreSQL, запустите БД и перед запуском Django задайте параметры подключения:

```sh
docker compose up -d db
export DB_ENGINE=django.db.backends.postgresql
export DB_NAME=investing
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_HOST=localhost
export DB_PORT=5432
python manage.py migrate
```

## Данные Tinkoff Invest API

Tinkoff SDK не входит в базовые зависимости: зафиксированная в исходном проекте версия `tinkoff-investments==0.2.0b50` недоступна в используемом Python-пакетном индексе. Чтобы включить внешний источник, установите совместимый SDK из доступного вам индекса/артефакта. Без SDK веб-приложение запускается, но запрос графика, загрузка инструментов и получение котировок завершаются явной ошибкой с указанием установить SDK.

Для запроса внешних инструментов и котировок также задайте токен в окружении, а не в исходном коде:

```sh
export TINKOFF_TOKEN=your-token
python manage.py add_shares
```

## Фоновые обновления цен

Celery использует Redis по адресу `redis://127.0.0.1:6379/0` по умолчанию. Запустите Redis, затем в отдельных терминалах запустите Beat и Worker:

```sh
celery -A config beat
celery -A config worker -l info
```

Задача `dashboard.tasks.update_last_price` настроена на запуск раз в 10 секунд. Адрес брокера можно изменить переменной `CELERY_BROKER_URL`.
