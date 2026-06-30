import argparse
import time
import requests
import sys

API_URL = "http://localhost:8000"

def start_scan(args):
    payload = {
        "project_name": args.project,
        "x_min": args.x_min, "x_max": args.x_max, "x_step": args.x_step,
        "y_min": args.y_min, "y_max": args.y_max, "y_step": args.y_step,
        "z_min": args.z_min, "z_max": args.z_max, "z_step": args.z_step
    }
    
    try:
        response = requests.post(f"{API_URL}/scan/start", json=payload)
        response.raise_for_status()
        print(f"SUKCES: {response.json()['message']}")
        
        if args.wait:
            print("Oczekiwanie na zakończenie...")
            while True:
                time.sleep(2)
                status = requests.get(f"{API_URL}/scan/status").json()
                sys.stdout.write(f"\rPostęp: {status['progress_percent']}% ({status['images_taken']}/{status['images_to_take']})")
                sys.stdout.flush()
                if not status['is_scanning'] and status['progress_percent'] > 0:
                    print("\nSkanowanie zakończone!")
                    break
    except requests.exceptions.RequestException as e:
        print(f"Błąd sieciowy przy uruchamianiu skanowania: {e}")

def get_status(args):
    try:
        status = requests.get(f"{API_URL}/scan/status").json()
        print("--- Status skanera scAnt ---")
        print(f"Zajęty skanowaniem: {'Tak' if status['is_scanning'] else 'Nie'}")
        print(f"Postęp:             {status['progress_percent']}%")
        print(f"Zrobiono zdjęć:     {status['images_taken']} / {status['images_to_take']}")
    except requests.exceptions.RequestException as e:
        print(f"Błąd pobierania statusu (Sprawdź, czy api_server.py działa w Dockerze): {e}")

def home_motors(args):
    try:
        print("Wymuszanie bazowania...")
        response = requests.post(f"{API_URL}/motor/home")
        response.raise_for_status()
        print("Bazowanie osi zakończone.")
    except requests.exceptions.RequestException as e:
        print(f"Błąd bazowania osi: {e}")

def fetch_data(args):
    import os
    from concurrent.futures import ThreadPoolExecutor

    api = args.host if args.host.startswith("http") else f"http://{args.host}:8000"
    project = args.project
    
    print(f"Pobieranie listy plików z {api} dla projektu {project}...")
    try:
        resp = requests.get(f"{api}/scan/files/{project}")
        resp.raise_for_status()
        files = resp.json()["files"]
    except Exception as e:
        print(f"Błąd: {e}")
        return

    if not files:
        print("Projekt pusty lub nie istnieje.")
        return

    out_dir = os.path.join("scans", project)
    os.makedirs(out_dir, exist_ok=True)

    print(f"Znaleziono {len(files)} plików. Rozpoczynam pobieranie (max 8 wątków)...")
    
    def download_file(f):
        url = f"{api}/scans_data/{project}/{f}"
        local_path = os.path.join(out_dir, f)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if os.path.exists(local_path):
            return
        r = requests.get(url, stream=True)
        with open(local_path, "wb") as out:
            for chunk in r.iter_content(chunk_size=8192):
                out.write(chunk)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, _ in enumerate(pool.map(download_file, files)):
            sys.stdout.write(f"\rPobrano: {i+1}/{len(files)}")
            sys.stdout.flush()
    print("\nPobieranie zakończone.")

def process_data(args):
    import subprocess
    print(f"Uruchamianie processStack.py dla projektu {args.project} wewnątrz kontenera scant_worker...")
    
    # Wywołanie skryptu przez Docker Compose w uruchomionym workerze
    cmd = [
        "docker", "compose", "-f", "docker-compose.worker.yml", 
        "exec", "scant_worker", 
        "python", "processStack.py", "-p", f"scans/{args.project}"
    ]
    try:
        subprocess.run(cmd, check=True)
        print("Post-processing (EDOF) zakończony!")
    except subprocess.CalledProcessError as e:
        print(f"Błąd podczas post-processingu: {e}")

