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

## Восстановленные функциональные требования

Ниже перечислено поведение, подтверждаемое исходным кодом. Сценарии, проверки и права доступа описаны раздельно для HTML-интерфейса и REST API. Недостатки и неоднозначности реализации вынесены в отдельный подраздел и не являются требованиями.

### Веб-интерфейс и учетные записи

1. **FR-01.** При открытии главной страницы приложение показывает акции, отсортированные по названию и разбитые на страницы по 100 записей; для пустого списка шаблон показывает сообщение об отсутствии акций. Подтверждение: `ShareListView` и маршрут `""` в [`dashboard/views.py`](dashboard/views.py) и [`dashboard/urls.py`](dashboard/urls.py); таблица и сообщение — [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html).
2. **FR-02.** Для каждой акции в списке отображаются тикер, название, ISIN, цена и валюта; переход по тикеру открывает карточку. Если `is_trend_high` истинно, цена выделяется зеленым, иначе — розовым. Подтверждение: [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html).
3. **FR-03.** При открытии карточки акции приложение показывает ее название, последнюю сохраненную цену, валюту и время обновления, а также график дневных закрытий за период до 180 дней. Подтверждение: `ShareDetailView.get` в [`dashboard/views.py`](dashboard/views.py), `get_graph` в [`dashboard/services/graph.py`](dashboard/services/graph.py), шаблон [`dashboard/templates/dashboard/detail.html`](dashboard/templates/dashboard/detail.html).
4. **FR-04.** Вошедший пользователь может создать акцию через HTML-форму; при успешном сохранении приложение возвращает его на главную страницу. Форма содержит поля модели, проходящие проверки `ModelForm` и ограничений модели. Подтверждение: `ShareCreateView` в [`dashboard/views.py`](dashboard/views.py), `ShareModelForm` в [`dashboard/forms.py`](dashboard/forms.py), шаблоны [`dashboard/templates/dashboard/create.html`](dashboard/templates/dashboard/create.html) и [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html), модель [`dashboard/models.py`](dashboard/models.py).
5. **FR-05.** Вошедший пользователь может изменить выбранную акцию, после сохранения приложение возвращает его на главную страницу. Подтверждение: `ShareUpdateView` в [`dashboard/views.py`](dashboard/views.py), `ShareModelForm` в [`dashboard/forms.py`](dashboard/forms.py), маршрут `update/<int:pk>` в [`dashboard/urls.py`](dashboard/urls.py).
6. **FR-06.** Вошедший пользователь может запросить удаление выбранной акции и подтвердить его POST-запросом; после удаления приложение возвращает его на главную страницу. Подтверждение: `ShareDeleteView` в [`dashboard/views.py`](dashboard/views.py), маршрут `delete/<int:pk>` в [`dashboard/urls.py`](dashboard/urls.py), форма подтверждения в [`dashboard/templates/dashboard/delete.html`](dashboard/templates/dashboard/delete.html).
7. **FR-07.** Гость может просматривать список и карточки акций, но при обращении к HTML-операциям создания, редактирования или удаления перенаправляется на главную страницу. Подтверждение: `ShareListView`, `ShareDetailView`, `IsUserAuthenticatedMixin.test_func` и `handle_no_permission`, а также защищенные `ShareCreateView`, `ShareUpdateView`, `ShareDeleteView` в [`dashboard/views.py`](dashboard/views.py); наличие ссылок управления только для вошедшего пользователя — [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html).
8. **FR-08.** Гость может открыть форму регистрации; при отправке корректной формы с уникальным email и совпадающими непустыми паролями приложение создает пользователя, выполняет вход и перенаправляет на главную страницу. При несовпадении паролей или найденном email форма возвращает ошибку. Подтверждение: `RegistrationView` в [`user/views.py`](user/views.py), `RegistrationForm.clean` и `save` в [`user/forms.py`](user/forms.py), маршрут `registration/` в [`user/urls.py`](user/urls.py), шаблон [`user/templates/user/registration.html`](user/templates/user/registration.html).
9. **FR-09.** Гость может отправить email и пароль для входа; при успешной аутентификации приложение создает сессию и перенаправляет на главную страницу, а при неуспешной показывает сообщение об ошибке. Подтверждение: `AuthView.get` и `AuthView.post` в [`user/views.py`](user/views.py), `AuthForm` в [`user/forms.py`](user/forms.py), маршрут `login/` в [`user/urls.py`](user/urls.py), шаблон [`user/templates/user/auth.html`](user/templates/user/auth.html).
10. **FR-10.** При переходе по маршруту выхода приложение завершает текущую сессию и перенаправляет пользователя на главную страницу. Подтверждение: `LogoutView.get` в [`user/views.py`](user/views.py), маршрут `logout/` в [`user/urls.py`](user/urls.py), ссылка выхода в [`dashboard/templates/dashboard/base.html`](dashboard/templates/dashboard/base.html).

