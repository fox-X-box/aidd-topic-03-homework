# Анализ исходного кода приложения Investing Demo

## 1. Назначение приложения

`Investing Demo` — веб-приложение для учета и мониторинга биржевых акций (инструментов). Приложение позволяет:

- хранить список акций с идентификаторами (`figi`, `isin`, `uid`), наименованием компании, тикером, валютой, текущей ценой (`last_price`), направлением тренда (`is_trend_high`) и временем последнего обновления (`updated_at`);
- просматривать список акций и детальную информацию по отдельной акции;
- отображать исторический график цен (свечи за 180 дней) через Plotly;
- добавлять, редактировать и удалять акции (для авторизованных пользователей);
- регистрировать и авторизовывать пользователей;
- работать с акциями через REST API (CRUD, фильтрация, поиск, сортировка, пагинация);
- периодически обновлять текущие цены акций и тренд через фоновую задачу Celery, обращаясь к внешнему API Tinkoff Invest.

Источник: `README.md`, `dashboard/models.py` (класс `Share`), `dashboard/views.py`, `dashboard/api/v1/views.py`, `dashboard/tasks.py`.

## 2. Технологический стек

- **Язык:** Python.
- **Веб-фреймворк:** Django 4.1.7 (`requirements.txt`, `config/settings.py`).
- **База данных:** PostgreSQL (`config/settings.py` `DATABASES`, `docker-compose.yml` сервис `db`).
- **Брокер сообщений (не кэш Django):** Redis (`config/settings.py` `CELERY_BROKER_URL`, `docker-compose.yml` сервис `redis`). Redis используется как брокер сообщений для Celery; в проекте не используется как кэш Django.
- **Фоновые задачи:** Celery 5.2.7 (`config/celery.py`, `dashboard/tasks.py`), Celery Beat (`config/celery.py` `beat_schedule`).
- **REST API:** Django REST Framework 3.14.0, `django-filter` (`config/settings.py` `INSTALLED_APPS`, `REST_FRAMEWORK`).
- **Внешний сервис рынка данных:** Tinkoff Invest API (`tinkoff-investments==0.2.0b50`, `dashboard/services/market_data.py`, `dashboard/services/graph.py`, `dashboard/management/commands/add_shares.py`).
- **Визуализация:** Plotly 5.13.1 (`dashboard/services/graph.py`) — библиотека для построения графика (линия по ценам закрытия) и генерации HTML-фрагмента через `plot(..., output_type="div")`, который вставляется в шаблон `dashboard/templates/dashboard/detail.html` через `{% autoescape off %}{{ plot_div }}`.
- **Формы/шаблоны:** `django-crispy-forms` + `crispy-bootstrap3`, Bootstrap CSS (статика в `dashboard/static`, `user/static`).
- **Интерфейсы запуска Django:** WSGI/ASGI — стандартные интерфейсы для запуска Django веб-серверами; `config/wsgi.py::application` и `config/asgi.py::application` — callable для WSGI/ASGI-серверов (Django по умолчанию синхронный, через WSGI).
- **ORM/миграции:** Django ORM, миграции в `dashboard/migrations/`.

## 3. Структура проекта

```
.
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── README.md
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   ├── wsgi.py / asgi.py
├── dashboard/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   ├── tasks.py
│   ├── services/market_data.py, graph.py
│   ├── api/urls.py, api/v1/{urls,router,views,serializer}.py
│   ├── management/commands/add_shares.py
│   ├── templates/dashboard/
│   ├── static/dashboard/css/
│   ├── migrations/
│   └── tests.py
└── user/
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── forms.py
    ├── templates/user/
    └── static/user/css/
```

Источник: вывод `find`, `config/urls.py`, `dashboard/urls.py`, `user/urls.py`.

## 4. Архитектура и взаимодействие компонентов

