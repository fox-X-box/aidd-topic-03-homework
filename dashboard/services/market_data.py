from config.settings import TINKOFF_TOKEN, logger


def _get_client():
    """Возвращает клиент Tinkoff Invest или None, если SDK/токен недоступны.

    Импорт SDK выполняется лениво, чтобы папка проекта не перекрывала
    настоящий пакет tinkoff-investments при его установке, и приложение
    запускалось без него.
    """
    try:
        from tinkoff.invest import Client
    except ImportError:
        logger.warning(
            "Пакет tinkoff-investments не установлен; рыночные данные недоступны"
        )
        return None
    if not TINKOFF_TOKEN:
        logger.warning("TINKOFF_TOKEN не задан; рыночные данные недоступны")
        return None
    return Client(TINKOFF_TOKEN)


def get_last_data(share):
    """Возвращает [цена, время] или None, если рыночные данные недоступны."""
    client = _get_client()
    if client is None:
        return None
    with client as c:
        resp = c.market_data.get_last_prices(figi=[share.figi])
        resp = resp.last_prices.pop()
        logger.info(f"Get last data for share with id {share.id}")
        return [resp.price.units, resp.time]
