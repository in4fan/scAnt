%% cmdview.m - Analiza kodu źródłowego projektu scAnt
%% Wygenerowano: 2026-06-30
%%
%% Spis treści:
%%   1. Błędy krytyczne (Critical Bugs)
%%   2. Błędy średnie (Medium Bugs)
%%   3. Problemy jakości kodu (Code Quality Issues)
%%   4. Problemy z Dockerem i wdrożeniem
%%   5. Propozycje ulepszeń i nowych funkcji


%% ========================================================================
%% 1. BŁĘDY KRYTYCZNE (Critical Bugs)
%% ========================================================================

%% 1.1 Niezdefiniowana zmienna `s3_stacked_path` w handler.py
%% Plik: handler.py, linia 61
%% Problem: W komunikacie zwrotnym użyto zmiennej `s3_stacked_path`,
%% która nigdy nie została zdefiniowana. Spowoduje to NameError przy
%% każdym pomyślnym zakończeniu zadania RunPod.
%% Rozwiązanie: Zastąpić `s3_stacked_path` na `remote_stacked_path`.

%% 1.2 Nieprawidłowa flaga `-i` w wywołaniach processStack.py
%% Pliki: handler.py (linia 46), scant_cli.py (linia 103)
%% Problem: Skrypt processStack.py definiuje argument jako `-p` / `--path`,
%% ale oba wywołania używają flagi `-i`, która nie istnieje w parserze.
%% Spowoduje to zignorowanie ścieżki lub błąd.
%% Rozwiązanie: Zmienić `-i` na `-p` w obu wywołaniach.

%% 1.3 `cv2.destroyAllWindows()` w kontenerze headless Docker
%% Plik: processStack.py, linia 819 (w bloku main)
%% Problem: Wywołanie cv2.destroyAllWindows() w środowisku bez X11
%% (headless Docker) może rzucać wyjątki lub powodować segfaulty.
%% Rozwiązanie: Usunąć tę linię lub opakować w try/except.

%% 1.4 `exit()` zamiast `return` w processStack.py
%% Plik: processStack.py, linie 834 i 1016 (w bloku main)
%% Problem: Użycie `exit()` w skrypcie wywołuje SystemExit, co zabija
%% cały proces Pythona, w tym wątek workera Dockera. W funkcji
%% `stack_images()` (linia 396) problem został już naprawiony, ale
%% w bloku main pozostał.
%% Rozwiązanie: Zastąpić `exit()` na `sys.exit()` lub lepiej na `return`.

%% 1.5 Brak importu `opencv-contrib-python-headless` w Dockerfile.worker
%% Plik: Dockerfile.worker
%% Problem: Moduł `cv2.ximgproc.createStructuredEdgeDetection` wymaga
%% pakietu `opencv-contrib-python-headless`, ale zainstalowany jest
%% tylko `opencv-python-headless`. Bez niego maskowanie (mask_images)
%% zawiedzie z AttributeError.
%% Rozwiązanie: Zmienić zależność w Dockerfile.worker i Dockerfile.serverless.

%% 1.6 Brak `opencv-python-headless` w głównym Dockerfile (RPi)
%% Plik: Dockerfile
%% Problem: Główny Dockerfile (API na Raspberry Pi) nie instaluje
%% opencv-python-headless, a camera_controller.py wymaga cv2
%% (do kodowania JPEG). Kontener się wysypie przy próbie streamingu.
%% Rozwiązanie: Dodać opencv-python-headless i numpy do pip install
%% w głównym Dockerfile.

%% 1.7 Potencjalna race condition w watchdog.py
%% Plik: watchdog.py
%% Problem: Globalny słownik `health_status` jest współdzielony między
%% wieloma async taskami bez mechanizmu synchronizacji (lock).
%% W teorii, jednoczesny zapis do `health_status` z różnych coroutine
%% może prowadzić do race condition. W praktyce CPython GIL chroni
%% przed tym w przypadku prostych przypisań, ale przy bardziej
%% złożonych operacjach może to być problem.
%% Rozwiązanie: Użyć threading.Lock lub asyncio.Lock do synchronizacji
%% dostępu do współdzielonego stanu.

%% 1.8 MJPEG generator nie ma warunku zatrzymania
%% Plik: api_server.py, linie 105-110 (funkcja mjpeg_generator)
%% Problem: Pętla `while True` w generatorze MJPEG działa bez przerwy,
%% nawet gdy klient rozłączy połączenie. Powinna reagować na
%% zamknięcie połączenia (np. sprawdzać czy generator jest jeszcze
%% potrzebny).
%% Rozwiązanie: Dodać mechanizm wykrywania zamknięcia połączenia
%% lub użyć StreamingResponse z odpowiednim middlewarem.


