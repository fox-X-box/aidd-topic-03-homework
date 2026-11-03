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
## 9. Восстановленные функциональные требования

### Веб-интерфейс

FR-01. При обращении к маршруту `""` система возвращает HTML-страницу со списком акций, отсортированных по наименованию компании (`ordering = ["name"]`), с пагинацией по 100 записей на страницу. Подтверждение: `dashboard/urls.py` `path("", ShareListView.as_view(), name="index")`; `dashboard/views.py` `ShareListView` (`model = Share`, `paginate_by = 100`, `ordering = ["name"]`, `template_name = "dashboard/list.html"`).

FR-02. На странице списка для каждой акции отображаются тикер (ссылка на детальную страницу), наименование, ISIN, текущая цена с валютой и цвет фона ячейки цены в зависимости от `is_trend_high` (зелёный при True, красный при False/None). Подтверждение: `dashboard/templates/dashboard/list.html`.

FR-03. Для авторизованного пользователя на странице списка отображаются кнопки «Добавить», «Редактировать», «Удалить»; для анонимного пользователя — не отображаются. Подтверждение: `dashboard/templates/dashboard/list.html` (`{% if user.is_authenticated %}`); `dashboard/views.py` `ShareListView`.

FR-04. При обращении к `"/<int:pk>"` система загружает акцию по id и отображает детальную страницу с наименованием, текущей ценой, валютой, временем последнего обновления и HTML-графиком исторических цен (свечи за 180 дней, дневной интервал). Подтверждение: `dashboard/urls.py` `path("<int:pk>", ShareDetailView.as_view(), name="detail")`; `dashboard/views.py` `ShareDetailView.get` (`Share.objects.get(id=pk)`); `dashboard/services/graph.py` `get_graph` (`from_=now() - timedelta(days=180)`, `interval=CandleInterval.CANDLE_INTERVAL_DAY`); `dashboard/templates/dashboard/detail.html`.

FR-05. При обращении к `"/create"` авторизованным пользователем отображается форма создания акции; `ShareModelForm` использует `fields = "__all__"`, но поле `updated_at` имеет `auto_now=True` и не доступно для ввода; доступные для ввода поля: `figi`, `isin`, `name`, `ticker`, `currency`, `uid`, `last_price`, `is_trend_high`. При успешной отправке создаётся запись и выполняется перенаправление на главную страницу. Подтверждение: `dashboard/urls.py` `path("create", ShareCreateView.as_view(), name="create")`; `dashboard/views.py` `ShareCreateView` (`IsUserAuthenticatedMixin`, `CreateView`, `form_class = ShareModelForm`, `success_url = reverse_lazy("dashboard:index")`); `dashboard/forms.py` `ShareModelForm` (`fields = "__all__"`); `dashboard/models.py` `Share` (`updated_at = DateTimeField(auto_now=True, ...)`).

FR-06. При обращении к `"/update/<int:pk>"` авторизованным пользователем отображается форма редактирования существующей акции; при успешной отправке изменения сохраняются и выполняется перенаправление на главную страницу. Подтверждение: `dashboard/urls.py` `path("update/<int:pk>", ShareUpdateView.as_view(), name="update")`; `dashboard/views.py` `ShareUpdateView`.

FR-07. При обращении к `"/delete/<int:pk>"` авторизованным пользователем отображается страница подтверждения удаления; при подтверждении запись удаляется и выполняется перенаправление на главную страницу. Подтверждение: `dashboard/urls.py` `path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete")`; `dashboard/views.py` `ShareDeleteView`; `dashboard/templates/dashboard/delete.html`.

FR-08. Анонимный пользователь при обращении к `"/create"`, `"/update/<pk>"`, `"/delete/<pk>"` перенаправляется на главную страницу без показа формы/удаления. Подтверждение: `dashboard/views.py` `IsUserAuthenticatedMixin.test_func` (`request.user.is_authenticated`), `handle_no_permission` (статический метод, возвращает `redirect("dashboard:index")`).

FR-09. Пользователь может зарегистрироваться по email и паролю: при совпадающих паролях и отсутствии пользователя с таким email создаётся пользователь (username = email) и выполняется вход с перенаправлением на главную страницу. Подтверждение: `user/urls.py` `path("registration/", RegistrationView.as_view(), name="registration")`; `user/views.py` `RegistrationView.post`; `user/forms.py` `RegistrationForm.clean` (проверка совпадения паролей и уникальности email), `RegistrationForm.save` (`User.objects.create_user(email, email, password)`).

FR-10. Пользователь может войти по email и паролю: при корректных данных выполняется вход и перенаправление на главную; при некорректных — страница входа с сообщением об ошибке. Подтверждение: `user/urls.py` `path("login/", AuthView.as_view(), name="auth")`; `user/views.py` `AuthView.post` (`authenticate(request, username=form.data["email"].lower(), password=...)`, `login(request, user)`); `user/templates/user/auth.html`.

