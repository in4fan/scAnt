import runpod
import subprocess
import os
import shutil

def run_command(cmd):
    """Pomocnicza funkcja do uruchamiania poleceń shellowych i logowania wyników."""
    print(f"Uruchamianie komendy: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Błąd komendy: {result.stderr}")
        raise Exception(f"Komenda {' '.join(cmd)} zakończyła się błędem: {result.stderr}")
    print(result.stdout)
    return result.stdout

def handler(job):
    """
    Główny handler dla RunPod Serverless.
    Oczekiwane parametry w `job['input']`:
    - project: nazwa projektu (np. 'my_scan')
    - remote_path: bazowa ścieżka rclone (np. 's3:moj-bucket/scant' albo 'gdrive:mojedane/scant')
    """
    job_input = job.get("input", {})
    project = job_input.get("project")
    remote_path = job_input.get("remote_path")
    
    if not project or not remote_path:
        return {"error": "Brak wymaganego parametru 'project' lub 'remote_path' w wejściu (input)."}

    print(f"Rozpoczynanie przetwarzania dla projektu {project} ze źródła {remote_path}")

    local_scan_dir = f"/app/scans/{project}"
    local_stacked_dir = f"/app/scans/stacked"

    if os.path.exists(local_scan_dir):
        shutil.rmtree(local_scan_dir)
    
    try:
        # 1. Pobieranie danych z dowolnej chmury rclone (Google Drive, S3, FTP, itp.)
        remote_raw_path = f"{remote_path}/{project}/RAW"
        print(f"Pobieranie plików z {remote_raw_path} do {local_scan_dir}...")
        run_command(["rclone", "copy", remote_raw_path, local_scan_dir])

        # 2. Uruchomienie processStack.py (EDOF i Maskowanie)
        print(f"Uruchamianie processStack.py dla folderu {local_scan_dir}...")
        run_command(["python", "processStack.py", "-i", local_scan_dir])

        # 3. Wgrywanie przetworzonych danych z powrotem na wskazany remote
        remote_stacked_path = f"{remote_path}/{project}/stacked"
        print(f"Wgrywanie przetworzonych plików z {local_stacked_dir}/{project} do {remote_stacked_path}...")
        
        output_folder = f"{local_stacked_dir}/{project}"
        if os.path.exists(output_folder):
            run_command(["rclone", "copy", output_folder, remote_stacked_path])
        else:
            print("Ostrzeżenie: Folder ze sklejonymi zdjęciami (stacked) nie został wygenerowany lub ma inną nazwę!")

        return {
            "status": "success", 
            "project": project, 
            "message": f"Przetwarzanie EDOF zakończone pomyślnie. Wyniki zgrane do {s3_stacked_path}."
        }

    except Exception as e:
        print(f"Wystąpił błąd podczas przetwarzania: {e}")
        return {"error": str(e)}

    finally:
        # 4. Sprzątanie
        print("Czyszczenie po zadaniu...")
        if os.path.exists(local_scan_dir):
            shutil.rmtree(local_scan_dir)
        if os.path.exists(f"{local_stacked_dir}/{project}"):
            shutil.rmtree(f"{local_stacked_dir}/{project}")

# Uruchomienie Serverless
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