### REST API и права доступа

11. **FR-11.** Клиент, в том числе не прошедший аутентификацию, может получить список акций или одну акцию через `/api/v1/shares/` и `/api/v1/shares/<id>/`. Для списка используется `LimitOffsetPagination`: размер страницы по умолчанию (`limit`) — 100 элементов; параметр `limit` задает число записей в ответе, а `offset` — число записей в выборке, которые нужно пропустить перед этой страницей (по умолчанию `offset=0`). Подтверждение: `ShareViewSet` в [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py), регистрация роутера в [`dashboard/api/v1/router.py`](dashboard/api/v1/router.py), `DEFAULT_PAGINATION_CLASS` и `PAGE_SIZE` в [`config/settings.py`](config/settings.py); публичное чтение без аутентификации проверяется в [`dashboard/tests.py`](dashboard/tests.py) (`test_share_list`, `test_share_detail`).
12. **FR-12.** Не прошедший аутентификацию клиент может создать акцию POST-запросом к `/api/v1/shares/`. Если данные не проходят валидацию `ShareSerializer` (например, отсутствуют обязательные поля, как в тесте с одним `figi`), API возвращает HTTP 400; если сериализатор валидирует данные и запись в БД проходит успешно, API возвращает HTTP 201. HTTP 400 здесь относится к ошибкам валидации сериализатора, а не к ошибкам записи в БД. Подтверждение: `ShareViewSet` и `ShareSerializer` в [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py) и [`dashboard/api/v1/serializer.py`](dashboard/api/v1/serializer.py); `test_share_create_invalid` и `test_share_create` в [`dashboard/tests.py`](dashboard/tests.py).
13. **FR-13.** Не прошедший аутентификацию клиент может изменить существующую акцию PUT/PATCH-запросом к `/api/v1/shares/<id>/`; успешный PUT возвращает обновленное представление, а отсутствующие обязательные данные полного PUT приводят к HTTP 400. Подтверждение: `ShareViewSet` и `ShareSerializer` в [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py) и [`dashboard/api/v1/serializer.py`](dashboard/api/v1/serializer.py), `test_share_update` и `test_share_update_invalid` в [`dashboard/tests.py`](dashboard/tests.py).
14. **FR-14.** Не прошедший аутентификацию клиент может удалить существующую акцию DELETE-запросом к `/api/v1/shares/<id>/`; успешное удаление возвращает HTTP 204, а для отсутствующего идентификатора — HTTP 404. Подтверждение: `ShareViewSet` в [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py), `test_share_delete` и `test_share_delete_invalid` в [`dashboard/tests.py`](dashboard/tests.py).
15. **FR-15.** В запросе списка API клиент может фильтровать акции по `name` и `ticker`, выполнять поиск по `name` и сортировать по `name` или `ticker`. Подтверждение: `ShareFilter` и `ShareViewSet.filter_backends`, `search_fields`, `ordering_fields` в [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py).
16. **FR-16.** Представление акции в API содержит `id`, `figi`, `isin`, `name`, `ticker`, `currency`, `last_price`, `is_trend_high` и `updated_at`; поле `uid` не включается. Подтверждение: `ShareSerializer.Meta.fields` в [`dashboard/api/v1/serializer.py`](dashboard/api/v1/serializer.py).

