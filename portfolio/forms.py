from decimal import Decimal

from django import forms

from dashboard.models import Share
from .models import Portfolio, Trade


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ["name", "currency", "initial_cash"]

    def clean_currency(self):
        currency = self.cleaned_data["currency"].strip().lower()
        if not currency.isascii() or not currency.isalpha():
            raise forms.ValidationError("Укажите код валюты, например rub или usd.")
        return currency


class TradeForm(forms.Form):
    share = forms.ModelChoiceField(queryset=Share.objects.none(), label="Акция")
    side = forms.ChoiceField(choices=Trade.Side.choices, label="Операция")
    quantity = forms.DecimalField(label="Количество", max_digits=25, decimal_places=9, min_value=Decimal("0.000000001"))

    def __init__(self, *args, portfolio, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.filter(currency__iexact=portfolio.currency).order_by("ticker")
        self.fields["share"].label_from_instance = lambda share: f"{share.ticker} — {share.name} ({share.last_price})"