FR-11. Пользователь может выйти: обращение к фактическому URL `/userlogout/` (префикс `user` из `config/urls.py` `path("user", include("user.urls"))` заканчивается на букву, а `logout/` из `user/urls.py` начинается с буквы, поэтому слэш между ними не добавляется) завершает сессию и перенаправляет на главную страницу. Подтверждение: `config/urls.py` `path("user", include("user.urls"))`; `user/urls.py` `path("logout/", LogoutView.as_view(), name="logout")`; `user/views.py` `LogoutView.get` (`logout(request)`, `redirect("dashboard:index")`).
### REST API

FR-12. API доступно по префиксу `"/api/v1/"` и предоставляет CRUD для ресурса `shares`: GET список, GET по id, POST создание, PUT/PATCH обновление, DELETE удаление. Подтверждение: `config/urls.py` `path("", include("dashboard.urls"))`; `dashboard/urls.py` `path("api/", include("dashboard.api.urls"))`; `dashboard/api/urls.py`; `dashboard/api/v1/urls.py` `path("", include(router.urls))`; `dashboard/api/v1/router.py` `router.register(r"shares", ShareViewSet)`; `dashboard/api/v1/views.py` `ShareViewSet` (`ModelViewSet`).

FR-13. Список API возвращает объект с полем `results`; по умолчанию `LimitOffsetPagination` возвращает `PAGE_SIZE = 100` записей на страницу; параметр `limit` позволяет запросить иной размер, максимальный размер не ограничен настройками (`max_limit` не задан). Подтверждение: `config/settings.py` `REST_FRAMEWORK` (`DEFAULT_PAGINATION_CLASS = "rest_framework.pagination.LimitOffsetPagination"`, `PAGE_SIZE = 100`); `dashboard/api/v1/views.py` `ShareViewSet`.

FR-14. API поддерживает фильтрацию списка по точному совпадению полей `name` и `ticker`. Подтверждение: `dashboard/api/v1/views.py` `ShareFilter` (`Meta.fields = ("name", "ticker")`), `filter_backends = (..., filters.DjangoFilterBackend, ...)`.

FR-15. API поддерживает сортировку по полям `name` и `ticker` (параметр `ordering`). Подтверждение: `dashboard/api/v1/views.py` `ordering_fields = ["name", "ticker"]`, `filter_backends` включает `OrderingFilter`.

FR-16. API поддерживает поиск по полю `name` с использованием регулярного выражения (префикс `$` в `search_fields` означает `iregex`) (параметр `search`). Подтверждение: `dashboard/api/v1/views.py` `search_fields = ["$name"]`, `filter_backends` включает `SearchFilter`.

FR-17. Ответ API-сериализатора включает поля `id`, `figi`, `isin`, `name`, `ticker`, `currency`, `last_price`, `is_trend_high`, `updated_at` (поле `uid` не включено). Подтверждение: `dashboard/api/v1/serializer.py` `ShareSerializer` `Meta.fields`.

FR-18. При создании/обновлении через API:
- сериализатор `ShareSerializer` проверяет обязательность и типы полей, включённых в `fields` (`figi`, `isin`, `name`, `ticker`, `currency`, `last_price`, `is_trend_high`); поле `updated_at` доступно только для чтения (read-only, `auto_now`), поле `uid` не входит в `fields`, поэтому API не может его задать;
- уникальность `figi` и `ticker` проверяется и сериализатором (UniqueValidator, генерируемый DRF для unique-полей модели), и ограничениями БД; уникальность `uid` обеспечивается только ограничениями БД, так как `uid` отсутствует в сериализаторе.
При нарушении обязательности/типов полей сериализатора возвращается 400 Bad Request. Подтверждение: `dashboard/models.py` `Share` (`unique` для `figi`/`ticker`/`uid`, обязательные поля, `uid = CharField(max_length=255, unique=True)` без default, `updated_at = DateTimeField(auto_now=True, ...)`); `dashboard/api/v1/serializer.py` `ShareSerializer` (`Meta.fields` без `uid`); `dashboard/api/v1/views.py` `ShareViewSet`; `dashboard/tests.py` `test_share_create_invalid`, `test_share_update_invalid`.
### Права доступа

FR-19. Веб-интерфейс: просмотр списка и детали доступен анонимным пользователям; создание, редактирование и удаление требуют аутентификации. Подтверждение: `dashboard/views.py` `ShareListView` и `ShareDetailView` без миксина; `ShareCreateView`, `ShareUpdateView`, `ShareDeleteView` с `IsUserAuthenticatedMixin`.

FR-20. REST API: так как `permission_classes` не заданы, все операции CRUD доступны без аутентификации (по умолчанию AllowAny). Подтверждение: `dashboard/api/v1/views.py` `ShareViewSet` без `permission_classes`; `config/settings.py` `REST_FRAMEWORK` без `DEFAULT_PERMISSION_CLASSES`.

