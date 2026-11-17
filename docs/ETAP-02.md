# Etap 2 — konta, zabezpieczenia i podstawowe funkcje

Autor: Arkadiusz Cebula. Data: 17 listopada 2026.

## Wdrożony zakres

- Rejestracja, logowanie, wylogowanie i osobne formularze z komunikatami błędów.
- Dodawanie prywatnego quizu ABCD (1–10 pytań), wyświetlanie własnych quizów i wspólnego quizu startowego.
- Rozwiązywanie quizu i obliczanie punktów przez serwer.
- Historia ostatnich 100 wyników przypisana do zalogowanego konta.

## Zabezpieczenia

- PBKDF2-HMAC-SHA256, 600 000 iteracji i losowa 16-bajtowa sól. Baza zawiera kolumnę `password_hash`, a nie hasła jawne.
- Losowy 256-bitowy token sesji w ciasteczku `HttpOnly; SameSite=Lax`. Baza przechowuje tylko SHA-256 tokenu. Sesja wygasa po godzinie i jest usuwana przy wylogowaniu.
- Nagłówek `X-CSRF-Token` wymagany dla operacji zalogowanego użytkownika; sprawdzanie `Origin` i typu JSON.
- Walidacja loginu, hasła, potwierdzenia hasła, długości pól, liczby pytań i odpowiedzi zarówno w interfejsie, jak i w backendzie.
- Ochrona stron `/quizy`, `/dodaj`, `/historia` przez przekierowanie HTTP 303 do logowania. API zwraca 401 dla niezalogowanego użytkownika.
- Weryfikacja właściciela quizu; odczyt historii zawsze ograniczony do użytkownika z sesji.
- Parametryzowane zapytania SQLite, bezpieczne kodowanie tekstu w HTML i polityka CSP.
- Ograniczenie do 15 prób logowania/rejestracji z jednego IP w ciągu 5 minut.
- Baza danych, hasła, sesje i pliki konfiguracyjne pozostają poza Git.

## Testy

Polecenie: `python -m unittest discover -s tests -v`.

Wynik sprawdzenia z 17.11.2026: **14 testów zakończonych powodzeniem**.
Testy tworzą osobną bazę tymczasową; nie korzystają z danych użytkownika.

| Sprawdzenie | Oczekiwany i uzyskany rezultat |
| --- | --- |
| Rejestracja i baza | Hash PBKDF2 zamiast hasła; sól różna dla jednakowych haseł. |
| Niepoprawne dane bez formularza | HTTP 400; brak zapisu konta lub nieprawidłowego quizu. |
| Zajęty login | HTTP 409 także przy zmianie wielkości liter. |
| Niepoprawne logowanie | HTTP 401 z ogólnym komunikatem o błędnych danych. |
| Wylogowanie, wygasła i podrobiona sesja | HTTP 401 przy próbie ponownego dostępu. |
| Dostęp bez logowania | HTTP 303 do formularza dla podstron i 401 dla API. |
| CSRF i obce źródło | HTTP 403; sesja pozostaje niezmieniona. |
| Prywatny quiz innego konta | HTTP 404 przy odczycie i przesyłaniu odpowiedzi. |
| Cudza historia | Brak cudzych wyników nawet po dodaniu `user_id` do adresu. |
| Punkty podmienione przez klienta | Pole `score` nie wpływa na wynik obliczany przez serwer. |
| Błędne odpowiedzi | HTTP 400, wynik nie jest zapisywany. |
| Fragment SQL w tytule | Zapis jako tekst; tabela użytkowników pozostaje nienaruszona. |
| Limit prób | HTTP 429 po osiągnięciu limitu. |
| Próba odczytu bazy lub źródeł przez HTTP | HTTP 404; odpowiedzi zawierają nagłówki ochronne. |

Test przeglądarkowy obejmuje utworzenie konta testowego, za krótkie hasło, błędne logowanie, dodanie quizu, rozwiązanie i historię oraz przekierowanie po wylogowaniu. Zrzuty i opis znajdują się w osobnym dokumencie do oddania.

## Ograniczenia tego etapu

Wersja demonstracyjna działa lokalnie przez HTTP. Domyślnie serwer nasłuchuje tylko na `127.0.0.1`. Publikacja w Internecie wymaga serwera wdrożeniowego, HTTPS oraz `ARENA_COOKIE_SECURE=1`. Bieżący zakres nie obejmuje jeszcze panelu administratora, rankingu ani trybu LAN. Wcześniejszy dokument założeń opisuje zakres planowany na cały semestr.