- **Маршрутизация:** `config/urls.py` подключает `admin/`, `dashboard.urls` (префикс ``) и `user` (префикс `user`). `dashboard/urls.py` объявляет маршруты CRUD и `api/` (включает `dashboard/api/urls.py` → `dashboard/api/v1/urls.py` → `router.urls`).
- **Представления dashboard:** `dashboard/views.py`: `ShareListView` (ListView), `ShareDetailView` (View), `ShareCreateView`/`ShareUpdateView`/`ShareDeleteView` (CBV с `IsUserAuthenticatedMixin`).
- **Представления user:** `user/views.py`: `AuthView`, `RegistrationView`, `LogoutView`.
- **Сервисный слой:** `dashboard/services/market_data.py::get_last_data(share)` и `dashboard/services/graph.py::get_graph(share)` инкапсулируют обращения к Tinkoff Invest API и Plotly. `get_last_data` вызывает `client.market_data.get_last_prices(figi=[share.figi])`, берёт `resp.last_prices.pop()` и возвращает `[resp.price.units, resp.time]` — то есть целую часть цены (`units`, без дробной части `nano`) и время последней цены. `get_graph` итерирует `client.get_all_candles(...)`, собирает `x_data = candle.time.date()` и `y_data = candle.close.units` — то есть дату свечи и целую часть цены закрытия (`units`).
- **Фоновые задачи:** `dashboard/tasks.py::update_last_price` (Celery task) перебирает `Share.objects.all()`, вызывает `get_last_data`, обновляет `last_price`/`is_trend_high` через `Share.objects.filter(id=share.id).update(...)`. Расписание задано в `config/celery.py::app.conf.beat_schedule` ("add-every-5-min", schedule 10.0 секунд).
- **Инициализация данных:** `dashboard/management/commands/add_shares.py::Command.handle` загружает список инструментов из Tinkoff API и сохраняет через `Share.objects.get_or_create(...)`.
- **Админка:** `dashboard/admin.py::ShareAdmin` регистрирует модель `Share`.
- **API:** `dashboard/api/v1/views.py::ShareViewSet` (ModelViewSet) с `ShareFilter`, `ShareSerializer`; маршруты генерируются `DefaultRouter` в `dashboard/api/v1/router.py`.
- **Авторизация:** Django auth (`django.contrib.auth`), пользовательская модель — стандартная (`user/models.py::User = get_user_model()`). `IsUserAuthenticatedMixin` в `dashboard/views.py` проверяет `request.user.is_authenticated`.
## 5. Используемые библиотеки и внешние сервисы

**Библиотеки (основные, из `requirements.txt`):**
- Django 4.1.7, asgiref 3.6.0
- djangorestframework 3.14.0, django-filter 22.1
- crispy_forms / crispy-bootstrap3
- psycopg2-binary 2.9.5 (PostgreSQL)
- celery 5.2.7, kombu, billiard, vine, amqp, redis 4.5.1
- tinkoff 0.1.1, tinkoff-investments 0.2.0b50
- plotly 5.13.1
- grpcio 1.51.3, protobuf 3.20.3
- pydantic 1.10.6, python-dateutil, pytz, tenacity, cachetools, sqlparse и др.

**Внешние сервисы:**
- PostgreSQL (БД приложения) — `config/settings.py` `DATABASES`, `docker-compose.yml`.
- Redis (брокер Celery) — `config/settings.py` `CELERY_BROKER_URL`, `docker-compose.yml`.
- Tinkoff Invest API (котировки, свечи, список инструментов) — `dashboard/services/market_data.py`, `dashboard/services/graph.py`, `dashboard/management/commands/add_shares.py`.

## 6. Модель данных

### Сущность `Share` (`dashboard/models.py::Share`, таблица `dashboard_share`)

Атрибуты (поля модели):
- `id` — `BigAutoField`, PK (неявное, `DEFAULT_AUTO_FIELD = BigAutoField`).
- `figi` — `CharField(max_length=255, unique=True)`.
- `isin` — `CharField(max_length=255)`.
- `name` — `CharField(max_length=255, verbose_name="Наименование компании")`.
- `ticker` — `CharField(max_length=10, unique=True, verbose_name="Тикер")`.
- `currency` — `CharField(max_length=20, verbose_name="Валюта")`.
- `uid` — `CharField(max_length=255, unique=True)`.
- `last_price` — `FloatField(blank=True, null=True, verbose_name="Текущая цена")`.
- `is_trend_high` — `BooleanField(blank=True, null=True, verbose_name="Растет цена")`.
- `updated_at` — `DateTimeField(auto_now=True, blank=True, null=True)`.

