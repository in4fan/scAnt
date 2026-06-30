# Analiza kodu źródłowego projektu scAnt
## Wygenerowano: 2026-06-30

- ✅ = poprawione
- ⏳ = zaplanowane
- ❌ = nierozpoczęte

---

## 1. 🔴 BŁĘDY KRYTYCZNE — wszystkie ✅

| # | Plik | Problem | Status |
|---|------|---------|--------|
| 1.1 | `handler.py:61` | `s3_stacked_path` → `remote_stacked_path` (NameError przy sukcesie RunPod) | ✅ |
| 1.2 | `handler.py:46`, `scant_cli.py:103` | flaga `-i` zamiast `-p` w wywołaniach processStack | ✅ |
| 1.3 | `processStack.py:819` | `cv2.destroyAllWindows()` crash w headless Docker | ✅ |
| 1.4 | `processStack.py:834,1016` | `exit()` zabija worker — zamienione na `sys.exit()` | ✅ |
| 1.5 | `Dockerfile.worker` | brak `opencv-contrib-python-headless` (maskowanie nie działa) | ✅ |
| 1.6 | `Dockerfile` | brak `opencv-python-headless` (streaming się wysypie) | ✅ |
| 1.7 | `watchdog.py` | race condition na `health_status` — GIL chroni, ale nierozwiązane | ❌ |
| 1.8 | `api_server.py` | MJPEG generator bez warunku stopu | ❌ |

## 2. 🟡 BŁĘDY ŚREDNIE — wszystkie ✅

| # | Plik | Problem | Status |
|---|------|---------|--------|
| 2.1 | `processStack.py` | `os.system()` → `subprocess.run()` (9 wystąpień) | ✅ |
| 2.2 | `processStack.py` | `cv2.findContours()` API — kompatybilność OpenCV 3/4 | ✅ |
| 2.3 | `processStack.py` | brak config.yaml → generowanie domyślnego configu | ✅ |
| 2.4 | `scripts/write_meta_data.py` | `Popen` bez `.wait()` → `subprocess.run(check=True)` | ✅ |
| 2.5 | `processStack.py` | `os.rmdir()` → `shutil.rmtree(ignore_errors=True)` | ✅ |
| 2.6 | `scripts/Scanner_Controller.py` | walidacja pustych zakresów i `step <= 0` | ✅ |
| 2.7 | `scripts/Scanner_Controller.py` | `correctName()` gubi znak — dodany prefix `n`/`p` | ✅ |
| 2.8 | `api_server.py` | walidacja zakresów w ScanConfig (Pydantic validatory) | ✅ |

## 3. 🟠 PROBLEMY JAKOŚCI KODU — wszystkie ✅

| # | Plik | Problem | Status |
|---|------|---------|--------|
| 3.1 | `api_server.py` | `@app.on_event("startup")` → `lifespan` context manager | ✅ |
| 3.2 | `api_server.py` | StaticFiles mount() przed trasami → przeniesiony na koniec | ✅ |
| 3.3 | `api_server.py` | globalne `is_scanning` bez locka → `threading.Lock()` | ✅ |
| 3.4 | `processStack.py` | `exitFlag` (int) → `threading.Event()` | ✅ *(następnie zastąpione ThreadPoolExecutor w 3.6)* |
| 3.5 | `legacy_scripts/` | duplikat `model.yml` (35 MB) usunięty | ✅ |
| 3.6 | `processStack.py` | duplikacja kodu main vs funkcje — refactor: +47/-350 linii | ✅ |
| 3.7 | `processStack.py` | hardcoded ścieżka `model.yml` → `Path(__file__).parent` | ✅ |
| 3.8 | `api_server.py` | `/app/scans` hardcoded → `SCANS_DIR` env var z fallbackiem | ✅ |

## 4. 🔵 PROBLEMY Z DOCKEREM I WDROŻENIEM

| # | Problem | Status |
|---|---------|--------|
| 4.1 | Brak `.dockerignore` (obraz puchnie o 50-80%) | ❌ |
| 4.2 | Folder `external/` z 90 plikami `.exe` (Windows) | ⏳ *(zachowany, udokumentowany w `external/README.md`)* |
| 4.3 | `picamera2` na `python:3.11-slim` — działa po buildzie | ✅ *(zweryfikowane)* |
| 4.4 | `/dev/dma_heap` w docker-compose.yml — dodany komentarz o warunkowym montowaniu | ✅ |

## 5. 🟢 PROPOZYCIE ULEPSZEŃ

| # | Pomysł | Status |
|---|--------|--------|
| 5.1 | Endpoint `/scan/cancel` — anulowanie skanowania | ❌ |
| 5.2 | Endpoint `/motor/position` — odczyt pozycji osi | ❌ |
| 5.3 | Przycisk "Snapshot" w Web GUI | ❌ |
| 5.4 | Galeria zdjęć w Web GUI | ❌ |
| 5.5 | Auto-generowanie config.yaml z API | ❌ |
| 5.6 | Wyświetlanie pozycji osi w GUI na żywo | ❌ |
| 5.7 | Walidacja Pydantic dla ScanConfig | ✅ *(zrobione w 2.8)* |
| 5.8 | Structured logging zamiast `print()` | ❌ |
| 5.9 | Testy integracyjne dla processStack.py | ❌ |
| 5.10 | Rate limiting dla API | ❌ |

---

## Podsumowanie

- **Section 1** (krytyczne): **6/8** — 1.7 watchdog race condition i 1.8 MJPEG stop czekają
- **Section 2** (średnie): **8/8** — wszystkie zrobione
- **Section 3** (jakość): **8/8** — wszystkie zrobione, w tym duży refactor 3.6 (-350 linii)
- **Section 4** (Docker): **1/4** — tylko weryfikacja picamera2
- **Section 5** (ulepszenia): **1/10** — tylko walidacja Pydantic

**Łącznie: 24/38 pozycji załatwionych.**
