# Szczegółowy Plan Architektury i Wdrożeń (scAnt)

Poniższy plan zawiera podział na główne filary implementacyjne dla naszego systemu w architekturze RPi + Cloud/PC. Służy jako stała lista zadań (Checklista) na wypadek, gdyby praca została przerwana.

## Filar 1: Integracja Cloud Serverless (Zakończone) ✅
*Działania dla architektury Serverless np. z wykorzystaniem platformy RunPod oraz dowolnego dostawcy chmurowego przez rclone.*

- [x] Stworzenie skryptu `handler.py` z logiką RunPod i elastycznymi wywołaniami `rclone` (Google Drive, S3, FTP itp.).
- [x] Utworzenie pliku `Dockerfile.serverless` bazującego na obrazie NVIDIA, z doinstalowanymi `rclone` i `runpod`.
- [x] Rozbudowa interfejsu `scant_cli.py` o komendę `runpod`, obsługującą wysyłanie paczek w górę, pingowanie statusu oraz pobieranie wyniku w dół.

---

## Filar 2: System Watchdogów API (Zakończone) ✅
*Zgodnie z regułą #8 (Wbudowane Watchdogi) i #7 (Scentralizowane Logowanie).*

- [x] **Stworzenie modułu `watchdog.py`**:
  - Pętla asynchroniczna sprawdzająca stan demona Moonraker (np. GET `/printer/info`).
  - Pętla weryfikująca działanie kamery (`picamera2` lub dostęp do `/dev/video0`).
- [x] **Rejestracja w `api_server.py`**:
  - Podpięcie Watchdogów do startu aplikacji FastApi (np. `@app.on_event("startup")`).
- [x] **Logowanie na standardowe wyjście**:
  - Skonfigurowanie loggera w taki sposób, aby przesyłał metadane o uptime i statusie bezpośrednio do `stdout` (gdzie złapie je Docker).
- [x] **Endpoint API `/health`**:
  - Stworzenie szybkiej trasy zwracającej stan zdrowia (błędy, ostatnie logi) w formacie JSON dla CLI lub zewnętrznego monitoringu.

---

## Filar 3: System Testów Automatycznych (Zakończone) ✅
*Aby zapobiegać błędom i regresjom przy dalszych modyfikacjach kodu.*

- [x] **Zależności testowe**:
  - Dodanie biblioteki `pytest` i `httpx` (do testowania API) do głównego `Dockerfile` dla RPi.
- [x] **Testy API (`tests/test_api.py`)**:
  - Utworzenie mocków (zaślepek) dla zapytań HTTP kierowanych normalnie do Moonrakera.
  - Sprawdzenie poprawności zwracania statusów 200 przez trasy `/health`, `/motor/home`, `/scan/files`.
- [x] **Testy CLI (`tests/test_cli.py`)**:
  - Walidacja parsera `argparse`. Zapewnienie, że niedozwolone kombinacje argumentów są odrzucane.
  - Test komendy `runpod` z odciętym siecią (symulacja braku internetu/dostępu do S3).

---

## Instrukcja Kontynuacji (Dla Agenta AI)
W przypadku wznowienia pracy lub odczytania tego pliku przez innego agenta:
1. Sprawdź, na jakim etapie zatrzymały się zaznaczenia checkboxów `[ ]`.
2. Zacznij od najbliższego niezakończonego zadania, analizując obecny stan kodu.
3. Po zakończeniu sekcji oznacz ją jako `[x]`.
