# Arena Emocji — aplikacja do quizów edukacyjnych

## Nazwa i autorzy

**Nazwa projektu:** Arena Emocji.

**Autor:** Arkadiusz Cebula.

**Przedmiot:** Technologie webowe — projekt semestralny „Bezpieczna aplikacja webowa”.

## Cel aplikacji

Aplikacja jest przeznaczona dla uczniów oraz nauczyciela prowadzącego powtórki materiału. Ma umożliwiać rozwiązywanie krótkich quizów w przeglądarce, automatyczne obliczanie punktów i przeglądanie wyników. Nauczyciel będzie zarządzać pytaniami w jednym miejscu, zamiast ręcznie sprawdzać odpowiedzi i zestawiać wyniki.

**Przykład użycia:** nauczyciel przygotowuje zestaw pytań do powtórki. Uczeń loguje się, wybiera quiz i odpowiada na pytania. Serwer sprawdza odpowiedzi, zapisuje wynik i udostępnia go uczniowi. Nauczyciel może poprawić pytania przed kolejną rozgrywką.

## Planowane funkcje

1. Użytkownik zakłada konto, loguje się i wylogowuje.
2. Użytkownik przegląda dostępne quizy i wybiera zestaw do rozwiązania.
3. Użytkownik odpowiada na pytania i otrzymuje wynik obliczony przez serwer.
4. Użytkownik przegląda historię własnych wyników oraz ranking uczestników.
5. Administrator dodaje, edytuje i wyłącza pytania oraz quizy.
6. Administrator zarządza kontami i ich rolami.

W pierwszej działającej wersji powstanie jeden quiz typu ABCD: wyświetlenie pytania, przesłanie odpowiedzi, obliczenie punktów i zapisanie oraz wyświetlenie wyniku. Kolejne rodzaje gier i pokoje do wspólnej rozgrywki w sieci lokalnej będą rozszerzeniem po wykonaniu podstawowego zakresu.

## Technologie i dane

| Element | Planowane rozwiązanie |
| --- | --- |
| Interfejs | HTML5, CSS3 i JavaScript; obsługa formularzy i komunikacja z serwerem przez `fetch` |
| Backend | Python 3.10+; serwer HTTP i obsługa żądań w aplikacji |
| Baza danych | SQLite, dostępna wyłącznie dla backendu przez moduł `sqlite3` |
| Komunikacja | Żądania HTTP i odpowiedzi JSON; uruchomienie demonstracyjne na komputerze lokalnym |
| Kontrola wersji | Git; repozytorium z kodem, dokumentacją i testami |
| Testy | `unittest`, osobna tymczasowa baza oraz konta testowe |

W bazie będą przechowywane konta i role użytkowników, skróty danych uwierzytelniających z indywidualną solą, sesje, quizy, pytania i wyniki. Hasła nie będą zapisywane jawnym tekstem. Poprawne odpowiedzi i naliczanie punktów będą obsługiwane po stronie serwera. Plik bazy z danymi użytkowników nie będzie dodawany do repozytorium.

## Zagrożenia i planowane zabezpieczenia

| Zagrożenie | Planowane zabezpieczenie | Sposób sprawdzenia |
| --- | --- | --- |
| Użytkownik próbuje odczytać cudzą historię po zmianie identyfikatora w żądaniu. | Serwer ustala użytkownika na podstawie sesji i sprawdza uprawnienia do danych. | Z konta A próba pobrania historii konta B; odpowiedź nie może zawierać danych B. |
| Uczestnik próbuje dodać lub usunąć pytanie przez endpoint administratora. | Sprawdzenie roli na serwerze przed wykonaniem operacji. | Żądanie z konta uczestnika powinno otrzymać odmowę; stan pytania w bazie pozostaje bez zmian. |
| Klient wysyła nieprawidłowy identyfikator quizu, zbyt długi tekst albo własną liczbę punktów. | Walidacja typów, długości i zakresów na serwerze; punkty wyliczane wyłącznie przez backend. | Żądanie pomijające formularz zostaje odrzucone albo pole z punktami nie wpływa na wynik; brak nieprawidłowego zapisu. |
| W nazwie użytkownika lub treści pytania pojawia się kod HTML. | Wyświetlanie treści użytkownika jako tekstu; bezpieczne kodowanie przy tworzeniu HTML. | Wartość `<b>Próba</b>` wyświetla się dosłownie, bez pogrubienia. |
| Dane formularza zmieniają znaczenie zapytania SQL. | Zapytania parametryzowane zamiast doklejania danych do SQL. | Tekst zawierający apostrof i fragment SQL nie zmienia logiki zapytania ani struktury bazy. |
| Ktoś wielokrotnie zgaduje hasło użytkownika. | Ograniczenie prób logowania, bezpieczne przechowywanie haseł i wygasanie sesji. | Seria nieudanych logowań powoduje czasową blokadę kolejnych prób. |

Powyższa tabela opisuje plan, a nie wyniki wykonanych testów. W etapie bezpieczeństwa zostaną udokumentowane co najmniej trzy testy: dane wejściowe, oczekiwane zachowanie, rzeczywista odpowiedź serwera oraz stan danych po próbie. Testy będą wykonywane wyłącznie we własnej aplikacji, na danych testowych.

## Plan pracy

| Etap | Zakres | Rezultat |
| --- | --- | --- |
| 1. Zgłoszenie pomysłu | Określenie celu, funkcji, technologii, zagrożeń i harmonogramu; przygotowanie repozytorium. | README i link do repozytorium. |
| 2. Pierwsza funkcja od początku do końca | Jeden quiz ABCD, formularz odpowiedzi, obliczenie punktów, zapis i odczyt wyniku z SQLite. | Działający scenariusz: pytanie → odpowiedź → wynik. |
| 3. Konta i wyniki | Rejestracja, logowanie, sesje, powiązanie wyników z kontem, własna historia i ranking. | Rozgrywka na oddzielnych kontach użytkowników. |
| 4. Administracja | Dodawanie i edytowanie quizów oraz pytań; zarządzanie kontami i rolami. | Panel administratora i sprawdzanie uprawnień przez serwer. |
| 5. Bezpieczeństwo i testy | Przegląd kontroli dostępu, walidacji, wyświetlania treści i logowania; testy i poprawki. | Opis co najmniej trzech testów zabezpieczeń wraz z rzeczywistymi wynikami. |
| 6. Oddanie i prezentacja | Sprawdzenie uruchomienia na innym komputerze, uzupełnienie instrukcji i przygotowanie demonstracji. | Działająca aplikacja, dokumentacja oraz pokaz scenariusza i jednego testu zabezpieczenia. |

Zabezpieczenia będą dodawane wraz z funkcjami; etap 5 służy ich całościowemu sprawdzeniu. W ramach projektu indywidualnego autor odpowiada za interfejs, backend, bazę danych, testy i dokumentację. W przypadku realizacji w parze ten opis zostanie zastąpiony podziałem obowiązków między wskazanych autorów.

Postępy będą zapisywane w Git jako konkretne zmiany z czytelnymi opisami. Repozytorium nie będzie zawierać haseł, kluczy, prywatnej konfiguracji ani baz z rzeczywistymi danymi użytkowników.

## Uruchomienie i stan etapu

Ten etap zawiera zgłoszenie pomysłu i plan realizacji. Nie zawiera jeszcze wersji aplikacji do uruchomienia. Instrukcja uruchomienia zostanie dodana wraz z pierwszą działającą funkcją i uzupełniana w kolejnych etapach.
