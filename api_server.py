from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from contextlib import asynccontextmanager
import logging
import threading
from scripts.Scanner_Controller import ScannerController
from scripts.camera_controller import CameraController
import os
from pathlib import Path
import watchdog

# Zmienne środowiskowe dla ścieżek (z fallbackiem do Dockerowych domyślnych)
SCANS_DIR = os.environ.get("SCANS_DIR", "/app/scans")
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")

@asynccontextmanager
async def lifespan(app):
    watchdog.start_watchdogs()
    yield
    # ew. cleanup przy shutdown

app = FastAPI(title="scAnt API", description="API do sterowania skanerem 3D scAnt", lifespan=lifespan)

# Konfiguracja logowania (Console-First Logging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Globalne instancje sprzętowe
scAnt = ScannerController()
cam = CameraController()
scAnt.initCam(cam)

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

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Nazwa projektu nie może być pusta")
        return v.strip()

    @field_validator("x_step", "y_step", "z_step")
    @classmethod
    def validate_step_positive(cls, v):
        if v <= 0:
            raise ValueError(f"Krok skanowania musi być > 0 (otrzymano {v})")
        return v

    @field_validator("x_max", "y_max", "z_max")
    @classmethod
    def validate_max_ge_min(cls, v, info):
        axis = info.field_name.split("_")[0]
        min_val = info.data.get(f"{axis}_min")
        if min_val is not None and v <= min_val:
            raise ValueError(f"{axis}_max ({v}) musi być większe niż {axis}_min ({min_val})")
        return v

# Flaga blokująca inne polecenia w trakcie skanowania (z synchronizacją)
_scan_lock = threading.Lock()
_is_scanning = False

def _set_scanning(val: bool):
    global _is_scanning
    with _scan_lock:
        _is_scanning = val

def scanning_in_progress():
    global _is_scanning
    with _scan_lock:
        return _is_scanning

def run_scan_task(config: ScanConfig):
    _set_scanning(True)
    try:
        # Katalog docelowy
        output_dir = Path.cwd() / "scans" / config.project_name
        os.makedirs(output_dir, exist_ok=True)
        scAnt.outputFolder = str(output_dir) + "/"
        
        # Przekazanie ustawień zasięgu
        scAnt.setScanRange(0, config.x_min, config.x_max, config.x_step)
        scAnt.setScanRange(1, config.y_min, config.y_max, config.y_step)
        scAnt.setScanRange(2, config.z_min, config.z_max, config.z_step)
        
        logging.info("Rozpoczęcie procedury skanowania zlecenia z API...")
        scAnt.home()
        scAnt.runScan()
        scAnt.deEnergise()
        
    except Exception as e:
        logging.error(f"Skanowanie przerwane awarią: {e}")
    finally:
        _set_scanning(False)
        logging.info(f"Proces skanowania {config.project_name} zakończony.")

@app.post("/scan/start")
def start_scan(config: ScanConfig, background_tasks: BackgroundTasks):
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Skanowanie jest już w toku. Oczekuj na zakończenie.")
    
    background_tasks.add_task(run_scan_task, config)
    return {"message": f"Kolejkowano skanowanie projektu: {config.project_name}"}

@app.get("/scan/status")
def get_status():
    return {
        "is_scanning": scanning_in_progress(),
        "progress_percent": round(scAnt.getProgress(), 2),
        "images_taken": scAnt.images_taken,
        "images_to_take": scAnt.images_to_take
    }

@app.post("/camera/capture")
def capture_single_image(output_path: str = "test_image.tif"):
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Zasób kamery zablokowany przez proces skanowania.")
    
    full_path = str(Path.cwd() / output_path)
    cam.capture_image(full_path)
    return {"message": "Zdjęcie zrobione testowo", "path": full_path}

@app.post("/motor/home")
def home_motors():
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Silniki zajęte przez proces skanowania.")
    scAnt.home()
    return {"message": "Zakończono bazowanie osi (G28)"}

class MotorMoveRequest(BaseModel):
    axis: str
    distance: float

@app.post("/motor/move")
def move_motor(req: MotorMoveRequest):
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Silniki zajęte przez proces skanowania.")
    if req.axis.upper() not in ["X", "Y", "Z"]:
        raise HTTPException(status_code=400, detail="Nieprawidłowa oś (tylko X, Y, Z).")
    scAnt.moveRelative(req.axis, req.distance)
    return {"message": f"Przesunięto oś {req.axis} o {req.distance}"}

@app.post("/motor/disable")
def disable_motors():
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Silniki zajęte przez proces skanowania.")
    scAnt.deEnergise()
    return {"message": "Silniki odblokowane (M84)"}

import time
def mjpeg_generator():
    while True:
        frame = cam.capture_jpeg_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)  # max ~10 FPS

@app.get("/camera/stream")
def video_stream():
    return StreamingResponse(mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/scan/projects")
def list_projects():
    """Zwraca listę projektów dostępnych w folderze skanów"""
    if not os.path.exists(SCANS_DIR):
        return {"projects": []}
    return {"projects": [f.name for f in os.scandir(SCANS_DIR) if f.is_dir()]}

@app.get("/scan/files/{project}")
def list_files(project: str):
    """Zwraca listę wszystkich plików wewnątrz wybranego projektu"""
    proj_path = Path(SCANS_DIR) / project
    if not proj_path.exists() or not proj_path.is_dir():
        raise HTTPException(status_code=404, detail="Projekt nie znaleziony")
    
    files = []
    for root, _, filenames in os.walk(proj_path):
        for f in filenames:
            rel_path = Path(os.path.join(root, f)).relative_to(proj_path)
            # Normalizujemy ścieżki dla URL
            files.append(str(rel_path).replace("\\", "/"))
    return {"files": files}

@app.get("/health")
def get_health():
    """Zwraca skonsolidowany status zdrowia sprzętu."""
    return watchdog.health_status

# StaticFiles mount na końcu pliku (po trasach dynamicznych), by nie przechwytywały żądań
os.makedirs(SCANS_DIR, exist_ok=True)
app.mount("/scans_data", StaticFiles(directory=SCANS_DIR), name="scans_data")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/gui", StaticFiles(directory=STATIC_DIR, html=True), name="gui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
