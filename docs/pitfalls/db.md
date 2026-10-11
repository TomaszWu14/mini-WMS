# Pułapki: baza danych i migracje

1. **Stan HU zmieniaj tylko przez `warehouse/services.py`.** Każda funkcja serwisu zapisuje
   `StockMovement` w tej samej transakcji (`@transaction.atomic`). Bezpośredni
   `hu.quantity = …; hu.save()` w widoku/komendzie rozjeżdża historię ze stanem.
2. **`select_for_update()` w SQLite nic nie blokuje.** Dev i testy działają na SQLite,
   produkcja na PostgreSQL — wyścigi (dwa pickingi tej samej palety) widać dopiero na
   Postgresie. Test „równoległości” na SQLite niczego nie dowodzi.
3. **Blokuj wiersz przed odczytem ilości.** Wzór z `pick_from_hu`/`repack_hu`:
   `HandlingUnit.objects.select_for_update().get(pk=hu.pk)` na początku transakcji, potem
   walidacja. Walidacja na obiekcie przekazanym z widoku czyta nieaktualny stan.
4. **Numeracja WZ/SP może kolidować.** `_next_daily_number` liczy max+1 bez blokady —
   zapis zawsze przez `save_with_unique_number` (savepoint + ponowienie po
   `IntegrityError`). Numer HU idzie inną drogą: licznik `HUNumberingConfig` z
   `select_for_update`.
5. **Ograniczenia w bazie, nie tylko w formularzu.** `CheckConstraint` (ilość ≥ 0) i
   pola `unique=True` (numer HU/WZ, kod lokalizacji, indeks materiału). Nowa reguła ilościowa
   → constraint + migracja, nie sam `clean()`.
6. **`CheckConstraint(check=…)` jest przestarzałe** (RemovedInDjango60Warning w
   `models.py:90,215`). Nowe constrainty pisz z `condition=`; zmiana istniejących generuje
   migrację — osobny PR.
7. **Migracje danych muszą być odwracalne.** `0002_seed_defaults` ma
   `RunPython(create_defaults, remove_defaults)` — każdy nowy `RunPython` też z funkcją
   wsteczną (albo jawnie `RunPython.noop`). Używaj `apps.get_model`, nie importu modeli.
8. **Po zmianie modelu: `makemigrations --check`.** CI odrzuca brakujące migracje
   (`python manage.py makemigrations --check --dry-run`). Nie edytuj zastosowanych migracji.
9. **N+1 na listach.** Widoki list używają `select_related("material", "location",
   "material__unit")`; szablon odwołujący się do nowej relacji bez dopisania jej tu = zapytanie
   na wiersz. `issue_execute` liczy `line.shortage` po `doc.lines.all()` — przy dużych WZ
   sprawdź liczbę zapytań (`assertNumQueries`).
10. **`on_delete=PROTECT` na materiale/lokalizacji.** Usunięcie materiału z HU rzuca
    `ProtectedError` — obsłuż to w widoku zamiast zmieniać na `CASCADE` (skasowałoby historię).
