"""Konfiguracja panelu administracyjnego mini-WMS."""

from django.contrib import admin

from .models import (
    HandlingUnit,
    HUNumberingConfig,
    IssueDocument,
    IssueLine,
    Location,
    LoginEvent,
    Material,
    Profile,
    StockMovement,
    StocktakeLine,
    StocktakeSheet,
    Unit,
)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("index", "name", "unit", "max_per_pallet", "created_at")
    list_filter = ("unit",)
    search_fields = ("index", "name")
    autocomplete_fields = ("unit",)
    list_select_related = ("unit",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "type", "capacity", "occupancy")
    list_filter = ("type",)
    search_fields = ("code",)


@admin.register(HandlingUnit)
class HandlingUnitAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "material",
        "quantity",
        "status",
        "location",
        "lot",
        "expiry_date",
        "delivery_ref",
        "delivery_date",
        "created_at",
    )
    list_filter = ("status", "location__type")
    search_fields = ("number", "material__index", "lot", "delivery_ref")
    autocomplete_fields = ("material", "location")
    list_select_related = ("material", "material__unit", "location")
    readonly_fields = ("number",)
    date_hierarchy = "created_at"


class IssueLineInline(admin.TabularInline):
    model = IssueLine
    extra = 0
    autocomplete_fields = ("material", "specific_hu")


@admin.register(IssueDocument)
class IssueDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "reference", "status", "created_at", "created_by")
    list_filter = ("status",)
    search_fields = ("number", "reference")
    list_select_related = ("created_by",)
    readonly_fields = ("number",)
    inlines = [IssueLineInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "type",
        "material",
        "handling_unit",
        "quantity_delta",
        "reason",
        "location_from",
        "location_to",
        "created_by",
    )
    list_filter = ("type", "reason")
    search_fields = ("material__index", "handling_unit__number", "note")
    list_select_related = (
        "material",
        "handling_unit",
        "location_from",
        "location_to",
        "created_by",
    )
    date_hierarchy = "created_at"
    autocomplete_fields = ("material", "handling_unit")

    def has_change_permission(self, request, obj=None):
        # Ruchy są niezmienne; korekty robi się nowym ruchem. Tylko superuser.
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class StocktakeLineInline(admin.TabularInline):
    model = StocktakeLine
    extra = 0
    autocomplete_fields = ("handling_unit", "material")


@admin.register(StocktakeSheet)
class StocktakeSheetAdmin(admin.ModelAdmin):
    list_display = ("number", "location", "status", "created_at", "created_by")
    list_filter = ("status",)
    search_fields = ("number",)
    list_select_related = ("location", "created_by")
    readonly_fields = ("number",)
    inlines = [StocktakeLineInline]


@admin.register(HUNumberingConfig)
class HUNumberingConfigAdmin(admin.ModelAdmin):
    list_display = ("prefix", "next_number", "padding")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "username", "user", "ip", "user_agent")
    list_filter = ("kind",)
    search_fields = ("username", "ip", "user_agent")
    date_hierarchy = "created_at"
    readonly_fields = ("user", "username", "kind", "ip", "user_agent", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
