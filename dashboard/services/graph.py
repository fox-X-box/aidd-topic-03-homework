from datetime import timedelta
from plotly.graph_objs import Scatter
from plotly.offline import plot
from config.settings import TINKOFF_TOKEN, logger

NANO = 1_000_000_000


def _quotation_to_float(quotation):
    """Переводит Quotation Tinkoff Invest (units + nano) в float.

    Формат Tinkoff: отрицательные котировки хранятся как units < 0 и
    nano того же знака, поэтому при units < 0 дробная часть вычитается.
    """
    units = quotation.units
    nano = quotation.nano
    if units >= 0:
        return units + nano / NANO
    return units - nano / NANO


def _get_candle_client():
    """Возвращает (Client, CandleInterval, now) или None, если SDK/токен недоступны."""
    try:
        from tinkoff.invest import CandleInterval, Client
        from tinkoff.invest.utils import now
    except ImportError:
        logger.warning(
            "Пакет tinkoff-investments не установлен; график недоступен"
        )
        return None
    if not TINKOFF_TOKEN:
        logger.warning("TINKOFF_TOKEN не задан; график недоступен")
        return None
    return Client, CandleInterval, now


def get_graph(share):
    """Возвращает HTML-див с графиком или None, если рыночные данные недоступны."""
    candle_client = _get_candle_client()
    if candle_client is None:
        return None
    Client, CandleInterval, now = candle_client
    with Client(TINKOFF_TOKEN) as client:
        x_data, y_data = [], []
        for candle in client.get_all_candles(
            figi=share.figi,
            from_=now() - timedelta(days=180),
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        ):
            x_data.append(candle.time.date())
            y_data.append(_quotation_to_float(candle.close))
    plot_div = plot(
        [
            Scatter(
                x=x_data,
                y=y_data,
                mode="lines",
                name="test",
                opacity=0.8,
                marker_color="red",
            )
        ],
        output_type="div",
        show_link=False,
        link_text="",
    )
    return plot_div
