# ADR-0003 — Weryfikacja dwuetapowa (TOTP) przez `django-otp`

| | |
|---|---|
| Status | zaakceptowany przez zespół [DEV]/[SEC]; wdrożenie 2FA — decyzja PO 2026-10-16 („rób US-010”); tryb dobrowolny — Z-39, do potwierdzenia |
| Data | 2026-10-16 |
| Właściciel | [DEV] z udziałem [SEC] |
| Powiązania | US-010, SEC-006; AUDYT R6; TM-36; ASVS 4.3.1; RYZYKA RR-10, W-2; `warehouse/two_factor.py` |

## Kontekst

Konto Administratora i superusera daje pełny dostęp do kont, dziennika i `/admin/`. Samo hasło
(nawet w argon2, US-008, i z blokadą konta, US-009) nie chroni przed jego wyciekiem lub phishingiem.
Prompt PO (sekcja 6) przewiduje 2FA dla adminów jako opcję.

## Rozważane opcje

| Opcja | Zalety | Wady |
|---|---|---|
| Własna implementacja TOTP (RFC 6238) | brak zależności | kryptografia i ochrona przed powtórzeniem kodu do napisania i utrzymania |
| **`django-otp` (+ plugin `otp_totp`)** | dojrzała biblioteka; `OTPMiddleware` i `user.is_verified()`; ochrona przed ponownym użyciem kodu i dławienie prób; własne migracje | nowa zależność (czysty Python) i 1 tabela |
| `django-two-factor-auth` | gotowe ekrany, SMS, kody zapasowe | ciężka (formtools, phonenumbers), własny przepływ logowania zastępuje nasz `LoginView` z limitami |
| WebAuthn / klucze sprzętowe | odporne na phishing | wymaga HTTPS i kluczy; za duży koszt przy 2 operatorach |

## Decyzja

`django-otp==1.7.4` z pluginem TOTP. Nasz kod (`warehouse/two_factor.py`):
- `/2fa/` (rola Administrator) — kod QR (`qrcode`, już w zależnościach) i potwierdzenie pierwszym kodem;
- `/2fa/weryfikacja/` — drugi krok po haśle; nieudany kod zapisuje „Nieudane logowanie” i liczy się do
  blokady konta z US-009 (10 / 15 min);
- `TwoFactorRequiredMiddleware` — konto z **potwierdzonym** urządzeniem i niezweryfikowaną sesją widzi
  tylko ekran kodu i wylogowanie (wszystkie widoki, także `/admin/`);
- `manage.py reset_2fa <login>` — utrata telefonu (RUNBOOK §8.3b).

Tryb **dobrowolny** (Z-39): każdy Administrator sam włącza 2FA; Operator i Podgląd nie mają tej opcji.

## Konsekwencje

- Nowe migracje biblioteki (`otp_totp` 0001–0003) — tylko nowa tabela, bez zmian w danych aplikacji.
- Każde żądanie zalogowanego użytkownika z niezweryfikowaną sesją robi jedno zapytanie o urządzenie
  (pomijalne przy tej skali).
- Brak kodów zapasowych — odzyskanie dostępu wyłącznie przez superusera (`reset_2fa`); jeśli superuser
  sam straci telefon, reset w kontenerze (`docker compose exec web python manage.py reset_2fa <login>`).
- Wymuszenie 2FA dla wszystkich Administratorów to później jedna zmiana w middleware (osobna decyzja PO).
