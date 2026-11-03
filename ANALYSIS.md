# Анализ исходного кода Investing Demo

## Назначение приложения

Investing Demo — веб-приложение для просмотра и ведения списка акций. Оно показывает тикер, название, ISIN, валюту, последнюю цену и направление ее изменения; позволяет просматривать карточку инструмента с графиком исторических цен. Для пользователей предусмотрены регистрация, вход и выход. Данные об акциях доступны также через REST API, а отдельная фоновая задача периодически получает цены из Tinkoff Invest API.

Такое назначение следует из модели `Share` и представлений в [`dashboard/models.py`](dashboard/models.py) и [`dashboard/views.py`](dashboard/views.py), шаблонов списка и карточки в [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html) и [`dashboard/templates/dashboard/detail.html`](dashboard/templates/dashboard/detail.html), а также интеграции с рыночными данными в [`dashboard/services/market_data.py`](dashboard/services/market_data.py) и [`dashboard/tasks.py`](dashboard/tasks.py).

## Технологический стек и внешние зависимости

- **Python и Django 4.1.7** — серверная платформа, маршрутизация, ORM, шаблоны, аутентификация и административный интерфейс. Настройки проекта находятся в [`config/settings.py`](config/settings.py), запуск команд Django — в [`manage.py`](manage.py).
- **PostgreSQL** — основная реляционная база данных. Подключение `investing` задается в `DATABASES` файла [`config/settings.py`](config/settings.py); контейнер базы описан в [`docker-compose.yml`](docker-compose.yml).
- **Django REST Framework 3.14.0** — REST API с сериализацией, CRUD-представлением, пагинацией и фильтрацией.
- **django-filter** — фильтрация API по `name` и `ticker`; вместе с DRF подключен в [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py).
- **Celery 5.2.7 и Redis** — выполнение фоновой задачи и брокер сообщений. `redis==4.5.1` в [`requirements.txt`](requirements.txt) — версия Python-библиотеки-клиента Redis (redis-py), а не версия Redis-сервера. Адрес брокера `redis://127.0.0.1:6379/0` установлен в [`config/settings.py`](config/settings.py), конфигурация приложения и расписание — в [`config/celery.py`](config/celery.py). В коде интервал задачи указан как 10 секунд (`schedule: 10.0`); ключ расписания при этом называется `add-every-5-min`. В [`docker-compose.yml`](docker-compose.yml) сервис задан как `image: redis` без тега или версии, поэтому версия серверного образа явно не зафиксирована.
- **Tinkoff Invest API** (`tinkoff-investments`) — внешний источник списка инструментов, последних цен и свечей. Клиенты API используются в [`dashboard/management/commands/add_shares.py`](dashboard/management/commands/add_shares.py), [`dashboard/services/market_data.py`](dashboard/services/market_data.py) и [`dashboard/services/graph.py`](dashboard/services/graph.py). Токен ожидается в `TINKOFF_TOKEN` в [`config/settings.py`](config/settings.py).
- **Plotly 5.13.1** — построение графика исторических цен; HTML-фрагмент графика формируется в `get_graph` файла [`dashboard/services/graph.py`](dashboard/services/graph.py) и выводится в шаблоне карточки.
- **django-crispy-forms и crispy-bootstrap3**, локальные CSS-файлы Bootstrap — оформление форм и страниц. HTML-шаблоны приложений размещены в `dashboard/templates/` и `user/templates/`.
- В `requirements.txt` также зафиксированы `psycopg2-binary` (драйвер PostgreSQL), `pydantic`, `grpcio`, `protobuf` и другие зависимости SDK/окружения. Полный список и версии приведены в [`requirements.txt`](requirements.txt).

## Структура проекта

- [`config/`](config/) — настройки Django, корневая маршрутизация, WSGI/ASGI-точки входа и инициализация Celery (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `celery.py`).
- [`dashboard/`](dashboard/) — основная предметная область акций:
  - `models.py` — модель акции `Share`;
  - `views.py`, `urls.py`, `forms.py` — HTML-страницы списка, карточки и операций управления;
  - `api/` — REST API, маршруты, сериализатор и набор представлений;
  - `services/` — интеграции для получения рыночных данных и построения графика;
  - `tasks.py` — периодическое обновление цен через Celery;
  - `management/commands/add_shares.py` — загрузка инструментов из Tinkoff API;
  - `migrations/` — история схемы БД;
  - `templates/`, `static/` — HTML-шаблоны и стили.
