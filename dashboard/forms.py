from django import forms
from .models import Share


class ShareModelForm(forms.ModelForm):
    class Meta:
        model = Share
        fields = ('figi', 'isin', 'name', 'ticker', 'currency', 'uid')


class HistoryRangeForm(forms.Form):
    source = forms.ChoiceField(required=False, choices=(("local", "Сохранённая история"), ("market", "Внешние дневные свечи Invest API")), initial="local")
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('Начало периода не может быть позже окончания.')
        return data
