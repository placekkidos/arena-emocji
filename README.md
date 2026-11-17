# Arena Emocji — aplikacja do quizów edukacyjnych

**Autor: Arkadiusz Cebula**
**Etap 2 — 17 listopada 2026**

Repozytorium: https://github.com/placekkidos/arena-emocji

## Co działa

Rejestracja, logowanie hasłem i wylogowanie. Po zalogowaniu użytkownik może:

1. Dodawać prywatne quizy ABCD (1–10 pytań) i przeglądać swoją bibliotekę.
2. Rozwiązywać quizy; wynik oblicza i zapisuje serwer.
3. Przeglądać historię własnych wyników, także po ponownym zalogowaniu.

Aplikacja zawiera wspólny quiz startowy. Nie tworzy domyślnych kont ani haseł.

## Uruchomienie

Wymagany Python 3.10 lub nowszy. Nie trzeba instalować dodatkowych pakietów.

```sh
git clone https://github.com/placekkidos/arena-emocji.git
cd arena-emocji
python app.py
```

Otwórz http://127.0.0.1:8080 i utwórz konto. W Windows można użyć `start.bat`.
Gdy port jest zajęty: `python app.py --port 8091`.
Serwer zakończ przez Ctrl+C. Baza SQLite `data/arena.db` tworzy się automatycznie.
Do zmiany ścieżki bazy służy zmienna `ARENA_DB`.

Login: 3–30 znaków ASCII (litery, cyfry i `_`). Hasło: 12–128 znaków, identyczne z potwierdzeniem.
W tej wersji własne quizy i historia są prywatne. Panel administratora i ranking należą do kolejnych etapów.

## Bezpieczeństwo

- Hasła: PBKDF2-HMAC-SHA256, 600 000 iteracji, indywidualna losowa sól 16 bajtów.
- Sesja: losowy token 32 bajty, ciasteczko `HttpOnly; SameSite=Lax`, ważność 1 godzina.
- Token sesji jest zapisany w SQLite wyłącznie jako SHA-256; wylogowanie unieważnia sesję na serwerze.
- Token CSRF oraz kontrola Origin dla operacji zapisujących dane.
- Walidacja pól w JavaScript i niezależnie na serwerze.
- Ochrona podstron przed niezalogowanymi oraz kontrola dostępu do danych w API.
- Zapytania parametryzowane SQLite, kodowanie tekstu HTML, CSP i brak cache odpowiedzi.
- Limit 15 prób uwierzytelniania na 5 minut dla jednego IP.

Stosowany jest token sesji, a nie JWT: jedna aplikacja i jedna baza umożliwiają natychmiastowe unieważnienie tokenu przy wylogowaniu.

Serwer demonstracyjny nasłuchuje domyślnie na `127.0.0.1` i używa HTTP.
Wdrożenie internetowe wymaga HTTPS, serwera wdrożeniowego i `ARENA_COOKIE_SECURE=1`.
Nie udostępniaj w Git pliku bazy, aktywnych tokenów ani prawdziwych haseł.

Parametry haszowania: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

## Testy

```sh
python -m unittest discover -s tests -v
python -m py_compile app.py auth.py tests/test_app.py
node --check static/app.js
```

Node.js jest opcjonalny i służy tylko do sprawdzenia składni JavaScript.
Wynik: **14 testów backendu zakończonych powodzeniem** (17.11.2026).
Testy używają tymczasowej bazy i niezależnych klientów HTTP.
Scenariusze, zabezpieczenia i ograniczenia opisano w [raporcie etapu 2](docs/ETAP-02.md).

## Pliki

- `app.py` — backend HTTP, SQLite, kontrola dostępu, quizy i wyniki.
- `auth.py` — haszowanie haseł i tokenów.
- `static/` — formularze, widoki, style i walidacja przeglądarkowa.
- `tests/test_app.py` — testy integracyjne i testy zabezpieczeń.
- `docs/ETAP-02.md` — opis zmian i rezultatów testów.
- Dokument Word z założeniami — plan całego semestru z pierwszego etapu.
