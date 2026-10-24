from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import Share, PricePoint
from dashboard.services.prices import record_price


class Command(BaseCommand):
    help = 'Create clearly labelled synthetic instruments and local history. No real market data.'

    def handle(self, *args, **options):
        for ticker, price in [('DEMO1', '100.50'), ('DEMO2', '250.25')]:
            share, created = Share.objects.get_or_create(ticker=ticker, defaults={
                'name': f'Демонстрационная акция {ticker}', 'figi': f'DEMO-{ticker}',
                'isin': f'DEMO-{ticker}', 'uid': f'demo-{ticker}', 'currency': 'rub',
            })
            if not created:
                continue
            now = timezone.now()
            for days in range(7, 0, -1):
                PricePoint.objects.create(share=share, price=Decimal(price)-days, observed_at=now-timedelta(days=days))
            record_price(share, Decimal(price), now)
        self.stdout.write(self.style.SUCCESS('Synthetic demo catalogue is ready; no live prices used.'))