### Загрузка справочника и фоновые задачи

17. **FR-17.** При запуске команды `python manage.py add_shares` приложение запрашивает у Tinkoff Invest API список акций и для каждого инструмента вызывает `Share.objects.get_or_create` с его FIGI, названием, ISIN, тикером, валютой и UID. Подтверждение: `Command.handle` в [`dashboard/management/commands/add_shares.py`](dashboard/management/commands/add_shares.py).
18. **FR-18.** Celery Beat запускает `dashboard.tasks.update_last_price` с настроенным интервалом 10 секунд; задача проходит по записям `Share`, получает актуальную цену по FIGI и записывает `price.units` в `last_price`. Подтверждение: `app.conf.beat_schedule` в [`config/celery.py`](config/celery.py), `update_last_price` в [`dashboard/tasks.py`](dashboard/tasks.py), `get_last_data` в [`dashboard/services/market_data.py`](dashboard/services/market_data.py).
19. **FR-19.** При обработке цены задача устанавливает `is_trend_high` в `False`, если ранее сохраненная цена больше новой, и в `True` в противном случае; если сравнение завершается исключением, задача пишет ошибку в лог и устанавливает `True`. Подтверждение: `update_last_price` в [`dashboard/tasks.py`](dashboard/tasks.py), логгер `main` в [`config/settings.py`](config/settings.py).
20. **FR-20.** Если получение данных или обновление отдельной акции завершается исключением, задача записывает ошибку в лог и продолжает цикл обработки следующих акций. Подтверждение: внешний блок `try/except` внутри цикла `update_last_price` в [`dashboard/tasks.py`](dashboard/tasks.py).

## Неоднозначности, противоречия и возможные дефекты реализации

