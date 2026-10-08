"""Formularze ekranów operatora."""

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator

from .models import (
    AdjustReason,
    HandlingUnit,
    HUStatus,
    IssueDocument,
    Location,
    Material,
    Role,
    Unit,
)


class _MaxSizeFileMixin:
    """Ogranicza rozmiar wgrywanego pliku importu (ochrona przed OOM/DoS)."""

    max_upload_mb = 5

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if upload and upload.size > self.max_upload_mb * 1024 * 1024:
            raise forms.ValidationError(
                f"Plik jest za duży (maks. {self.max_upload_mb} MB)."
            )
        return upload


class MaterialForm(forms.ModelForm):
    max_per_pallet = forms.IntegerField(
        label="maks. ilość na palecie",
        required=False,
        min_value=1,
        help_text="Opcjonalny sztywny limit ilości na jednej palecie.",
    )

    class Meta:
        model = Material
        fields = ["index", "name", "unit", "max_per_pallet"]
        widgets = {
            "index": forms.TextInput(attrs={"autofocus": True}),
        }


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["code", "name"]


class LocationForm(forms.ModelForm):
    capacity = forms.IntegerField(
        label="pojemność (liczba HU)",
        min_value=0,
        initial=1,
        help_text="Maks. liczba HU. 0 = bez limitu.",
    )

    class Meta:
        model = Location
        fields = ["code", "type", "capacity"]


class LocationImportForm(_MaxSizeFileMixin, forms.Form):
    file = forms.FileField(
        label="Plik CSV lub XLSX",
        help_text="Kolumny: kod, typ (PICKING/ZAPAS), pojemnosc.",
    )


class StockImportForm(_MaxSizeFileMixin, forms.Form):
    file = forms.FileField(
        label="Plik CSV lub XLSX",
        help_text="Kolumny: HU, REF, nazwa, ilosc, lokalizacja, partia, data ważności.",
    )


class ReceiptImportForm(_MaxSizeFileMixin, forms.Form):
    file = forms.FileField(
        label="Plik CSV lub XLSX",
        help_text="Kolumny: indeks, ilosc, palety, lot, data_waznosci, dostawa.",
    )


class InventoryForm(forms.Form):
    MODE_ADD = "add"
    MODE_SUB = "sub"
    MODE_CHOICES = [
        (MODE_ADD, "Dodaj (+)"),
        (MODE_SUB, "Odejmij (−)"),
    ]

    hu_number = forms.CharField(
        label="Numer HU",
        max_length=30,
        widget=forms.TextInput(
            attrs={"autofocus": True, "placeholder": "np. 10476246"}
        ),
    )
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        label="Operacja",
        initial=MODE_ADD,
        widget=forms.RadioSelect,
    )
    quantity = forms.IntegerField(label="Ilość", min_value=1)
    reason = forms.ChoiceField(
        label="Powód",
        choices=[("", "— wybierz —")] + list(AdjustReason.choices),
        required=False,
    )
    note = forms.CharField(label="Uwaga", max_length=255, required=False)


class RepackForm(forms.Form):
    source_number = forms.CharField(
        label="HU źródłowy",
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "numer palety źródłowej"}),
    )
    target_number = forms.CharField(
        label="HU docelowy",
        max_length=30,
        widget=forms.TextInput(attrs={"placeholder": "numer palety docelowej"}),
    )
    quantity = forms.IntegerField(label="Ilość", min_value=1)


class UserCreateForm(forms.Form):
    username = forms.CharField(
        label="Login", max_length=150, validators=[UnicodeUsernameValidator()]
    )
    email = forms.EmailField(label="E-mail", required=False)
    password = forms.CharField(label="Hasło", widget=forms.PasswordInput)
    role = forms.ChoiceField(label="Rola", choices=Role.choices, initial=Role.OPERATOR)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Użytkownik o tym loginie już istnieje.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        # Przekazujemy „roboczego" usera, by UserAttributeSimilarityValidator
        # odrzucił hasło zbyt podobne do loginu/e-maila (bez usera nie działa).
        probe = User(
            username=self.cleaned_data.get("username", ""),
            email=self.cleaned_data.get("email", ""),
        )
        validate_password(password, user=probe)
        return password


class UserEditForm(forms.Form):
    role = forms.ChoiceField(label="Rola", choices=Role.choices)
    is_active = forms.BooleanField(label="Konto aktywne", required=False, initial=True)
    new_password = forms.CharField(
        label="Nowe hasło (opcjonalnie)",
        widget=forms.PasswordInput,
        required=False,
    )

    def __init__(self, *args, edited_user=None, **kwargs):
        # Edytowany user pozwala sprawdzić podobieństwo hasła do loginu/e-maila.
        self.edited_user = edited_user
        super().__init__(*args, **kwargs)

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password", "")
        if password:
            validate_password(password, user=self.edited_user)
        return password


class StocktakeCreateForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Lokalizacja (zakres)",
        help_text="Puste = cały magazyn.",
        empty_label="— cały magazyn —",
    )


class ReceiveForm(forms.Form):
    MODE_TOTAL = "total"
    MODE_PER_PALLET = "per_pallet"
    MODE_CHOICES = [
        (MODE_TOTAL, "Ilość całkowita + liczba palet"),
        (MODE_PER_PALLET, "Ilość na paletę + liczba palet"),
    ]

    material = forms.ModelChoiceField(queryset=Material.objects.all(), label="Materiał")
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        label="Tryb",
        initial=MODE_TOTAL,
        widget=forms.RadioSelect,
    )
    total_quantity = forms.IntegerField(
        label="Ilość całkowita", min_value=1, required=False
    )
    qty_per_pallet = forms.IntegerField(
        label="Ilość na paletę", min_value=1, required=False
    )
    pallets = forms.IntegerField(label="Liczba palet", min_value=1)

    lot = forms.CharField(label="Partia / LOT", max_length=50, required=False)
    expiry_date = forms.DateField(
        label="Data ważności",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    delivery_ref = forms.CharField(label="Numer dostawy", max_length=50, required=False)

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        pallets = cleaned.get("pallets")
        total = cleaned.get("total_quantity")
        per_pallet = cleaned.get("qty_per_pallet")
        material = cleaned.get("material")

        if not pallets:
            return cleaned

        if mode == self.MODE_TOTAL:
            if not total:
                self.add_error("total_quantity", "Podaj ilość całkowitą.")
                return cleaned
            cleaned["computed_total"] = total
        else:  # MODE_PER_PALLET
            if not per_pallet:
                self.add_error("qty_per_pallet", "Podaj ilość na paletę.")
                return cleaned
            cleaned["computed_total"] = per_pallet * pallets

        # Walidacja maks. ilości na palecie (sztywny limit z materiału).
        if material and material.max_per_pallet:
            computed_total = cleaned.get("computed_total", 0)
            # Najgęściej obciążona paleta = sufit(total / pallets).
            heaviest = -(-computed_total // pallets)
            if heaviest > material.max_per_pallet:
                self.add_error(
                    None,
                    f"Przy tym podziale na paletę przypadłoby {heaviest} szt., "
                    f"a limit materiału to {material.max_per_pallet}. "
                    f"Zwiększ liczbę palet.",
                )
        return cleaned


class AllocateForm(forms.Form):
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(), label="Lokalizacja"
    )


class DeliveryDateForm(forms.Form):
    delivery_date = forms.DateField(
        label="Termin dostawy",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    delivery_ref = forms.CharField(label="Numer dostawy", max_length=50, required=False)


class HUCorrectionForm(forms.Form):
    new_quantity = forms.IntegerField(label="Nowa ilość", min_value=0)
    note = forms.CharField(label="Uwaga", max_length=255, required=False)


class IssueDocumentForm(forms.ModelForm):
    class Meta:
        model = IssueDocument
        fields = ["reference"]
        labels = {"reference": "Referencja (opcjonalna)"}


class IssueImportForm(_MaxSizeFileMixin, forms.Form):
    file = forms.FileField(
        label="Plik CSV lub XLSX",
        help_text="Kolumny: indeks, ilosc, opcjonalnie referencja/dokument.",
    )
    reference = forms.CharField(
        label="Domyślna referencja", max_length=100, required=False
    )


class ShipForm(forms.Form):
    carrier = forms.CharField(label="Przewoźnik", max_length=80, required=False)
    tracking = forms.CharField(label="Nr przesyłki", max_length=80, required=False)


class IssueLineForm(forms.Form):
    MODE_MATERIAL = "material"
    MODE_HU = "hu"
    MODE_CHOICES = [
        (MODE_MATERIAL, "Po materiale (automatyczny dobór HU)"),
        (MODE_HU, "Konkretny HU"),
    ]

    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        label="Tryb",
        initial=MODE_MATERIAL,
        widget=forms.RadioSelect,
    )
    material = forms.ModelChoiceField(
        queryset=Material.objects.all(), label="Materiał", required=False
    )
    specific_hu = forms.ModelChoiceField(
        queryset=HandlingUnit.objects.exclude(status=HUStatus.PUSTY).filter(
            quantity__gt=0
        ),
        label="Konkretny HU",
        required=False,
    )
    requested_qty = forms.IntegerField(label="Ilość", min_value=1)

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        if mode == self.MODE_MATERIAL:
            if not cleaned.get("material"):
                self.add_error("material", "Wybierz materiał.")
        else:
            hu = cleaned.get("specific_hu")
            if not hu:
                self.add_error("specific_hu", "Wybierz HU.")
            else:
                cleaned["material"] = hu.material
                qty = cleaned.get("requested_qty")
                if qty and qty > hu.quantity:
                    self.add_error(
                        "requested_qty",
                        f"HU {hu.number} ma tylko {hu.quantity} szt.",
                    )
        return cleaned
