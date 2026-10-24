import django.db.models.deletion
import django.core.validators
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dashboard", "0007_add_updated_at"),
    ]
    operations = [
        migrations.CreateModel(
            name="Watchlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="Название списка")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name", "pk")},
        ),
        migrations.CreateModel(
            name="WatchRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("direction", models.CharField(choices=[("above", "Цена не ниже цели"), ("below", "Цена не выше цели")], max_length=5, verbose_name="Условие")),
                ("target_price", models.DecimalField(decimal_places=9, max_digits=24, validators=[django.core.validators.MinValueValidator(Decimal("0.000000001"))], verbose_name="Целевая цена")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("share", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="dashboard.share")),
                ("watchlist", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rules", to="monitoring.watchlist")),
            ],
            options={"ordering": ("-created_at", "-pk")},
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ticker", models.CharField(max_length=10)),
                ("currency", models.CharField(max_length=20)),
                ("direction", models.CharField(choices=[("above", "Цена не ниже цели"), ("below", "Цена не выше цели")], max_length=5)),
                ("target_price", models.DecimalField(decimal_places=9, max_digits=24)),
                ("observed_price", models.DecimalField(decimal_places=9, max_digits=24)),
                ("observed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("is_read", models.BooleanField(default=False)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("rule", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification", to="monitoring.watchrule")),
            ],
            options={"ordering": ("-created_at", "-pk")},
        ),
        migrations.AddConstraint(model_name="watchlist", constraint=models.UniqueConstraint(fields=("owner", "name"), name="unique_owner_watchlist")),
        migrations.AddConstraint(model_name="watchrule", constraint=models.CheckConstraint(condition=models.Q(target_price__gt=0), name="watch_target_positive")),
    ]
