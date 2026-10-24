from datetime import timedelta
from plotly.graph_objs import Scatter
from plotly.offline import plot
from django.utils import timezone
from .market_data import get_candles, quotation


def get_graph(share):
    end = timezone.now()
    candles = get_candles(share, end - timedelta(days=180), end)
    return plot([Scatter(x=[c['time'] for c in candles], y=[quotation(c['close']) for c in candles], mode='lines', name=share.ticker)],
                output_type='div', include_plotlyjs=True, show_link=False)
