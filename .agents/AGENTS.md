# scAnt Project Rules

See also `AGENTS.md` (root) for commands and quick reference.

Poniższe reguły to nasze główne ustalenia architektoniczne dla tego obszaru roboczego (projektu scAnt). Agent AI powinien się do nich zawsze stosować.

1. **Sprzęt Sterujący:** Projekt jest w całości oparty o Raspberry Pi jako centralną jednostkę obliczeniową. Za ruch odpowiada płyta BTT SKR Pico z oprogramowaniem Klipper.
2. **Przechwytywanie Obrazu:** Do robienia zdjęć używamy natywnie RPI-HQ-CAMERA z wykorzystaniem biblioteki `picamera2`. Rezygnujemy z obsługi starych urządzeń (FLIR, DSLR).
3. **Komunikacja Klipper:** Aplikacja nie generuje komend systemowych do oddzielnych sterowników (jak robiono to kiedyś przez `ticcmd`). Aplikacja komunikuje się z Moonrakerem (HTTP REST API) w celu sterowania płytą BTT SKR Pico.
4. **Brak GUI (Interfejs):** Interfejs okienkowy PyQt5 został całkowicie usunięty ze względu na trudności z uruchamianiem na "bezgłowym" RPi. Głównym punktem wejścia do aplikacji jest teraz serwer REST API (FastAPI) oraz narzędzia wiersza poleceń (CLI).
5. **Konteneryzacja:** API oraz CLI są uruchamiane za pomocą Dockera (Docker Compose), a wszystkie wymagane piny i urządzenia komunikacyjne (np. VCHIQ dla kamery) muszą być odpowiednio zmapowane w kontenerze. Bezwzględnie unikamy instalowania jakichkolwiek zależności czy bibliotek globalnie na komputerze/systemie hosta – wszystko ma być zamknięte w Dockerze.
6. **Kontrola Wersji:** Do zarządzania repozytorium i wykonywania operacji na systemie kontroli wersji używamy narzędzia `gh` (GitHub CLI) zamiast klasycznego `git`.
7. **Scentralizowane Logowanie (Console-First):** Zamiast pisać własne, wbudowane systemy zapisujące logi do plików tekstowych, cała diagnostyka (błędy, logi, strumienie wykonania) musi trafiać na standardowe wyjście (`stdout`/`stderr`). Będą one przechwytywane natywnie przez mechanizmy logowania platformy Docker. Nigdy nie przekierowujemy logów do `/dev/null`.
8. **Wbudowane Watchdogi:** Składniki systemu (np. połączenie z Klipperem/Moonrakerem, status kamery) powinny być stale monitorowane przez mechanizmy typu watchdog. Mają one raportować na bieżąco status, czas działania (uptime) oraz ewentualne statystyki błędów bezpośrednio do logów.
9. **Architektura "Single-Command":** Projekt ma być na tyle dobrze przygotowany, aby całe środowisko można było uruchomić od zera do działania pojedynczą komendą: `docker compose up --build`.
10. **Separacja Zadań (Separation of Concerns):** Narzucamy ścisły podział na logikę główną (komunikacja ze sprzętem w tle), warstwę interfejsu (skrypty CLI) oraz warstwę zarządzającą (np. webowe API).
