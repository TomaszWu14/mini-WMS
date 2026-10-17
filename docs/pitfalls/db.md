# Pułapki: baza danych i migracje

1. **Stan HU zmieniaj tylko przez `warehouse/services.py`.** Każda funkcja serwisu zapisuje
   `StockMovement` w tej samej transakcji (`@transaction.atomic`). Bezpośredni
   `hu.quantity = …; hu.save()` w widoku/komendzie rozjeżdża historię ze stanem.
2. **`select_for_update()` w SQLite nic nie blokuje.** Dev i testy działają na SQLite,
   produkcja na PostgreSQL — wyścigi (dwa pickingi tej samej palety) widać dopiero na
   Postgresie. Test „równoległości” na SQLite niczego nie dowodzi — pisz go jak
   `tests_concurrency_pg.py` (pomijany na SQLite, uruchamia go job CI `test-postgres`).
3. **Blokuj wiersz przed odczytem ilości.** Wzór z `pick_from_hu`/`repack_hu`:
   `HandlingUnit.objects.select_for_update().get(pk=hu.pk)` na początku transakcji, potem
   walidacja. Walidacja na obiekcie przekazanym z widoku czyta nieaktualny stan.
3a. **Kolejność blokad: dokument WZ → pozycja → HU (US-018).** Każdy wiersz osobnym
   `select_for_update()` — **nie** `select_for_update().select_related(...)`: zapytanie z JOIN blokuje
   wszystkie złączone wiersze w nieustalonej kolejności i daje `deadlock detected` z inną ścieżką.
   Zmiana stanu WZ tylko w serwisie (`complete_if_picked`, `execute_issue_document`, `pack/ship`).
   Palety między sobą nie mają jeszcze jednej kolejności (US-053). Pozycje WZ dodaje i usuwa tylko
   `services.add_issue_line` / `delete_issue_line` (US-052) — pozycji z `picked_qty > 0` nie usuwamy.
4. **Numeracja WZ/SP może kolidować.** `_next_daily_number` liczy max+1 bez blokady —
   zapis zawsze przez `save_with_unique_number` (savepoint + ponowienie po
   `IntegrityError`). Numer HU idzie inną drogą: licznik `HUNumberingConfig` z
   `select_for_update`.
5. **Ograniczenia w bazie, nie tylko w formularzu.** `CheckConstraint` (ilość ≥ 0) i
   pola `unique=True` (numer HU/WZ, kod lokalizacji, indeks materiału). Nowa reguła ilościowa
   → constraint + migracja, nie sam `clean()`.
6. **`CheckConstraint` pisz z `condition=`**, nie `check=` (usunięte w Django 6.0). Zamiana
   w istniejących constraintach nie wymaga migracji (`makemigrations --check` = brak zmian).
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
