from django import forms

from portfolio.models import Portfolio
from .models import Strategy


class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = ["name", "portfolio", "share", "side", "quantity", "price_threshold"]

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = owner
        self.fields["portfolio"].queryset = Portfolio.objects.filter(owner=owner)

    def clean(self):
        cleaned = super().clean()
        portfolio, share = cleaned.get("portfolio"), cleaned.get("share")
        if portfolio and share and portfolio.currency.lower() != share.currency.lower():
            raise forms.ValidationError("Валюта акции должна совпадать с валютой портфеля.")
        return cleaned
