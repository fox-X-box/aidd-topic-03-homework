from django.contrib import admin

from dashboard.models import PriceAlert, Share, WatchlistItem


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("figi", "isin", "name", "ticker", "currency")
    search_fields = ("figi", "isin", "name", "ticker")
    fields = (
        "figi",
        "isin",
        "name",
        "ticker",
        "currency",
        "uid",
        "last_price",
        "is_trend_high",
    )


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "target_price", "is_above_target")
    list_select_related = ("user", "share")


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "ticker",
        "target_price",
        "triggered_price",
        "created_at",
    )
    list_select_related = ("user", "share")
    readonly_fields = (
        "user",
        "share",
        "share_name",
        "ticker",
        "target_price",
        "triggered_price",
        "created_at",
    )
