"""Small HTTPS adapter to the official Invest REST API; no abandoned SDK dependency."""
import json
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class MarketDataError(Exception):
    pass


def quotation(value):
    try:
        units = Decimal(str(value['units']))
        nanos = Decimal(str(value.get('nano', 0)))
        if not units.is_finite() or not nanos.is_finite() or units != units.to_integral_value() or nanos != nanos.to_integral_value() or abs(nanos) >= 1_000_000_000:
            raise ValueError
        return units + nanos / Decimal(1_000_000_000)
    except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
        raise MarketDataError('Сервис вернул некорректную дробную котировку.') from exc


def api_request(service, method, payload):
    if not settings.TINKOFF_TOKEN:
        raise MarketDataError('TINKOFF_TOKEN не настроен. Доступны локальные данные и деморежим.')
    if not settings.INVEST_API_URL.startswith('https://'):
        raise ImproperlyConfigured('INVEST_API_URL must use HTTPS')
    url = f'{settings.INVEST_API_URL.rstrip("/")}/tinkoff.public.invest.api.contract.v1.{service}/{method}'
    request = Request(url, data=json.dumps(payload).encode(), headers={
        'Authorization': f'Bearer {settings.TINKOFF_TOKEN}',
        'Content-Type': 'application/json',
    })
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        # Do not include response bodies or authorization headers in logs.
        raise MarketDataError('Сервис котировок недоступен или отклонил запрос.') from exc


def get_last_data(share):
    result = api_request('MarketDataService', 'GetLastPrices', {'figi': [share.figi]})
    try:
        item = result['lastPrices'][0]
        observed_at = datetime.fromisoformat(item['time'].replace('Z', '+00:00'))
        if observed_at.tzinfo is None:
            raise ValueError
        return quotation(item['price']), observed_at.astimezone(dt_timezone.utc)
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise MarketDataError('Сервис не вернул корректную цену инструмента.') from exc


def get_instruments():
    return api_request('InstrumentsService', 'Shares', {'instrumentStatus': 'INSTRUMENT_STATUS_BASE'}).get('instruments', [])


def get_candles(share, start, end):
    return api_request('MarketDataService', 'GetCandles', {
        'figi': share.figi, 'from': start.isoformat(), 'to': end.isoformat(),
        'interval': 'CANDLE_INTERVAL_DAY',
    }).get('candles', [])
