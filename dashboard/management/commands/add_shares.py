from django.core.management.base import BaseCommand, CommandError
from dashboard.services.market_data import get_instruments, MarketDataError
from dashboard.models import Share


class Command(BaseCommand):
    help = 'Import/update the official instrument catalogue (requires TINKOFF_TOKEN).'

    def handle(self, *args, **options):
        try:
            instruments = get_instruments()
        except MarketDataError as exc:
            raise CommandError(str(exc)) from exc
        for instrument in instruments:
            Share.objects.update_or_create(figi=instrument['figi'], defaults={
                field: instrument[field] for field in ('name', 'isin', 'ticker', 'currency', 'uid')
            })
        self.stdout.write(self.style.SUCCESS(f'Imported {len(instruments)} instruments'))