%% ========================================================================
%% 2. BŁĘDY ŚREDNIE (Medium Bugs)
%% ========================================================================

%% 2.1 `os.system()` zamiast `subprocess.run()`
%% Plik: processStack.py, linie 173-228, 568-571, oraz w createAlphaMask
%% Problem: os.system() jest podatny na shell injection i nie pozwala
%% na przechwycenie stderr/stdout. Ponadto `os.system("rm ...")` to
%% antywzorzec - Python ma `os.remove()` i `pathlib.Path.unlink()`.
%% Rozwiązanie: Zamienić wszystkie wystąpienia os.system() na
%% subprocess.run() z listą argumentów.

%% 2.2 `cv2.findContours()` - niezgodność API między wersjami OpenCV
%% Plik: processStack.py, funkcja findSignificantContour (linie 478-488)
%% Problem: W nowszych wersjach OpenCV (>=4.5.3) funkcja
%% cv2.findContours() zwraca tylko 2 wartości (contours, hierarchy),
%% a w starszych zwraca 3 (image, contours, hierarchy). Kod próbuje
%% obsłużyć oba przypadki przez try/except, ale to kruche rozwiązanie.
%% Nie wszystkie wersje mają też atrybut RETR_TREE dostępny w ten sam sposób.
%% Rozwiązanie: Użyć cv2.RETR_TREE z cv2.CHAIN_APPROX_SIMPLE bezpośrednio
%% i sprawdzić wersję OpenCV przed wyborem API.

%% 2.3 Nieobsłużony wyjątek przy braku config.yaml w projekcie
%% Plik: processStack.py, blok main (linia 1018)
%% Problem: Jeśli w folderze projektu nie ma pliku .yaml, skrypt
%% wypisuje "No config file found in folder!" i kończy działanie.
%% Brak jednak mechanizmu tworzenia domyślnego pliku konfiguracyjnego
%% na podstawie parametrów CLI.
%% Rozwiązanie: Dodać generowanie domyślnego config.yaml, gdy nie
%% zostanie znaleziony.

%% 2.4 `write_exif_to_img` używa subprocess.Popen bez oczekiwania
%% Plik: scripts/write_meta_data.py, linia 49
%% Problem: Funkcja używa `subprocess.Popen(complete_command)` bez
%% wywołania `.wait()`, co oznacza, że proces exiftool może być
%% uruchomiony asynchronicznie i nie zakończyć się przed kolejnymi
%% operacjami na pliku. W processStack.py (linia 998) po zapisie EXIF
%% od razu zapisywany jest następny plik, co może prowadzić do
%% wyścigu (race condition) na plikach.
%% Rozwiązanie: Użyć subprocess.run() zamiast Popen, lub dodać .wait().

%% 2.5 Potencjalny błąd przy usuwaniu katalogów tymczasowych
%% Plik: processStack.py, funkcja stack_images (linie 421-426)
%% Problem: `os.rmdir()` usunie katalog tylko jeśli jest pusty.
%% Jeśli wcześniejsze usunięcie plików tymczasowych nie powiedzie się,
%% rmdir rzuci OSError.
%% Rozwiązanie: Użyć shutil.rmtree() z try/except.

%% 2.6 `ScannerController.setScanRange()` może tworzyć puste zakresy
%% Plik: scripts/Scanner_Controller.py, linie 91-93
%% Problem: Jeśli np. range(min_val, max_val, step) jest pusty
%% (np. gdy step > max_val - min_val), skanowanie przejdzie przez
%% 0 iteracji, ale nie generuje ostrzeżenia w logach.
%% Rozwiązanie: Dodać walidację i warning, gdy zakres jest pusty.

%% 2.7 `correctName()` formatuje wartość bezwzględną, gubiąc znak
%% Plik: scripts/Scanner_Controller.py, linia 35
%% Problem: Funkcja `correctName` używa `abs(int(val))`, co traci
%% informację o znaku ujemnym. Nazwy plików dla ujemnych pozycji
%% (np. Z=-250) będą wyglądać tak samo jak dla dodatnich (Z=250).
%% Rozwiązanie: Dodać prefix '-' dla wartości ujemnych lub użyć
%% formatowania z zachowaniem znaku.

%% 2.8 API `/scan/start` nie waliduje zakresów skanowania
%% Plik: api_server.py, linia 75-83
%% Problem: Funkcja run_scan_task() przekazuje wartości bez
%% walidacji np. czy step != 0 (co by zapętliło skanowanie),
%% czy min < max itp.
%% Rozwiązanie: Dodać walidację w ScanConfig z Pydantic @validator.


%% ========================================================================
%% 3. PROBLEMY JAKOŚCI KODU (Code Quality Issues)
%% ========================================================================