def runpod_process(args):
    import subprocess
    import time

    project = args.project
    remote_path = args.remote_path
    api_key = args.api_key
    endpoint_id = args.endpoint_id

    # 1. Rclone Sync W Górę
    print(f"Wysyłanie plików surowych projektu '{project}' do chmury ({remote_path})...")
    local_raw_path = f"scans/{project}"
    remote_raw_path = f"{remote_path}/{project}/RAW"
    try:
        subprocess.run(["rclone", "sync", local_raw_path, remote_raw_path], check=True)
        print("Wysyłanie zakończone pomyślnie.")
    except Exception as e:
        print(f"Błąd przesyłania rclone: {e}")
        return

    # 2. Wywołanie API RunPod Serverless
    print("Zlecanie zadania do chmury RunPod...")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "input": {
            "project": project,
            "remote_path": remote_path
        }
    }
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"

    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        job_id = resp.json().get("id")
        print(f"Zlecenie przyjęte! ID zadania: {job_id}")
    except Exception as e:
        print(f"Błąd komunikacji z RunPod: {e}")
        return

    # 3. Oczekiwanie na wynik (Polling)
    status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    print("Oczekiwanie na zakończenie obliczeń w chmurze...")
    while True:
        try:
            time.sleep(5)
            s_resp = requests.get(status_url, headers=headers)
            s_resp.raise_for_status()
            status_data = s_resp.json()
            status = status_data.get("status")
            
            if status == "COMPLETED":
                print("\nObliczenia w chmurze zakończone sukcesem!")
                break
            elif status in ["FAILED", "CANCELLED"]:
                print(f"\nBłąd w chmurze: Zadanie zakończone statusem {status}.")
                print(status_data)
                return
            else:
                sys.stdout.write(".")
                sys.stdout.flush()
        except Exception as e:
            print(f"\nBłąd odpytywania statusu: {e}")
            return

    # 4. Rclone Sync W Dół
    remote_stacked_path = f"{remote_path}/{project}/stacked"
    local_stacked_path = f"scans/stacked/{project}"
    print(f"Pobieranie przetworzonych plików z {remote_stacked_path} do {local_stacked_path}...")
    try:
        subprocess.run(["rclone", "sync", remote_stacked_path, local_stacked_path], check=True)
        print("Gotowe! Przetworzone pliki 3D pobrane z chmury.")
    except Exception as e:
        print(f"Błąd pobierania rclone: {e}")

def main():
    parser = argparse.ArgumentParser(description="Zarządzanie skanerem scAnt z linii komend (łączy się z lokalnym REST API).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Status
    status_parser = subparsers.add_parser("status", help="Wyświetla aktualny postęp zlecenia i status maszyny")
    status_parser.set_defaults(func=get_status)
    
    # Homing
    home_parser = subparsers.add_parser("home", help="Powrót silników na fizyczne zero (G28)")
    home_parser.set_defaults(func=home_motors)

    # Skanowanie
    scan_parser = subparsers.add_parser("scan", help="Uruchamia procedurę wieloosiowego skanowania")
    scan_parser.add_argument("--project", required=True, help="Zadana nazwa projektu (folderu docelowego)")
    scan_parser.add_argument("--x-min", type=int, default=0, help="Min X (ramię kamery)")
    scan_parser.add_argument("--x-max", type=int, default=45, help="Max X")
    scan_parser.add_argument("--x-step", type=int, default=5, help="Krok osi X")
    scan_parser.add_argument("--y-min", type=int, default=0, help="Min Y (stół obrotowy)")
    scan_parser.add_argument("--y-max", type=int, default=160, help="Max Y")
    scan_parser.add_argument("--y-step", type=int, default=8, help="Krok osi Y")
    scan_parser.add_argument("--z-min", type=int, default=-250, help="Min Z (wózek ostrości)")
    scan_parser.add_argument("--z-max", type=int, default=-80, help="Max Z")
    scan_parser.add_argument("--z-step", type=int, default=50, help="Krok osi Z")
    scan_parser.add_argument("--wait", action="store_true", help="Zablokuj konsolę i wyświetlaj pasek postępu")
    scan_parser.set_defaults(func=start_scan)

    # Fetch
    fetch_parser = subparsers.add_parser("fetch", help="Pobiera zdjęcia projektu po LAN z Raspberry Pi")
    fetch_parser.add_argument("--project", required=True, help="Nazwa projektu do pobrania")
    fetch_parser.add_argument("--host", default="localhost", help="Adres IP malinki (domyślnie localhost)")
    fetch_parser.set_defaults(func=fetch_data)

    # Process
    process_parser = subparsers.add_parser("process", help="Uruchamia processStack.py na PC / RunPodzie (EDOF)")
    process_parser.add_argument("--project", required=True, help="Nazwa projektu w folderze ./scans/")
    process_parser.set_defaults(func=process_data)

    # RunPod Serverless
    runpod_parser = subparsers.add_parser("runpod", help="Wysyła projekt do chmury RunPod przez Rclone")
    runpod_parser.add_argument("--project", required=True, help="Nazwa projektu")
    runpod_parser.add_argument("--remote-path", required=True, help="Ścieżka Rclone, np. s3:moj-bucket/scant")
    runpod_parser.add_argument("--api-key", required=True, help="Klucz API RunPod")
    runpod_parser.add_argument("--endpoint-id", required=True, help="ID Endpointu RunPod Serverless")
    runpod_parser.set_defaults(func=runpod_process)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
