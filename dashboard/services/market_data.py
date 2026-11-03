from config.settings import TINKOFF_TOKEN, logger


class MarketDataError(Exception):
    """An expected failure while requesting market data."""


def money_value_to_float(value):
    return value.units + value.nano / 1_000_000_000


def get_last_data(share):
    try:
        from tinkoff.invest import Client
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("tinkoff"):
            raise MarketDataError(
                "Install the optional tinkoff-investments SDK to fetch market data"
            ) from exc
        raise

    try:
        from grpc import RpcError
    except ModuleNotFoundError as exc:
        if exc.name == "grpc":
            raise MarketDataError(
                "Install the optional tinkoff-investments SDK dependencies"
            ) from exc
        raise

    try:
        with Client(TINKOFF_TOKEN) as client:
            resp = client.market_data.get_last_prices(figi=[share.figi])
            resp = resp.last_prices.pop()
            logger.info(f"Get last data for share with id {share.id}")
            return money_value_to_float(resp.price), resp.time
    except RpcError as exc:
        raise MarketDataError("Tinkoff market data request failed") from exc
