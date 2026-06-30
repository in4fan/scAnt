# 🔍 Audyt Projektu scAnt — Znaleziska, Bugi i Propozycje Ulepszeń

Po dokładnym przejrzeniu **każdego pliku** w repozytorium, poniżej zestawiam wszystko, co znalazłem — od krytycznych bugów, przez łatwe do naprawienia drobnostki, po ambitne pomysły na nowe funkcjonalności.

---

## 🔴 Krytyczne Bugi (do natychmiastowej naprawy)

### 1. Zmienna-widmo `s3_stacked_path` w `handler.py`
**Plik:** [handler.py](file:///home/m4rcin/scAnt/handler.py#L61)
**Problem:** W linii 61 jest odwołanie do zmiennej `s3_stacked_path`, która **nigdy nie została zdefiniowana**. To spowoduje natychmiastowy `NameError` przy każdym pomyślnym zakończeniu zadania RunPod.
```python
# Linia 61 – BUG:
f"Przetwarzanie EDOF zakończone pomyślnie. Wyniki zgrane do {s3_stacked_path}."
# Powinno być:
f"Przetwarzanie EDOF zakończone pomyślnie. Wyniki zgrane do {remote_stacked_path}."
```

### 2. Nieprawidłowa flaga `-i` w `handler.py` i `scant_cli.py`
**Pliki:** [handler.py:46](file:///home/m4rcin/scAnt/handler.py#L46), [scant_cli.py:103](file:///home/m4rcin/scAnt/scant_cli.py#L103)
**Problem:** Skrypt `processStack.py` definiuje argument jako `-p` / `--path` (linia 676), a nie `-i`. Oba wywołania używają flagi `-i`, która nie istnieje w parserze — co spowoduje cichą ignorancję ścieżki lub crash.
```python
# handler.py:46 — BUG:
run_command(["python", "processStack.py", "-i", local_scan_dir])
# Powinno być:
run_command(["python", "processStack.py", "-p", local_scan_dir])
```

### 3. `cv2.destroyAllWindows()` w kontenerze headless
**Plik:** [processStack.py:819](file:///home/m4rcin/scAnt/processStack.py#L819)
**Problem:** Wywołanie `cv2.destroyAllWindows()` w środowisku bez X11 (headless Docker) może rzucać wyjątkami lub segfaultami z `opencv-python-headless`. Należy usunąć tę linię lub opakować w `try/except`.

### 4. `exit()` zamiast `return` w `processStack.py`
**Plik:** [processStack.py:834](file:///home/m4rcin/scAnt/processStack.py#L834) i [processStack.py:1016](file:///home/m4rcin/scAnt/processStack.py#L1016)
**Problem:** Użycie `exit()` w skrypcie woła `SystemExit`, co zabija cały proces Pythona, w tym wątek workera Dockera. Powinno być `sys.exit()` lub lepiej `return`.

---

## 🟡 Ulepszenia Istniejącego Kodu

### 5. `os.system()` → `subprocess.run()` w `processStack.py`
**Plik:** [processStack.py](file:///home/m4rcin/scAnt/processStack.py) — linie 173–228, 568–571
**Problem:** `os.system()` jest podatny na shell injection i nie pozwala na przechwycenie stderr/stdout. Ponadto `os.system("rm ...")` i `os.system("del ...")` to antywzorzec — Python ma `os.remove()` i `pathlib.Path.unlink()`.

### 6. Zduplikowany plik `model.yml` (35 MB × 2 = 70 MB!)
**Pliki:** [scripts/model.yml](file:///home/m4rcin/scAnt/scripts/model.yml) i [legacy_scripts/model.yml](file:///home/m4rcin/scAnt/legacy_scripts/model.yml)
**Problem:** Ten sam 35 MB plik modelu krawędziowego OpenCV istnieje w dwóch kopiach. Repozytoria z tego rozmiaru binariami powinny używać **Git LFS** lub trzymać model w artefakcie zewnętrznym (np. pobieranym przy pierwszym uruchomieniu). Warto przynajmniej usunąć duplikat.

### 7. `cv2.ximgproc.createStructuredEdgeDetection` — niedostępna w headless
**Plik:** [processStack.py:650](file:///home/m4rcin/scAnt/processStack.py#L650) i [processStack.py:961](file:///home/m4rcin/scAnt/processStack.py#L961)
**Problem:** Moduł `cv2.ximgproc` wymaga pakietu `opencv-contrib-python-headless`, a nie zwykłego `opencv-python-headless`. Bez niego maskowanie (`mask_images`) zawali się na `AttributeError`. Trzeba zmienić zależność w Dockerfile.worker.

### 8. Folder `external/` pełen plików `.exe` i `.dll` (Windows)
**Plik:** [external/](file:///home/m4rcin/scAnt/external)
**Problem:** ~90 plików binarnych Windows (`.exe`, `.dll`) o łącznym rozmiarze kilkudziesięciu MB niepotrzebnie puchnie repozytorium i obraz Dockera. Skoro nasz pipeline to Linux-only (Docker + RPi), te pliki można przenieść do osobnego brancha/release'u lub `.gitignore`.

### 9. Brak `opencv-python-headless` w głównym Dockerfile (RPi)
**Plik:** [Dockerfile](file:///home/m4rcin/scAnt/Dockerfile#L22-L30)
**Problem:** Główny Dockerfile (API na Raspberry Pi) instaluje `picamera2`, ale nie `opencv-python-headless`. Jeśli `api_server.py` zaimportuje `camera_controller.py`, który teraz wymaga `cv2` i `numpy`, kontener się wysypie.

### 10. `@app.on_event("startup")` — deprecation warning
**Plik:** [api_server.py:14](file:///home/m4rcin/scAnt/api_server.py#L14)
**Problem:** `on_event("startup")` jest oznaczony jako deprecated w FastAPI od wersji 0.95+. Zalecane jest użycie `lifespan` context managera.

### 11. Statyczne `mount()` przed dynamicznymi `route()`
**Plik:** [api_server.py:19-22](file:///home/m4rcin/scAnt/api_server.py#L19-L22)
**Problem:** `StaticFiles` są montowane zaraz po starcie, a trasy dynamiczne (np. `/camera/stream`) poniżej. FastAPI przeszukuje routery w kolejności dodania. `mount("/gui")` może nadpisać trasy zaczynające się od `/gui/...` i obsłużyć je zanim dotrą do tras dynamicznych. Bezpieczniej jest dodać `mount()` na końcu pliku.

---

## 🟢 Propozycje Nowych Funkcjonalności

### 12. **Galeria zdjęć w Web GUI**
Dodaj do panelu kontrolnego zakładkę „Galeria", pokazującą miniatury najnowszych zdjęć z aktywnego projektu (endpoint `/scan/files/{project}` już istnieje). Pozwoli to na szybki przegląd efektów skanowania bez logowania się do konsoli.

### 13. **Endpoint `/scan/cancel`** — Przerwanie skanowania
Brak możliwości anulowania trwającego skanu z poziomu API/GUI. Aktualnie jedynym sposobem jest restart kontenera. Dodanie flagi `cancel_requested` i sprawdzanie jej w pętli `runScan()` rozwiązałoby problem.

### 14. **Przycisk "Zrób jedno zdjęcie" w Web GUI**
Endpoint `/camera/capture` już istnieje, ale nie jest podpięty w GUI. Dodanie przycisku "📸 Snapshot" obok strumienia MJPEG, który pobierze i wyświetli pełnorozdzielcze zdjęcie testowe, ułatwi sprawdzanie ostrości.

### 15. **Automatyczne generowanie `config.yaml` z poziomu API**
Skrypt `processStack.py` (linia 710) szuka pliku `.yaml` w folderze projektu. Obecnie użytkownik musi go ręcznie tworzyć. API mogłoby automatycznie generować plik konfiguracyjny na podstawie parametrów skanowania i metadanych kamery RPi HQ.

### 16. **Wyświetlanie pozycji osi w GUI (Odczyt pozycji)**
Panel GUI pozwala jedynie na ruch relatywny, ale nie pokazuje, *gdzie* aktualnie znajduje się kamera. Moonraker udostępnia endpoint `GET /printer/objects/query?gcode_move`, z którego można odczytać `position: [x, y, z]` i wyświetlić je w panelu na żywo.

### 17. **Dodanie `.dockerignore`**
Brak pliku `.dockerignore` oznacza, że `COPY . /app` kopiuje do obrazu Dockera **WSZYSTKO**: folder `.git` (może ważyć setki MB), `external/` (90 plików Windows), `build.log`, `worker_build.log` itd. Prosty `.dockerignore` zmniejszy czas budowania i rozmiar obrazu o 50-80%.

### 18. **Endpoint `/motor/position` — Odczyt pozycji osi**
Do odczytu pozycji (punkty 12/16) potrzebujemy dedykowanego endpointu, który odpyta Moonrakera.

---

## 📊 Podsumowanie Priorytetów

| #  | Typ       | Trudność | Wpływ   | Opis skrócony                                     |
|----|-----------|----------|---------|----------------------------------------------------|
| 1  | 🔴 Bug    | Łatwy    | Krytyczny | `s3_stacked_path` → `remote_stacked_path`         |
| 2  | 🔴 Bug    | Łatwy    | Krytyczny | Flaga `-i` → `-p` w processStack                  |
| 3  | 🔴 Bug    | Łatwy    | Wysoki   | `destroyAllWindows()` w headless                   |
| 4  | 🔴 Bug    | Łatwy    | Wysoki   | `exit()` zabija worker — zamień na `return`         |
| 7  | 🟡 Fix    | Łatwy    | Wysoki   | Brak `opencv-contrib` — maskowanie nie zadziała     |
| 9  | 🟡 Fix    | Łatwy    | Wysoki   | Brak `opencv` w Dockerfile RPi                     |
| 17 | 🟢 Nowe   | Łatwy    | Wysoki   | `.dockerignore` — zmniejszenie obrazu              |
| 8  | 🟡 Czystka| Średni   | Średni   | Usunięcie 90 plików `.exe` z `external/`           |
| 6  | 🟡 Czystka| Łatwy    | Średni   | Usunięcie duplikatu `model.yml` (35 MB)            |
| 5  | 🟡 Refactor| Średni  | Średni   | `os.system()` → `subprocess.run()`                 |
| 13 | 🟢 Nowe   | Średni   | Wysoki   | Endpoint `/scan/cancel`                            |
| 16 | 🟢 Nowe   | Łatwy    | Średni   | Wyświetlanie pozycji osi w GUI                     |
| 12 | 🟢 Nowe   | Średni   | Średni   | Galeria zdjęć w Web GUI                            |
| 14 | 🟢 Nowe   | Łatwy    | Średni   | Przycisk Snapshot w GUI                            |
| 15 | 🟢 Nowe   | Średni   | Średni   | Auto-generowanie `config.yaml`                     |