- [`user/`](user/) — формы и представления регистрации, аутентификации и выхода; HTML-шаблоны и стили пользовательской части. Отдельная модель пользователя здесь не объявлена: [`user/models.py`](user/models.py) получает стандартную модель через `get_user_model()`.
- [`manage.py`](manage.py) — командная точка входа для Django.
- [`docker-compose.yml`](docker-compose.yml) — описание контейнеров PostgreSQL и Redis.
- [`requirements.txt`](requirements.txt) — зависимости Python; [`README.md`](README.md) содержит команды запуска и основные адреса.

## Архитектура и взаимодействие компонентов

Приложение использует Django-подход: URL-конфигурация направляет запрос в представление, представление обращается к модели через ORM и возвращает HTML-шаблон либо ответ REST API. Django настраивает шаблоны с поиском шаблонов внутри приложений (`APP_DIRS=True`) и включает сессии и middleware аутентификации в [`config/settings.py`](config/settings.py).

Корневой URLConf в [`config/urls.py`](config/urls.py) подключает административный интерфейс по `admin/`, основное приложение по корню и пользовательские маршруты по `user`. Внутри `dashboard` URL-маршруты разделяются между HTML-страницами и API. HTML-страницы используют `ShareListView`, `ShareDetailView`, `ShareCreateView`, `ShareUpdateView` и `ShareDeleteView` из [`dashboard/views.py`](dashboard/views.py). Для создания и редактирования применяется `ShareModelForm` из [`dashboard/forms.py`](dashboard/forms.py); операции записи выполняются стандартными Django generic views через модель `Share`.

### Доступ к HTML-операциям с акциями

Гостю доступны просмотр списка (`ShareListView`, URL `/`) и карточки акции (`ShareDetailView`, URL `/<int:pk>`). Добавление (`ShareCreateView`), редактирование (`ShareUpdateView`) и удаление (`ShareDeleteView`) требуют входа: все три представления используют `IsUserAuthenticatedMixin`, который проверяет `request.user.is_authenticated` и для гостя перенаправляет на список акций. Шаблон списка также показывает кнопку добавления и ссылки управления только при `user.is_authenticated` (`dashboard/templates/dashboard/list.html`), но фактическую защиту операций обеспечивает именно миксин в [`dashboard/views.py`](dashboard/views.py).

API построено на `DefaultRouter` и `ShareViewSet` (`dashboard/api/v1/router.py`, [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py)). `ModelViewSet` предоставляет стандартные действия чтения, создания, изменения и удаления модели; `ShareSerializer` определяет поля REST-представления в [`dashboard/api/v1/serializer.py`](dashboard/api/v1/serializer.py). Фильтр `ShareFilter` позволяет отбирать данные по названию и тикеру; также включены поиск по названию и сортировка по названию или тикеру. Глобальный размер страницы DRF — 100 элементов (`PAGE_SIZE` в [`config/settings.py`](config/settings.py)).

Сервисный слой отделяет обращения к внешнему API от представлений и задачи: `get_last_data` запрашивает актуальную цену, `get_graph` загружает дневные свечи за последние 180 дней и строит HTML-график. Celery-задача `update_last_price` обходит записи `Share`, получает цену для каждой акции и обновляет `last_price` и `is_trend_high`. Расписание задачи задано в `app.conf.beat_schedule` в [`config/celery.py`](config/celery.py); запуск Beat и Worker описан в [`README.md`](README.md).

В обработке цены оба метода используют только целую часть значения Tinkoff Invest API: `get_last_data` возвращает `resp.price.units`, а `get_graph` добавляет к графику `candle.close.units`. Дробная часть цены `nano` в этих местах не учитывается; поэтому сохраненная текущая цена и значения на графике не содержат дробную часть API. Реализация находится в [`dashboard/services/market_data.py`](dashboard/services/market_data.py) и [`dashboard/services/graph.py`](dashboard/services/graph.py).