Связи: у модели `Share` нет явных связей (`ForeignKey`/`ManyToMany`/`OneToOne`) с другими сущностями. В API-сериализаторе `dashboard/api/v1/serializer.py::ShareSerializer` используются поля `id, figi, isin, name, ticker, currency, last_price, is_trend_high, updated_at`.

### Сущность `User` (стандартная модель Django auth)

- `user/models.py::User = get_user_model()` — алиас на стандартную модель `django.contrib.auth.models.User` (таблица `auth_user`). Отдельной модели в проекте нет.
- Используется для регистрации/авторизации (`user/views.py`, `user/forms.py::RegistrationForm.save` вызывает `User.objects.create_user(email, email, password)`).

Связи между `Share` и `User` отсутствуют: владение акциями пользователями не моделируется.

## 7. Пример реального запроса: от URL до ответа

Рассмотрим запрос `GET /` (список акций).

1. **WSGI/ASGI-точка входа:** запрос принимается Django-приложением (`config/wsgi.py::application` / `config/asgi.py::application`).
2. **Корневая маршрутизация:** `config/urls.py` — `path("", include("dashboard.urls"))` направляет запрос в `dashboard/urls.py`.
3. **Маршрут приложения:** `dashboard/urls.py` — `path("", ShareListView.as_view(), name="index")`.
4. **Представление:** `dashboard/views.py::ShareListView` (наследник `ListView`), `model = Share`, `template_name = "dashboard/list.html"`, `paginate_by = 100`, `ordering = ["name"]`.
5. **Обращение к БД:** `ListView` формирует queryset `Share.objects.all()` (эквивалентно `SELECT ... FROM dashboard_share ORDER BY name LIMIT 100 OFFSET 0`), выполняемый через Django ORM к PostgreSQL (`config/settings.py` `DATABASES["default"]`). Это место обращения к БД: `dashboard/views.py::ShareListView` (через `model = Share` и стандартный `get_queryset` ListView).
6. **Рендеринг:** `dashboard/templates/dashboard/list.html` использует `share_list`, `page_obj`, `user.is_authenticated`.
7. **Ответ:** при успешной обработке — HTTP 200 с HTML-страницей.

Альтернативный пример `GET /api/v1/shares/`:
1. `config/urls.py` → `dashboard/urls.py` `path("api/", include("dashboard.api.urls"))`.
2. `dashboard/api/urls.py` → `include("dashboard.api.v1.urls")`.
3. `dashboard/api/v1/urls.py` → `include(router.urls)` (router из `dashboard/api/v1/router.py`).
4. `dashboard/api/v1/router.py` — `router.register(r"shares", ShareViewSet)` → маршрут `/shares/`.
5. `dashboard/api/v1/views.py::ShareViewSet.list` → `queryset = Share.objects.all()` (обращение к БД PostgreSQL) → фильтрация/сортировка/пагинация → `dashboard/api/v1/serializer.py::ShareSerializer` → JSON-ответ.

Пример `GET /<pk>` (деталь):
1. `dashboard/urls.py` — `path("<int:pk>", ShareDetailView.as_view(), name="detail")`.
2. `dashboard/views.py::ShareDetailView.get` — `share = Share.objects.get(id=pk)` (обращение к БД).
3. `dashboard/services/graph.py::get_graph(share)` — обращение к Tinkoff Invest API (`client.get_all_candles`) и Plotly.
4. Рендеринг `dashboard/templates/dashboard/detail.html` с `plot_div`, `share`.

## 8. Примечания

- В `config/settings.py` `TINKOFF_TOKEN = ""`, `SECRET_KEY = ""`, поэтому для реальной работы требуется заполнить токен и секретный ключ, а также запустить PostgreSQL и Redis (см. `docker-compose.yml`).
- Фоновая задача обновления цен запускается каждые 10 секунд (`config/celery.py`), что является потенциально частым расписанием.
- Миграция `0004_add_last_price.py` содержит опечатки в `verbose_name` (например, `name` → "Валюта", `ticker` → "Ти"), исправленные последующими миграциями `0005`, `0006`.
