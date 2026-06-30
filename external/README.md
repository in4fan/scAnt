# Folder `external/` — Binaria zewnętrzne (Windows, legacy)

## Status

Folder zachowany w repozytorium, ale **niewymagany do działania** scAnt 2.0.
Pipeline jest w 100% oparty na Linux (Docker + RPi), a wszystkie narzędzia są
instalowane przez `apt` (hugin-tools, enblend, enfuse, exiftool).

## Zawartość

Folder zawiera ~90 plików binarnych dla systemu Windows, będących pozostałością
po architekturze **scAnt 1.x** (PyQt5 na Windows z kamerami FLIR/DSLR).

| Kategoria | Pliki | Przeznaczenie |
|-----------|-------|---------------|
| **Hugin** | `align_image_stack.exe`, `cpfind.exe`, `nona.exe`, `pto_gen.exe`, `hugin.exe` i ~30 innych | Panorama stitching, alignment i stacking obrazów |
| **Enfuse/Enblend** | `enfuse.exe`, `enblend.exe` | Blending i focus stacking |
| **ExifTool** | `exiftool.exe` | Odczyt/zapis metadanych EXIF |
| **focus-stack/** | `focus-stack.exe` + biblioteki (33 pliki) | Eksperymentalna metoda stackowania |
| **Biblioteki DLL** | `opencv_world*.dll`, `wxbase*.dll`, `tiff.dll`, `jpeg62.dll`, `zlib1.dll` i ~30 innych | Zależności uruchomieniowe dla powyższych narzędzi |
| **Dane** | `cameraSensors.txt`, `cameraMakes.txt` | Baza sensorów FLIR/DSLR dla Meshroom |

## Dlaczego nie usuwamy?

- Repozytorium jest forkiem `evo-biomech/scAnt`, zachowujemy kompatybilność
  z historią
- Użytkownicy migrujący ze starej architektury mogą potrzebować tych plików
  do pracy lokalnej na Windows
- Wszystkie pliki są wykluczone z obrazów Dockera przez `.dockerignore`

## Alternatywy w Linux

| Narzędzie Windows | Odpowiednik Linux |
|-------------------|-------------------|
| `align_image_stack.exe` | `align_image_stack` (pkg: `hugin-tools`) |
| `enfuse.exe` | `enfuse` (pkg: `enfuse`) |
| `exiftool.exe` | `exiftool` (pkg: `libimage-exiftool-perl`) |
