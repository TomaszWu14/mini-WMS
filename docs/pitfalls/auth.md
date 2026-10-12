# Pułapki: uwierzytelnianie i role

1. **Każdy widok musi mieć dekorator.** `@login_required` (odczyt), `@operator_required`
   (operacje), `@admin_required` (użytkownicy, dziennik logowań) z `warehouse/roles.py`.
   Dziś wszystkie widoki w `views.py` i `scanner_views.py` go mają — nowy widok bez
   dekoratora jest publiczny.
2. **Rola pochodzi z `Profile`, nie z grup Django.** `get_role()`: superuser → zawsze
   Administrator; brak profilu → Podgląd. Nie sprawdzaj `user.groups` ani `is_staff`.
3. **Profil tworzy sygnał `ensure_profile` (post_save User).** Użytkownik tworzony bez
   `save()` (np. `bulk_create`) nie dostanie profilu i wyląduje jako Podgląd.
4. **Brak separacji danych między użytkownikami — to jeden magazyn.** Każdy zalogowany
   widzi wszystkie HU/WZ. Jeśli pojawi się drugi magazyn/firma, filtrowanie trzeba dodać
   w każdym querysecie (dziś go nie ma).
5. **`_client_ip` ufa `X-Forwarded-For` tylko przy `TRUSTED_PROXY_COUNT` > 0** (`signals.py`)
   i bierze N-ty wpis od końca. Nowe proxy przed aplikacją (np. Cloudflare przed Traefikiem)
   = podbij `DJANGO_TRUSTED_PROXY_COUNT`, inaczej wszyscy dzielą IP proxy i jeden limit.
6. **Limit logowań jest per proces gunicorna** (LocMem cache) — przy 3 workerach realnie
   ~30 prób/5 min. Działa zawsze (nie tylko w demo) — testy POST na `/login/` czyszczą cache.
7. **„Wejdź jako demo” (`demo.demo_login`) loguje bez hasła** — tylko przy `DEMO_MODE` i tylko
   kontem z `DEMO_ACCOUNTS` (`DEMO_USER` spoza listy = odmowa). Nie rozszerzaj listy o konto z
   uprawnieniami administratora.
8. **Konta demo chroni `is_demo_account` tylko w `user_edit`.** Nowy widok zmieniający
   hasło/rolę/status musi to sprawdzić osobno (inaczej publiczne demo da się zablokować).
9. **Admin Django jest wyłączony przy `DEMO_MODE=1`** (`config/urls.py`). Funkcje
   serwisowe dodawaj jako komendę `manage.py`, nie jako akcję admina.
10. **Sesja wygasa po 30 min bezczynności** (`SESSION_COOKIE_AGE=1800`,
   `SESSION_SAVE_EVERY_REQUEST`). Skaner trzymany długo w ręku dostanie redirect na login
   w środku operacji — API skanera zwraca wtedy HTML logowania, nie JSON.
11. **Testy: hasher MD5 tylko w `config.settings.test`** (pytest). Nie kopiuj go do
    `dev.py`/`prod.py`.