%% 3.1 `@app.on_event("startup")` - deprecation w FastAPI
%% Plik: api_server.py, linia 14
%% Problem: Metoda on_event("startup") jest oznaczona jako deprecated
%% od FastAPI 0.95+. Zalecane jest użycie lifespan context managera.
%% Rozwiązanie: Zrefaktorować na wzorzec lifespan.

%% 3.2 Statyczne mount() przed dynamicznymi trasami
%% Plik: api_server.py, linie 19-22
%% Problem: FastAPI mountuje StaticFiles przed dodaniem tras
%% dynamicznych. Może to powodować, że żądania do /gui/... będą
%% obsłużone przez StaticFiles zamiast przez router.
%% Rozwiązanie: Przenieść mount() na koniec pliku.

%% 3.3 Globalne zmienne `is_scanning` - problem z wielowątkowością
%% Plik: api_server.py, linia 47
%% Problem: `is_scanning` to globalna flaga bez synchronizacji.
%% W środowisku ASGI (Uvicorn z wieloma workerami) mogą wystąpić
%% race condition przy równoczesnym dostępie.
%% Rozwiązanie: Użyć threading.Lock() lub AtomicBoolean.

%% 3.4 Brak typu dla globalnych flag w processStack.py
%% Plik: processStack.py
%% Problem: Zmienne `exitFlag`, `exitFlag_stacking`, `exitFlag_alpha`
%% są używane jako globalne znaczniki zatrzymania wątków, ale nie są
%% typowane i nie użyto threading.Event(), który jest do tego
%% przeznaczony. Obecne rozwiązanie (polling zmiennej) jest podatne
%% na race condition.
%% Rozwiązanie: Użyć threading.Event() zamiast globalnych intów.

%% 3.5 Zduplikowany plik model.yml (35 MB x 2 = 70 MB)
%% Pliki: scripts/model.yml i legacy_scripts/model.yml
%% Problem: Ten sam 35-megabajtowy plik modelu krawędziowego OpenCV
%% istnieje w dwóch kopiach. To niepotrzebnie puchnie repozytorium.
%% Rozwiązanie: Usunąć duplikat i użyć Git LFS dla pozostałego.

%% 3.6 Zduplikowany kod w processStack.py (blok main i funkcje)
%% Problem: Kod w bloku `if __name__ == "__main__"` w processStack.py
%% powiela logikę z funkcji `stack_images()` i `mask_images()`.
%% Główna różnica to użycie wielowątkowości w bloku main vs
%% sekwencyjnego przetwarzania w funkcjach.
%% Rozwiązanie: Zrefaktorować tak, by blok main używał tych samych
%% funkcji co API (stack_images, mask_images).

%% 3.7 Duplikacja ścieżki do model.yml w processStack.py
%% Plik: processStack.py
%% Problem: Ścieżka do model.yml jest zakodowana na sztywno
%% w `mask_images()` (linia 673) jako `scripts/model.yml`,
%% a w bloku main (linia 961) jako `scripts/model.yml`.
%% W obu przypadkach jest to relative path, który zależy od CWD.
%% Rozwiązanie: Użyć Path(__file__).parent dla niezależności od CWD.

%% 3.8 Stała ścieżka `/app/scans` w api_server.py
%% Problem: Ścieżki `/app/scans` i `/app/static` są zakodowane na
%% sztywno. Działa to tylko w Dockerze. Dla środowiska deweloperskiego
%% (uruchomienie bez Dockera) to nie zadziała.
%% Rozwiązanie: Użyć zmiennych środowiskowych z fallbackiem.


%% ========================================================================
%% 4. PROBLEMY Z DOCKEREM I WDROŻENIEM
%% ========================================================================

%% 4.1 Brak pliku .dockerignore
%% Problem: Brak .dockerignore powoduje, że COPY . /app kopiuje
%% do obrazu wszystko: .git (setki MB), external/ (90 plików Windows),
%% build.log, worker_build.log itp. Można zmniejszyć obraz o 50-80%.
%% Rozwiązanie: Dodać .dockerignore z wykluczeniami.

%% 4.2 Folder external/ z 90 plikami .exe i .dll (Windows)
%% Problem: ~90 plików binarnych Windows o łącznym rozmiarze
%% kilkudziesięciu MB niepotrzebnie puchnie repozytorium i obraz
%% Dockera, skoro pipeline jest Linux-only.
%% Rozwiązanie: Przenieść do osobnego release'u lub .gitignore.