Пользовательская часть использует `AuthView`, `RegistrationView` и `LogoutView` из [`user/views.py`](user/views.py), а маршруты определены в [`user/urls.py`](user/urls.py). Создание и проверка учетных данных используют Django auth и формы из [`user/forms.py`](user/forms.py). CRUD-операции с акциями в HTML защищены `IsUserAuthenticatedMixin` в [`dashboard/views.py`](dashboard/views.py).

## Модель данных

### `Share` — акция

Модель объявлена в [`dashboard/models.py`](dashboard/models.py). Для нее Django создает таблицу приложения `dashboard` с первичным ключом `id` (тип по умолчанию — `BigAutoField`). Атрибуты:

| Атрибут | Тип / ограничения | Назначение |
|---|---|---|
| `id` | автоматически создаваемый первичный ключ | Идентификатор записи |
| `figi` | `CharField`, до 255 символов, уникальный | Идентификатор инструмента для Tinkoff API |
| `isin` | `CharField`, до 255 символов | Международный идентификатор ценной бумаги |
| `name` | `CharField`, до 255 символов | Название компании |
| `ticker` | `CharField`, до 10 символов, уникальный | Биржевой тикер |
| `currency` | `CharField`, до 20 символов | Валюта цены |
| `uid` | `CharField`, до 255 символов, уникальный | Уникальный идентификатор инструмента в API |
| `last_price` | `FloatField`, допускает `NULL` и пустое значение | Последняя сохраненная цена |
| `is_trend_high` | `BooleanField`, допускает `NULL` и пустое значение | Признак направления изменения цены |
| `updated_at` | `DateTimeField`, `auto_now=True`, nullable/blank | Время, автоматически проставляемое при сохранении модели через `save()` |

### Пользователь и связи

Собственная модель пользователя не определена: приложение использует стандартную модель Django, получаемую через `get_user_model()` в [`user/models.py`](user/models.py). Регистрация создается через `User.objects.create_user(...)` в `RegistrationForm.save()` ([`user/forms.py`](user/forms.py)); сессии и учетные записи обслуживаются Django auth.

В коде проекта нет внешних ключей или иных явных связей между `Share` и пользователем: акции хранятся как общий список, а не как портфель конкретного пользователя. Поля `figi`, `ticker` и `uid` имеют ограничения уникальности, но не являются отношениями с другими сущностями.

## Пример обработки запроса и обращение к БД

Пример: `GET /api/v1/shares/`.

1. [`config/urls.py`](config/urls.py) передает корневой URL в `dashboard.urls`.
2. [`dashboard/urls.py`](dashboard/urls.py) сопоставляет префикс `api/` с `dashboard.api.urls`.
3. [`dashboard/api/urls.py`](dashboard/api/urls.py) добавляет префикс `v1/` и подключает `dashboard.api.v1.urls`.
4. [`dashboard/api/v1/urls.py`](dashboard/api/v1/urls.py) включает URL-ы `DefaultRouter`, объявленного в `dashboard/api/v1/router.py`; регистрация `shares` направляет запрос к `ShareViewSet` из [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py).
5. Для списка `ShareViewSet` начинает с `queryset = Share.objects.all()`. **Это точка обращения к данным через Django ORM**: запрос к БД выполняется при вычислении ленивого QuerySet в ходе получения и пагинации списка. Настройка `DATABASES` в [`config/settings.py`](config/settings.py) направляет ORM к PostgreSQL.
6. DRF применяет настроенные фильтры, поиск или сортировку (если они переданы в query-параметрах), ограничивает страницу и сериализует объекты через `ShareSerializer` из [`dashboard/api/v1/serializer.py`](dashboard/api/v1/serializer.py).
7. Клиент получает JSON-ответ со списком `results` и метаданными пагинации. Сериализатор публикует `id`, `figi`, `isin`, `name`, `ticker`, `currency`, `last_price`, `is_trend_high`, `updated_at`; `uid` в API-представление не включен.

Основной путь для HTML-списка аналогичен: маршрут `""` в [`dashboard/urls.py`](dashboard/urls.py) вызывает `ShareListView` (`ListView`) из [`dashboard/views.py`](dashboard/views.py), который выбирает объекты `Share`, сортирует по `name` и разбивает на страницы по 100 записей. Результат отображается шаблоном [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html).
