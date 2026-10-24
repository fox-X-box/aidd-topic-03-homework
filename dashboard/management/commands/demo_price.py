from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from dashboard.models import Share
from dashboard.services.prices import record_price


class Command(BaseCommand):
    help = 'Submit a synthetic price ONLY for a seed_demo instrument; evaluates alerts and virtual strategies.'

    def add_arguments(self, parser):
        parser.add_argument('ticker')
        parser.add_argument('price')

    def handle(self, *args, **options):
        share = Share.objects.filter(ticker=options['ticker'], figi=f"DEMO-{options['ticker']}", uid=f"demo-{options['ticker']}").first()
        if share is None:
            raise CommandError('Only synthetic seed_demo instruments can be changed with this command.')
        try:
            record_price(share, options['price'])
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS(f"Synthetic {share.ticker} price recorded; personal rules evaluated."))
