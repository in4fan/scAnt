# S3 Output dla Raspberry Pi — Instrukcja Obsługi

*Wersja: 1.0 | Data: 2026-06-30*

---

## 📌 Podsumowanie

Ten dokument opisuje **4 sposoby konfigurowania wyjścia S3** dla obrazów ze skanera scAnt działającego na **Raspberry Pi**. Wszystkie metody wykorzystują **rclone**, który jest już preinstalowany w kontenerach Docker (`scant_api` i `scant_worker`).

| Metoda | Złożoność | Wymagane Zmiany | Czas Implem. | Rekomendacja |
|--------|-----------|-----------------|--------------|--------------|
| **1. Ręczny upload** | ⭐ | ❌ Żadne | 0 min | ✅ Działa od razu |
| **2. Automatyczny upload (API)** | ⭐⭐ | ✅ Małe | 15 min | 🏆 Najlepsza dla produkcji |
| **3. Upload w czasie rzeczywistym** | ⭐⭐⭐ | ✅ Średnie | 30 min | ⚠️ Spowalnia skanowanie |
| **4. s3fs mount** | ⭐⭐⭐⭐ | ✅ Duże | 60 min | ❌ Złożona |

---

## 🔹 Wymagania Wstępne

### 1. Konto AWS S3

- [ ] **Konto AWS** (https://aws.amazon.com/)
- [ ] **Bucket S3** (np. `my-scant-bucket`)
- [ ] **Access Key ID** i **Secret Access Key** (z IAM User z uprawnieniami `AmazonS3FullAccess`)

> 💡 **Alternatywy**: Możesz użyć innych dostawców (Backblaze B2, MinIO, Wasabi, itp.) — rclone obsługuje [40+ backendów](https://rclone.org/overview/).

### 2. Docker Compose

- [ ] Uruchomione kontenery `scant_api` i `scant_worker`
- [ ] rclone zainstalowane (już jest w `Dockerfile:13` i `Dockerfile.worker:17`)

```bash
# Sprawdź czy rclone jest dostępne
docker exec scant_api rclone version
# Oczekiwany output: rclone v1.65.2+...
```

---

## ✅ Metoda 1: Ręczny Upload (Działa OD RAZU)

**Najszybsza metoda — zero zmian w kodzie.**

### Krok 1: Skonfiguruj rclone

#### Opcja A: Konfiguracja w kontenerze API
```bash
docker exec -it scant_api rclone config
```

#### Opcja B: Konfiguracja na hoście (Raspberry Pi)
```bash
# Zainstaluj rclone na hoście (jeśli nie masz)
curl https://rclone.org/install.sh | sudo bash

# Uruchom konfigurację
rclone config
```

**Przykład konfiguracji dla AWS S3:**
```
n) New remote
name> scant-s3
env_auth> false
access_key_id> YOUR_AWS_ACCESS_KEY_ID
secret_access_key> YOUR_AWS_SECRET_ACCESS_KEY
region> eu-central-1
endpoint> (leave blank)
location_constraint> (leave blank)
acl> private
storage_class> STANDARD
```

### Krok 2: Sprawdź połączenie
```bash
# Lista bucketów
docker exec scant_api rclone lsd scant-s3:

# Lista plików w bucketcie
docker exec scant_api rclone ls scant-s3:my-scant-bucket/
```

### Krok 3: Upload po skanowaniu

Po zakończeniu skanowania:

```bash
# Skopiuj projekt do S3 (zachowuje lokalne pliki)
docker exec scant_api rclone copy /app/scans/my_project scant-s3:my-scant-bucket/scans/my_project

# Lub z hosta (jeśli rclone skonfigurowany na hoście):
rclone copy ./scans/my_project scant-s3:my-scant-bucket/scans/my_project
```

### Krok 4: Weryfikacja
```bash
# Sprawdź co zostało zgrane
docker exec scant_api rclone ls scant-s3:my-scant-bucket/scans/my_project/

# Ilość plików
docker exec scant_api rclone size scant-s3:my-scant-bucket/scans/my_project/
```

### 📌 Skrypt pomocniczy (opcjonalnie)

Stwórz plik `upload_to_s3.sh`:

```bash
#!/bin/bash
# upload_to_s3.sh - Upload projektu do S3

PROJECT_NAME=$1
S3_REMOTE=$2
S3_PATH=$3

if [ -z "$PROJECT_NAME" ] || [ -z "$S3_REMOTE" ] || [ -z "$S3_PATH" ]; then
    echo "Użycie: $0 <project_name> <rclone_remote> <s3_path>"
    echo "Przykład: $0 my_project scant-s3 my-scant-bucket/scans"
    exit 1
fi

echo "Upload projektu '$PROJECT_NAME' do $S3_REMOTE:$S3_PATH..."
docker exec scant_api rclone copy /app/scans/$PROJECT_NAME $S3_REMOTE:$S3_PATH/$PROJECT_NAME

if [ $? -eq 0 ]; then
    echo "✅ Upload zakończony pomyślnie!"
else
    echo "❌ Błąd podczas uploadu"
    exit 1
fi
```

Nadaj uprawnienia:
```bash
chmod +x upload_to_s3.sh
```

Użycie:
```bash
./upload_to_s3.sh my_project scant-s3 my-scant-bucket/scans
```

---

## 🏆 Metoda 2: Automatyczny Upload z API (Rekomendowana)

**Automatyczne wgrywanie do S3 po zakończeniu każdego skanowania.**

### Krok 1: Zmodyfikuj `api_server.py`

Dodaj pole do `ScanConfig`:

```python
# api_server.py - linia ~50 (po klasie ScanConfig)
from typing import Optional

class ScanConfig(BaseModel):
    project_name: str
    x_min: int = 0
    x_max: int = 45
    x_step: int = 5
    y_min: int = 0
    y_max: int = 160
    y_step: int = 8
    z_min: int = -250
    z_max: int = -80
    z_step: int = 50
    
    # === NOWE POLA DLA S3 ===
    upload_to_s3: bool = False
    s3_output_path: Optional[str] = None  # np. "scant-s3:my-scant-bucket/scans"
    s3_remove_local: bool = False  # Czy usunąć lokalne pliki po uploadzie
```

### Krok 2: Zmodyfikuj `run_scan_task()`

```python
# api_server.py - w funkcji run_scan_task()
import subprocess

def run_scan_task(config: ScanConfig):
    scAnt = _get_scanner()
    scAnt.cancel_requested = False
    try:
        output_dir = Path(SCANS_DIR) / config.project_name
        os.makedirs(output_dir, exist_ok=True)
        scAnt.outputFolder = str(output_dir) + "/"
        
        scAnt.setScanRange(0, config.x_min, config.x_max, config.x_step)
        scAnt.setScanRange(1, config.y_min, config.y_max, config.y_step)
        scAnt.setScanRange(2, config.z_min, config.z_max, config.z_step)
        
        logging.info("Rozpoczęcie procedury skanowania zlecenia z API...")
        scAnt.home()
        scAnt.runScan()
        scAnt.deEnergise()
        
        # === NOWY KOD: Upload do S3 ===
        if config.upload_to_s3 and config.s3_output_path:
            s3_dest = f"{config.s3_output_path}/{config.project_name}"
            logging.info(f"Wgrywanie do S3: {s3_dest}")
            
            try:
                result = subprocess.run(
                    ["rclone", "copy", str(output_dir), s3_dest],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minut timeout
                )
                logging.info(f"✅ Upload do S3 zakończony: {result.stdout}")
                
                # Opcjonalnie: usuń lokalne pliki
                if config.s3_remove_local:
                    logging.info(f"Usuwanie lokalnych plików: {output_dir}")
                    shutil.rmtree(output_dir)
                    
            except subprocess.TimeoutExpired:
                logging.error("⚠️ Upload do S3 przerwany (timeout)")
            except subprocess.CalledProcessError as e:
                logging.error(f"❌ Błąd uploadu do S3: {e.stderr}")
        
    except HardwareCommunicationError as e:
        logging.error(f"Skanowanie przerwane błędem komunikacji sprzętowej: {e}")
    except Exception as e:
        logging.error(f"Skanowanie przerwane awarią: {e}")
    finally:
        _set_scanning(False)
        logging.info(f"Proces skanowania {config.project_name} zakończony.")
```

### Krok 3: Zbuduj i uruchom

```bash
# Zbuduj obrazy na nowo
docker compose build

# Uruchom
docker compose up -d
```

### Krok 4: Użycie

```bash
# Uruchom skanowanie z automatycznym uploadem do S3
curl -X POST http://localhost:8000/scan/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "model_001",
    "x_min": 0, "x_max": 45, "x_step": 5,
    "y_min": 0, "y_max": 160, "y_step": 8,
    "z_min": -250, "z_max": -80, "z_step": 50,
    "upload_to_s3": true,
    "s3_output_path": "scant-s3:my-scant-bucket/scans"
  }'
```

**Parametry:**
- `upload_to_s3: true` — włącza upload
- `s3_output_path: "scant-s3:my-scant-bucket/scans"` — docelowa ścieżka w formacie rclone
- `s3_remove_local: false` (opcjonalnie) — usuwa lokalne pliki po uploadzie

---

## ⚡ Metoda 3: Upload w Czasie Rzeczywistym

**Każde zdjęcie jest od razu wgrywane do S3.**

⚠️ **Uwaga:** Spowalnia skanowanie (dodatkowe ~1-5s na zdjęcie).

### Krok 1: Zmodyfikuj `camera_controller.py`

```python
# scripts/camera_controller.py
import subprocess
import os

def capture_image(self, img_name: str):
    """Zrób zdjęcie i opcjonalnie wgraj do S3."""
    # Zrób zdjęcie
    self.picam2.capture_file(img_name)
    
    # Upload do S3 w tle (nie blokuj skanowania)
    s3_enabled = os.environ.get("S3_UPLOAD_ENABLED", "false").lower() == "true"
    s3_path = os.environ.get("S3_OUTPUT_PATH", "")
    
    if s3_enabled and s3_path:
        # Uruchom w tle (async)
        import threading
        def upload_to_s3():
            try:
                subprocess.run(
                    ["rclone", "copy", img_name, f"{s3_path}/{os.path.basename(img_name)}"],
                    check=True,
                    capture_output=True,
                    timeout=30
                )
            except Exception as e:
                print(f"Błąd uploadu do S3: {e}")
        
        threading.Thread(target=upload_to_s3, daemon=True).start()
```

### Krok 2: Konfiguracja środowiskowa

Dodaj do `docker-compose.yml`:

```yaml
services:
  scant_api:
    # ...
    environment:
      - S3_UPLOAD_ENABLED=true
      - S3_OUTPUT_PATH=scant-s3:my-scant-bucket/scans
```

### Krok 3: Zbuduj i uruchom
```bash
docker compose down && docker compose up -d
```

---

## 📁 Metoda 4: Mount S3 jako Filesystem (s3fs)

**S3 mountowany jako lokalny katalog.**

⚠️ **Wady:**
- Wymaga dodatkowego drivera Docker
- Może mieć problemy z wydajnością
- Skomplikowana konfiguracja

### Krok 1: Zainstaluj plugin s3fs

```bash
# Na Raspberry Pi (hoście)
docker plugin install viebel/s3fs
```

### Krok 2: Utwórz volume S3

```yaml
# docker-compose.yml
services:
  scant_api:
    # ...
    volumes:
      - s3-scans:/app/scans
    # ...

volumes:
  s3-scans:
    driver: viebel/s3fs
    driver_opts:
      bucket: my-scant-bucket
      path: /scans
      accessKeyId: YOUR_ACCESS_KEY
      secretAccessKey: YOUR_SECRET_KEY
      region: eu-central-1
```

### Krok 3: Uruchom
```bash
docker compose up -d
```

**Uwaga:** Ta metoda może nie działać stabilnie na Raspberry Pi z powodu ograniczeń pamięci.

---

## 🔧 Konfiguracja rclone — Przewodnik Krok po Kroku

### 1. Utwórz nowy remote

```bash
docker exec -it scant_api rclone config
```

**Dla AWS S3:**
```
n) New remote
name> scant-s3
Type of storage> 5 / Amazon S3
provider> (leave blank for AWS)
env_auth> false
access_key_id> AKIA... (Twój Access Key)
secret_access_key> ... (Twój Secret Key)
region> eu-central-1 (lub inny)
endpoint> (leave blank)
location_constraint> (leave blank)
acl> private
storage_class> STANDARD
```

**Dla Backblaze B2:**
```
Type of storage> 13 / Backblaze B2
key_id> (Key ID)
application_key> (Application Key)
```

**Dla MinIO:**
```
Type of storage> 4 / Minio
env_auth> false
access_key_id> (MinIO Access Key)
secret_access_key> (MinIO Secret Key)
endpoint> http://minio-server:9000
```

### 2. Sprawdź konfigurację

```bash
# Lista zkonfigurowanych remote'ów
docker exec scant_api rclone listremotes

# Sprawdź konfigurację konkretnego remote
docker exec scant_api rclone config show scant-s3:
```

### 3. Test połączenia

```bash
# Utwórz testowy plik
echo "test" > /tmp/test_s3.txt

# Wgraj do S3
docker exec scant_api rclone copy /tmp/test_s3.txt scant-s3:my-scant-bucket/test/

# Sprawdź czy plik istnieje
docker exec scant_api rclone ls scant-s3:my-scant-bucket/test/

# Usuń testowy plik
docker exec scant_api rclone delete scant-s3:my-scant-bucket/test/test_s3.txt
```

---

## 📊 Porównanie Metod

| Kryterium | Metoda 1 (Ręczna) | Metoda 2 (API) | Metoda 3 (Realtime) | Metoda 4 (s3fs) |
|-----------|------------------|----------------|-------------------|-----------------|
| **Złożoność** | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Zmiany w kodzie** | ❌ | ✅ Małe | ✅ Średnie | ✅ Duże |
| **Wydajność** | ✅ Pełna | ✅ Pełna | ⚠️ Spowolnienie | ⚠️ Zmienna |
| **Automatyzacja** | ❌ Ręczna | ✅ Pełna | ✅ Pełna | ✅ Pełna |
| **Backup lokalny** | ✅ | ✅ (opcjonalnie) | ❌ | ❌ |
| **Zalecana** | Testy | **🏆 Produkcja** | Specjalne przypadki | ❌ |

---

## 🚀 Rekomendacje

### 🎯 Dla większości użytkowników: **Metoda 2 (API)**

**Zalety:**
- Automatyczne wgrywanie po skanowaniu
- Zero wpływu na wydajność skanowania
- Prosta konfiguracja
- Możliwość wyłączenia (`upload_to_s3: false`)

### 🧪 Dla testów: **Metoda 1 (Ręczna)**

**Zalety:**
- Zero zmian w kodzie
- Pełna kontrola
- Możesz wybierać co uploadować

### ⚡ Dla szybkiego internetu: **Metoda 3 (Realtime)**

**Kiedy użyć:**
- Szybkie łącze internetowe (>50 Mbps upload)
- Mała liczba zdjęć (< 100 na skan)
- Potrzebujesz backupu w czasie rzeczywistym

### 🚫 Unikaj: **Metoda 4 (s3fs)**

**Dlaczego:**
- Niestabilna na Raspberry Pi
- Złożona konfiguracja
- Problemy z wydajnością

---

## ❓ Rozwiązywanie Problemów

### 🔴 "rclone: command not found"

**Rozwiązanie:** rclone nie jest zainstalowane

```bash
# Zainstaluj rclone w kontenerze
docker exec -it scant_api apt-get update && apt-get install -y rclone

# Lub zrebuilduj obrazy
docker compose build --no-cache
```

---

### 🔴 "Failed to create file system: failed to get credentials"

**Rozwiązanie:** Błędne poświadczenia AWS

```bash
# Sprawdź konfigurację
docker exec scant_api rclone config show scant-s3:

# Popraw poświadczenia
docker exec -it scant_api rclone config edit
```

---

### 🔴 "Access Denied" przy uploadzie

**Rozwiązanie:** Brak uprawnień do bucketu

1. Sprawdź **IAM Policy** dla użytkownika:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:*"],
         "Resource": ["arn:aws:s3:::my-scant-bucket/*"]
       }
     ]
   }
   ```

2. Sprawdź **Bucket Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {"AWS": "arn:aws:iam::YOUR_ACCOUNT:user/YOUR_USER"},
         "Action": "s3:*",
         "Resource": "arn:aws:s3:::my-scant-bucket/*"
       }
     ]
   }
   ```

