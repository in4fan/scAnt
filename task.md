# Plan Konwersji Kodu (Lista Zadań)

- [x] **Krok 1: Oczyszczanie repozytorium**
  - [x] Usunięcie głównego pliku `scAnt.py` (stare GUI oparte na PyQt5).
  - [x] Usunięcie starych plików obsługi kamer z folderu `GUI` (m.in. `Live_view_FLIR.py`, `Live_view_DSLR.py`).
  - [x] Odpięcie powiązanych zależności dla kamer Spinnaker z `conda_environment/`.

- [x] **Krok 2: Konfiguracja Klippera i BTT SKR Pico**
  - [x] Utworzenie pliku `config/skr_pico_klipper.cfg` ze zmapowanymi pinami płyty na osie (X=ramię, Y=stół, Z=focus) oraz logiką Sensorless Homing (TMC2209 diag_pin).
  - [x] Utworzenie pliku `docs/hardware_wiring.md` z przejrzystą tabelą przypisania pinów i instrukcją podpięcia zasilania.

- [x] **Krok 3: Implementacja kontrolera kamery (RPI-HQ-CAMERA)**
  - [x] Napisanie `scripts/camera_controller.py` opartego o `picamera2`.
  - [x] Implementacja metod do konfiguracji naświetlania, podglądu (preview) i zapisywania pełnego zdjęcia (capture).

- [x] **Krok 4: Integracja kontrolera silników (Moonraker)**
  - [x] Zrefaktoryzowanie `scripts/Scanner_Controller.py`.
  - [x] Usunięcie logiki systemowego `ticcmd`.
  - [x] Dodanie klienta HTTP (np. z użyciem `requests`) łączącego się z API Moonrakera (np. `http://localhost:7125/printer/gcode/script`).
  - [x] Wdrożenie logiki oczekującej na asynchroniczne zakończenie ruchu przez Moonrakera przed zrobieniem zdjęcia.

- [x] **Krok 5: Budowa API (FastAPI) i narzędzia CLI**
  - [x] Stworzenie `api_server.py` z endpointami kontrolującymi stan skanera (`/scan/start`, `/scan/status`, `/camera/capture`).
  - [x] Stworzenie `scant_cli.py` jako parsera z `argparse` do uruchamiania poleceń skanowania i kalibracji z linii komend lub skryptów automatyzujących.

- [x] **Krok 6: Środowisko Docker i konteneryzacja**
  - [x] Wygenerowanie `Dockerfile` budującego system z niezbędnymi paczkami do FastAPI, OpenCV i `picamera2`.
  - [x] Wygenerowanie `docker-compose.yml`, który połączy kontener serwera API, zapewniając odpowiednie mapowania (`/dev/vchiq` dla kamery na Raspberry Pi, port dla FastAPI).

- [x] **Krok 7: Dokumentacja końcowa i sprzątanie**
  - [x] Zaktualizowanie `README.md`, aby informowało o nowym użyciu serwera na Raspberry Pi.
  - [x] Stworzenie instrukcji uruchamiania `docker compose up --build`. podsumowującego jak uruchomić całość na czystym Raspberry Pi.
