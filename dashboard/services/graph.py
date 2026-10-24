from datetime import timedelta
from plotly.graph_objs import Scatter
from plotly.offline import plot
from django.conf import settings
from django.utils import timezone
from .market_data import get_candles, quotation


def get_graph(share, start=None, end=None, source="local"):
    end = end or timezone.now()
    start = start or end - timedelta(days=180)
    points = list(share.price_history.filter(observed_at__gte=start, observed_at__lte=end))
    if source == "market":
        candles = get_candles(share, start, end)
        x, y = [c['time'] for c in candles], [quotation(c['close']) for c in candles]
    elif points:
        x, y = [p.observed_at for p in points], [p.price for p in points]
    else:
        x, y = [], []
    return plot([Scatter(x=x, y=y, mode='lines+markers', name=share.ticker)],
                output_type='div', include_plotlyjs=True, show_link=False)
