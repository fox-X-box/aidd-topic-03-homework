from decimal import Decimal

from django import forms

from .models import Observation, Share


class ShareModelForm(forms.ModelForm):
    """Инструмент"""

    class Meta:
        model = Share
        fields = "__all__"


class ObservationTargetForm(forms.ModelForm):
    target_price = forms.DecimalField(
        label="Целевая цена", min_value=Decimal("0.01"), max_digits=12, decimal_places=2
    )

    class Meta:
        model = Observation
        fields = ["target_price"]


class ObservationCreateForm(ObservationTargetForm):
    class Meta(ObservationTargetForm.Meta):
        fields = ["stock", "target_price"]