FR-21. Административный интерфейс Django (префикс `admin/`) доступен только пользователям с правами staff (стандартное поведение Django admin). Подтверждение: `config/urls.py` `path("admin/", admin.site.urls)`; `dashboard/admin.py` `@admin.register(Share)` `ShareAdmin`.

### Загрузка данных и фоновые задачи

FR-22. Команда `manage.py add_shares` подключается к Tinkoff Invest API, получает список инструментов `shares()` и для каждого создаёт запись `Share`, если записи с такими же `figi`, `name`, `isin`, `ticker`, `currency`, `uid` ещё нет (`get_or_create`). Подтверждение: `dashboard/management/commands/add_shares.py` `Command.handle`; `dashboard/models.py` `Share`.

FR-23. Celery Beat запускает задачу `dashboard.tasks.update_last_price` каждые 10 секунд (`schedule = 10.0`). Подтверждение: `config/celery.py` `app.conf.beat_schedule` (`"add-every-5-min"`: `task = "dashboard.tasks.update_last_price"`, `schedule = 10.0`).

FR-24. Задача `update_last_price` для каждой акции запрашивает текущую цену через Tinkoff API, определяет тренд (если предыдущая цена больше новой — False, иначе True; при ошибке сравнения — True) и обновляет `last_price` и `is_trend_high` в БД. Подтверждение: `dashboard/tasks.py` `update_last_price`; `dashboard/services/market_data.py` `get_last_data`.

FR-25. При ошибке получения данных для отдельной акции задача логирует ошибку и продолжает обработку остальных акций. Подтверждение: `dashboard/tasks.py` (`try/except` вокруг итерации, `logger.error(e)`).

### Неоднозначности, противоречия и возможные дефекты

- API не защищено правами доступа, в отличие от веб-интерфейса (FR-19 vs FR-20). Подтверждение: `dashboard/api/v1/views.py` `ShareViewSet` без `permission_classes`; `dashboard/views.py` `IsUserAuthenticatedMixin`.
- `RegistrationView.post` при невалидной форме обращается к `form.errors["__all__"].data[0].message`; при ошибках только полей возникает `KeyError`. Подтверждение: `user/views.py` `RegistrationView.post`.
- `AuthView.post` использует `form.data["email"]` без проверки валидности формы; пустой запрос может вызвать `KeyError`; аутентификация использует `email.lower()` как username. Подтверждение: `user/views.py` `AuthView.post`.
- `ShareDetailView.get` использует `Share.objects.get(id=pk)`; при отсутствии записи выбрасывается `DoesNotExist` (HTTP 500, а не 404). Подтверждение: `dashboard/views.py` `ShareDetailView.get`.
- `get_graph` вызывается при каждом просмотре детали и обращается к Tinkoff Invest API; при пустом токене/ошибке возможен HTTP 500. Подтверждение: `dashboard/services/graph.py` `get_graph`; `config/settings.py` `TINKOFF_TOKEN = ""`.
- `get_last_data` берёт только `price.units` (целую часть), игнорируя `nano`; `resp.last_prices.pop()` предполагает непустой список (иначе `IndexError`). Подтверждение: `dashboard/services/market_data.py` `get_last_data`.
- `update_last_price`: при `share.last_price is None` сравнение `share.last_price > last_price` выбрасывает `TypeError`, который перехватывается и устанавливает `is_trend_high = True`; переменная `detetime` не используется. Подтверждение: `dashboard/tasks.py` `update_last_price`.
- `add_shares`: `get_or_create` с lookup по всем полям; при существующей записи с тем же `figi`, но отличиями других полей возможен дубликат/`IntegrityError` из-за уникальных ограничений; команда не обновляет существующие записи. Подтверждение: `dashboard/management/commands/add_shares.py` `Command.handle`.
- `ShareSerializer` не включает `uid`, поэтому API не может его задать; `uid` получает значение по умолчанию `''`, первый POST может пройти, повторный POST нарушает уникальность `uid` и приводит к ошибке БД. Подтверждение: `dashboard/api/v1/serializer.py` `ShareSerializer`; `dashboard/models.py` `Share.uid`.
- `search_fields = ["$name"]` использует регулярное выражение (`iregex`), а не полнотекстовый поиск; поведение зависит от поддержки regex в СУБД. Подтверждение: `dashboard/api/v1/views.py` `ShareViewSet`.
- Настройки `SECRET_KEY = ""`, `DEBUG = True`, `ALLOWED_HOSTS = []`, `TINKOFF_TOKEN = ""` не готовы к продакшену. Подтверждение: `config/settings.py`.
- Celery Beat запускает задачу каждые 10 секунд при имени `"add-every-5-min"`, несоответствие имени и расписания. Подтверждение: `config/celery.py` `app.conf.beat_schedule`.
- Миграция `0004_add_last_price.py` содержит опечатки в `verbose_name` (`name` → «Валюта», `ticker` → «Ти»), исправленные миграциями `0005`, `0006`. Подтверждение: `dashboard/migrations/0004_add_last_price.py`, `0005_add_verbose_name.py`, `0006_add_verbose_name.py`.
