# Przewodnik: Uruchamianie EDOF na RunPod (Chmura GPU)

Gdy Twój projekt zawiera setki lub tysiące zdjęć, algorytmy Focus Stackingu (`processStack.py`) mogą zająć na zwykłym procesorze wiele godzin. Dzięki przeniesieniu tego na RunPod, proces ten wykonuje się na potężnych kartach graficznych (np. RTX 4090, RTX A6000), co drastycznie skraca czas i kosztuje zaledwie kilka centów.

## 1. Wybór obrazu (Template) w RunPod
Otwórz panel RunPod i rozpocznij tworzenie nowego Poda (Deploy Pod).
Zalecanym najszybszym i najtańszym szablonem do manualnych testów jest po prostu oficjalne **Ubuntu 24.04**. Domyślnie cały nasz stos używa procesora (CPU) dla narzędzi Hugin/Enfuse.

## 2. Inicjalizacja środowiska po zalogowaniu do RunPod
Po uruchomieniu Poda połącz się przez **Web Terminal** lub **Jupyter Notebook**, pobierz projekt scAnt, a następnie zainstaluj najnowszą paczkę narzędzi oraz pakietów:

```bash
# Instalacja narzędzi EDOF (Hugin-tools, Enfuse - bez środowiska graficznego X11!)
apt-get update && apt-get install -y hugin-tools enblend enfuse libimage-exiftool-perl

# Utworzenie bezpiecznego środowiska wirtualnego (PEP 668)
python3 -m venv /opt/venv
source /opt/venv/bin/activate

# Instalacja bilbiotek Pythona
pip install opencv-python-headless scikit-image imutils Pillow numpy PyYAML
```

*(Uwaga: Powyższe komendy są wbudowane w `Dockerfile.worker` oraz `Dockerfile.serverless` – możesz zbudować i wypchnąć własny obraz na Docker Hub, by mieć to od razu "z pudełka" bez wpisywania tych poleceń!)*

### Jak zbudować ten obraz lokalnie (na swoim PC)?
Jeśli chcesz zbudować i uruchomić Workera lokalnie (np. przed wysłaniem na chmurę), wykonaj w głównym folderze:
```bash
docker compose -f docker-compose.worker.yml up --build -d
```
**Ważne o Akceleracji GPU NVIDIA:**
Domyślnie Worker jest skonfigurowany, by działać w 100% niezawodnie na każdym urządzeniu (tylko na CPU, brak środowisk graficznych X11) - nie wywali błędu jeśli nie masz dedykowanej karty graficznej. 
Jeśli jednak na swoim komputerze *posiadasz* kartę NVIDIA i chcesz przepuścić ją do środka kontenera (bo np. planujesz ręczne modyfikacje skryptów CUDA), wejdź do pliku `docker-compose.worker.yml` i odkomentuj w nim zablokowane 6 linijek z sekcji `deploy: resources...`. Docker automatycznie przechwyci wtedy Twoją kartę.

## 3. Przeniesienie plików na RunPod (Fetch)
Pobierz skrypt `scant_cli.py` na serwer RunPod.
Następnie użyj zbudowanej specjalnie w tym celu komendy **fetch**, aby zassać dane prosto z Twojego Raspberry Pi (wymaga, by RPi było wystawione w sieci za pomocą tunelu np. Ngrok, Tailscale lub publicznego IP):

```bash
python scant_cli.py fetch --project <NAZWA_PROJEKTU> --host <IP_RASPBERRY_PI>
```

Dane zostaną pobrane i wypakowane do wewnętrznego folderu `scans/<NAZWA_PROJEKTU>`.

## 4. Generowanie EDOF i Maskowanie
Gdy pliki znajdują się już na dysku sieciowym w RunPod, odpal post-processing w pełni korzystający z zasobów serwera:

```bash
python scant_cli.py process --project <NAZWA_PROJEKTU>
```

Algorytm EDOF połączy klatki w ostre obrazy i automatycznie je zamaskuje (wytnie tło).

## 5. Pobranie wyników na swój komputer i Meshing w 3DF Zephyr
Po zakończeniu skryptu, w folderze `scans/<NAZWA_PROJEKTU>` pojawią się wyostrzone pliki. Pobierz je na swój lokalny komputer (np. przez JupyterLab w RunPod lub narzędziem `rsync`).

Ostatnim etapem jest wciągnięcie tych plików na Windowsie do programu **3DF Zephyr** – od tego momentu fotogrametria wygeneruje w pełni teksturowany i gotowy model 3D (Mesh).