%% 4.3 `pip install picamera2` może nie działać na python:3.11-slim
%% Plik: Dockerfile
%% Problem: picamera2 to biblioteka specyficzna dla Raspberry Pi,
%% która może wymagać konkretnych wersji systemowych i bibliotek.
%% Instalacja z PyPI na python:3.11-slim może się nie powieść,
%% szczególnie że nie ma tam wszystkich zależności systemowych
%% potrzebnych dla libcamera.
%% Rozwiązanie: Użyć dedykowanego obrazu bazowego dla Raspberry Pi
%% lub dodać wszystkie zależności systemowe.

%% 4.4 Montowanie /dev/dma_heap w docker-compose.yml
%% Problem: Urządzenie /dev/dma_heap jest mapowane do kontenera,
%% ale może nie istnieć na wszystkich wersjach RPi OS lub może
%% wymagać odpowiedniego jądra.
%% Rozwiązanie: Sprawdzić dostępność i dodać warunkowe mapowanie.


%% ========================================================================
%% 5. PROPOZYCJE ULEPSZEŃ I NOWYCH FUNKCJI
%% ========================================================================

%% 5.1 Endpoint `/scan/cancel` - przerwanie skanowania
%% Obecnie brak możliwości anulowania skanowania z poziomu API.
%% Jedyny sposób to restart kontenera. Należy dodać flagę
%% `cancel_requested` sprawdzaną w pętli `runScan()`.

%% 5.2 Endpoint `/motor/position` - odczyt pozycji osi
%% Moonraker udostępnia GET /printer/objects/query?gcode_move,
%% z którego można odczytać aktualną pozycję [x, y, z].
%% Przydatne do wyświetlania w GUI.

%% 5.3 Przycisk "Snapshot" w Web GUI
%% Endpoint /camera/capture już istnieje, ale nie jest podpięty
%% w GUI. Przycisk obok strumienia MJPEG ułatwi sprawdzanie ostrości.

%% 5.4 Galeria zdjęć w Web GUI
%% Endpoint /scan/files/{project} już istnieje. Można dodać zakładkę
%% z miniaturami zdjęć z aktywnego projektu.

%% 5.5 Automatyczne generowanie config.yaml z API
%% Skrypt processStack.py szuka pliku .yaml w folderze projektu.
%% API mogłoby automatycznie generować plik konfiguracyjny na
%% podstawie parametrów skanowania i metadanych kamery.

%% 5.6 Wyświetlanie pozycji osi w GUI na żywo
%% Dodać okresowe odpytywanie Moonrakera o pozycję i wyświetlanie
%% w panelu kontrolnym. Użyteczne przy ręcznym ustawianiu ostrości.

%% 5.7 Walidacja Pydantic dla ScanConfig
%% Dodać validatory do ScanConfig (step > 0, min < max, itp.)
%% aby zapobiec błędnym konfiguracjom skanowania.

%% 5.8 Structured logging zamiast print()
%% W processStack.py i innych skryptach używane są print() zamiast
%% logger. Dla lepszej integracji z Dockerem warto użyć
%% structured logging (np. JSON).

%% 5.9 Testy integracyjne dla processStack.py
%% Obecne testy (test_api.py, test_cli.py) pokrywają tylko
%% podstawowe scenariusze. Brak testów dla kluczowej logiki
%% processStack.py (stack_images, mask_images, checkFocus).

%% 5.10 Rate limiting dla endpointów API
%% Endpoint /camera/stream i /motor/move nie mają rate limitingu,
%% co może prowadzić do przeciążenia Moonrakera przy szybkim
%% klikaniu w GUI.


%% ========================================================================
%% PODSUMOWANIE
%% ========================================================================
%%
%% Priorytet Rozwiązywania:
%%
%% 1. 🔴 Krytyczne (natychmiast):
%%    - handler.py: s3_stacked_path → remote_stacked_path (#1.1)
%%    - handler.py + scant_cli.py: -i → -p (#1.2)
%%    - processStack.py: cv2.destroyAllWindows() (#1.3)
%%    - processStack.py: exit() → return (#1.4)
%%    - Dockerfile.worker: opencv-contrib-python-headless (#1.5)
%%    - Dockerfile: brak opencv-python-headless (#1.6)
%%
%% 2. 🟡 Średnie (następny krok):
%%    - os.system() → subprocess.run() (#2.1)
%%    - cv2.findContours() API (#2.2)
%%    - write_exif_to_img: brak .wait() (#2.4)
%%    - Dodanie .dockerignore (#4.1)
%%    - Usunięcie duplikatu model.yml (#3.5)
%%    - Walidacja zakresów skanowania (#2.8)
%%
%% 3. 🟢 Usprawnienia (planowane):
%%    - endpoint /scan/cancel (#5.1)
%%    - Galeria w Web GUI (#5.4)
%%    - Structured logging (#5.8)
%%    - Testy dla processStack.py (#5.9)
%%    - Rate limiting (#5.10)
