from django import forms

from .models import Watchlist, WatchRule


class WatchlistForm(forms.ModelForm):
    class Meta:
        model = Watchlist
        fields = ("name",)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = owner

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Watchlist.objects.filter(owner=self.instance.owner, name=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Список с таким названием уже существует.")
        return name


class WatchRuleForm(forms.ModelForm):
    class Meta:
        model = WatchRule
        fields = ("share", "direction", "target_price")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].label_from_instance = lambda share: f"{share.ticker}: {share.name} ({share.currency})"
        self.fields["target_price"].help_text = "В валюте выбранной акции; правило сработает один раз."