- **Интервал фонового обновления:** ключ расписания Celery называется `add-every-5-min`, но фактически `schedule` равен `10.0` секундам. В требованиях выше указано фактическое значение. Подтверждение: [`config/celery.py`](config/celery.py).
- **Потеря дробной части цены:** `get_last_data` и `get_graph` используют только `units` цены/закрытия свечи, не включая `nano`; цена сохраняется и отображается с потерей дробной части. Подтверждение: [`dashboard/services/market_data.py`](dashboard/services/market_data.py), [`dashboard/services/graph.py`](dashboard/services/graph.py).
- **Не обновляется время обновления цены:** `update_last_price` записывает поля через `QuerySet.update`, который не вызывает `save()` модели; поэтому `auto_now` поля `updated_at` не обновляется этим путем. При этом возвращаемое `get_last_data` время API распаковывается в неиспользуемую переменную `detetime`. Подтверждение: [`dashboard/tasks.py`](dashboard/tasks.py), [`dashboard/services/market_data.py`](dashboard/services/market_data.py), поле в [`dashboard/models.py`](dashboard/models.py).
- **Неоднозначная семантика признака тренда:** равная цена приводит к `is_trend_high=True`; отсутствие предыдущей цены также попадает в обработчик исключения и получает `True`. В списке любое ложное значение, включая `NULL`, показывается тем же розовым цветом, что и снижение. Подтверждение: [`dashboard/tasks.py`](dashboard/tasks.py), [`dashboard/templates/dashboard/list.html`](dashboard/templates/dashboard/list.html), [`dashboard/models.py`](dashboard/models.py).
- **UID при API-создании (вывод по коду, не результат запуска):** поле `uid` обязательно и уникально в модели `Share`, но отсутствует в `ShareSerializer.Meta.fields`; DRF не включает его во входные `validated_data`, даже если клиент передает ключ `uid`. У поля модели нет текущего явного `default`, поэтому Django для `CharField` без значения использует пустую строку; миграция [`dashboard/migrations/0003_add_uuid.py`](dashboard/migrations/0003_add_uuid.py) также показывает, что при добавлении `uid` использовался `default=""`. Следовательно, первый POST новой акции без фактически принятого `uid` сохраняет `uid=""`; второй такой POST для другой акции с уникальными `figi` и `ticker` пытается записать тот же пустой `uid` и сталкивается с ограничением уникальности БД. `ShareViewSet` не перехватывает ошибку записи, поэтому она не становится ошибкой валидации HTTP 400 и при обычной обработке сервера приводит к серверной ошибке. Основание: [`dashboard/models.py`](dashboard/models.py), [`dashboard/api/v1/serializer.py`](dashboard/api/v1/serializer.py), [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py), [`dashboard/migrations/0003_add_uuid.py`](dashboard/migrations/0003_add_uuid.py).
- **Что проверяет `test_share_create`:** тест выполняет только один POST для `second_company`, после чего проверяет HTTP 201, несколько полей ответа и общее количество записей. В тестовом payload есть `uid`, но сериализатор его не включает; тест не проверяет сохраненное значение `uid` и не отправляет второй POST, поэтому случай конфликта двух пустых `uid` им не покрыт. Подтверждение: `DashboardTests.setUp` и `test_share_create` в [`dashboard/tests.py`](dashboard/tests.py).
- **Результат запуска проверки (отдельно от вывода по коду):** запуск `python manage.py test dashboard.tests.DashboardTests.test_share_create --verbosity 2` невозможен, поскольку команда `python` в окружении отсутствует. Повторный запуск через `python3` завершился до исполнения теста с `ModuleNotFoundError: No module named 'django'`. Поэтому описанное поведение с двумя POST выведено из исходников и ограничений модели, а не подтверждено выполнением теста.
- **Гостевой доступ к изменяющему API:** `ShareViewSet` предоставляет все действия `ModelViewSet`, а в `REST_FRAMEWORK` не задан `DEFAULT_PERMISSION_CLASSES`; API-тесты создают, обновляют и удаляют записи без выполнения входа. Это фактическое поведение исходной версии, отдельное от ограничений HTML-форм. Подтверждение: [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py), [`config/settings.py`](config/settings.py), [`dashboard/tests.py`](dashboard/tests.py).
- **Различия поиска API и фильтрации:** фильтр `ShareFilter` задает поля `name` и `ticker` без специальных lookup, тогда как `search_fields=["$name"]` использует префикс `$` для regex-поиска DRF. Таким образом, фильтрация и поиск имеют разные правила; пользовательское описание этих правил отсутствует. Подтверждение: [`dashboard/api/v1/views.py`](dashboard/api/v1/views.py).
- **Обработка некорректно заполненных форм пользователя:** `AuthView.post` берет значения напрямую из `form.data`, не вызывая `is_valid()`, а `RegistrationForm.clean` обращается к обязательным ключам `cleaned_data` напрямую. При пропущенных или некорректных полях возможна ошибка вместо штатного показа ошибок формы. Подтверждение: [`user/views.py`](user/views.py), [`user/forms.py`](user/forms.py).
- **Импорт может не обновить изменившиеся данные инструмента:** `get_or_create` получает все шесть полей инструмента как параметры поиска, а не только стабильный уникальный ключ с `defaults`; если инструмент уже существует с тем же уникальным FIGI, но отличаются другие поля, существующая запись не совпадет по всем условиям, и попытка создания может нарушить уникальность. Подтверждение: [`dashboard/management/commands/add_shares.py`](dashboard/management/commands/add_shares.py), ограничения уникальности в [`dashboard/models.py`](dashboard/models.py).
- **Ошибка карточки для неизвестного ID:** `ShareDetailView.get` использует `Share.objects.get(id=pk)` без обработки `DoesNotExist`; для несуществующей акции явно не задан ответ 404, в отличие от стандартного поведения generic views и API. Подтверждение: [`dashboard/views.py`](dashboard/views.py).