---

### 🔴 "Timeout" przy dużych plikach

**Rozwiązanie:** Zwiększ timeout lub użyj `--transfers`

```bash
# Zwiększ timeout (domyślnie 5 minut)
docker exec scant_api rclone --timeout 30m copy /app/scans/project scant-s3:bucket/

# Użyj wielu transferów (szybszy upload)
docker exec scant_api rclone --transfers 8 copy /app/scans/project scant-s3:bucket/
```

---

### 🟡 Upload trwa zbyt długo

**Rozwiązanie:** 

1. **Użyj `--fast-list`** (szybsze listowanie plików):
   ```bash
   docker exec scant_api rclone --fast-list copy /app/scans/project scant-s3:bucket/
   ```

2. **Zwiększ `--transfers`** (więcej równoległych uploadów):
   ```bash
   docker exec scant_api rclone --transfers 16 copy /app/scans/project scant-s3:bucket/
   ```

3. **Użyj `--progress`** (monitoruj postęp):
   ```bash
   docker exec scant_api rclone --progress copy /app/scans/project scant-s3:bucket/
   ```

---

## 📚 Przydatne Komendy rclone

### Podstawowe operacje

```bash
# Kopiowanie (zachowuje źródło)
docker exec scant_api rclone copy /source scant-s3:bucket/dest

# Synchronizacja (usunięcie plików które nie istnieją w źródle)
docker exec scant_api rclone sync /source scant-s3:bucket/dest

# Sprawdź rozmiar folderu
docker exec scant_api rclone size scant-s3:bucket/folder/

# Sprawdź ilość plików
docker exec scant_api rclone ls scant-s3:bucket/folder/ | wc -l

# Usuń plik
docker exec scant_api rclone delete scant-s3:bucket/file.jpg

# Usuń folder (wraz z plikami)
docker exec scant_api rclone purge scant-s3:bucket/folder/
```

### Zaawansowane

```bash
# Kopiowanie z pomijaniem istniejących plików
docker exec scant_api rclone copy --ignore-existing /source scant-s3:bucket/

# Kopiowanie tylko nowszych plików
docker exec scant_api rclone copy --update /source scant-s3:bucket/

# Kopiowanie z kompresją
docker exec scant_api rclone copy --compress /source scant-s3:bucket/

# Monitoring transferu
docker exec scant_api rclone --progress --stats 1s copy /source scant-s3:bucket/
```

---

## 🔗 Linki

- [rclone Documentation](https://rclone.org/docs/)
- [rclone S3 Setup](https://rclone.org/s3/)
- [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/)
- [Backblaze B2](https://www.backblaze.com/b2/cloud-storage.html)
- [MinIO](https://min.io/) (Self-hosted S3)

---

## 📝 Historia Zmian

| Wersja | Data | Autor | Zmiany |
|--------|------|-------|--------|
| 1.0 | 2026-06-30 | Mistral Vibe | Utworzenie dokumentu |
