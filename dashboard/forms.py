from django import forms

from .models import Share, WatchlistItem


class ShareModelForm(forms.ModelForm):
    """Инструмент"""

    class Meta:
        model = Share
        fields = "__all__"


class WatchlistCreateForm(forms.ModelForm):
    class Meta:
        model = WatchlistItem
        fields = ("share", "target_price")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.order_by("name")
        self.fields["target_price"].help_text = "Укажите положительную цену."

    def clean_share(self):
        share = self.cleaned_data["share"]
        if WatchlistItem.objects.filter(user=self.user, share=share).exists():
            raise forms.ValidationError("Эта акция уже есть в вашем списке.")
        return share


class WatchlistUpdateForm(forms.ModelForm):
    class Meta:
        model = WatchlistItem
        fields = ("target_price",)
