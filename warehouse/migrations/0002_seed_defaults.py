"""Dane domyślne: jednostka PCS oraz konfiguracja numeracji HU."""

from django.db import migrations


def create_defaults(apps, schema_editor):
    Unit = apps.get_model("warehouse", "Unit")
    HUNumberingConfig = apps.get_model("warehouse", "HUNumberingConfig")

    Unit.objects.get_or_create(code="PCS", defaults={"name": "Sztuki"})
    if not HUNumberingConfig.objects.exists():
        HUNumberingConfig.objects.create(prefix="HU", next_number=1, padding=8)


def remove_defaults(apps, schema_editor):
    # Nie usuwamy danych przy cofaniu — bezpieczniej zostawić.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_defaults, remove_defaults),
    ]
