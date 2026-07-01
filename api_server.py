from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from contextlib import asynccontextmanager
import logging
import asyncio
import threading
import time
from functools import wraps
from scripts.Scanner_Controller import ScannerController, HardwareCommunicationError
from scripts.camera_controller import CameraController
import os
from pathlib import Path
import watchdog

# Zmienne środowiskowe dla ścieżek (z fallbackiem do Dockerowych domyślnych)
SCANS_DIR = os.environ.get("SCANS_DIR", "/app/scans")
STATIC_DIR = os.environ.get("STATIC_DIR", "/app/static")

# Prosty rate limiter (zapobiega przeciążeniu Moonrakera przy szybkim klikaniu)
_rate_limit_store = {}
_rate_limit_lock = threading.Lock()

def rate_limit(max_calls: int = 3, per_seconds: int = 1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = func.__name__
            now = time.time()
            with _rate_limit_lock:
                window = _rate_limit_store.get(key, [])
                window = [t for t in window if now - t < per_seconds]
                if len(window) >= max_calls:
                    raise HTTPException(status_code=429, detail="Zbyt wiele żądań. Poczekaj chwilę.")
                window.append(now)
                _rate_limit_store[key] = window
            return func(*args, **kwargs)
        return wrapper
    return decorator

@asynccontextmanager
async def lifespan(app):
    watchdog.start_watchdogs()
    os.makedirs(SCANS_DIR, exist_ok=True)
    app.mount("/scans_data", StaticFiles(directory=SCANS_DIR), name="scans_data")
    os.makedirs(STATIC_DIR, exist_ok=True)
    app.mount("/gui", StaticFiles(directory=STATIC_DIR, html=True), name="gui")
    yield
    cam = getattr(app.state, "camera", None)
    if cam:
        cam.exit_cam()
    asyncio.create_task(watchdog.stop_watchdogs())

app = FastAPI(title="scAnt API", description="API do sterowania skanerem 3D scAnt", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_hardware_lock = threading.Lock()


def _ensure_hardware():
    with _hardware_lock:
        scanner = getattr(app.state, "scanner", None)
        camera = getattr(app.state, "camera", None)

        if scanner is None or camera is None:
            scanner = ScannerController()
            camera = CameraController()
            scanner.initCam(camera)
            app.state.scanner = scanner
            app.state.camera = camera
        elif getattr(scanner, "cam", None) is None:
            scanner.initCam(camera)

        return scanner, camera


def _get_scanner():
    return _ensure_hardware()[0]


def _get_camera():
    return _ensure_hardware()[1]

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


def _try_start_scanning():
    global _is_scanning
    with _scan_lock:
        if _is_scanning:
            return False
        _is_scanning = True
        return True

def scanning_in_progress():
    global _is_scanning
    with _scan_lock:
        return _is_scanning

def run_scan_task(config: ScanConfig):
    scAnt = _get_scanner()
    scAnt.cancel_requested = False
    try:
        # Katalog docelowy - używamy SCANS_DIR dla spójności
        output_dir = Path(SCANS_DIR) / config.project_name
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
    except HardwareCommunicationError as e:
        logging.error(f"Skanowanie przerwane błędem komunikacji sprzętowej: {e}")
    except Exception as e:
        logging.error(f"Skanowanie przerwane awarią: {e}")
    finally:
        _set_scanning(False)
        logging.info(f"Proces skanowania {config.project_name} zakończony.")

@app.post("/scan/start")
def start_scan(config: ScanConfig, background_tasks: BackgroundTasks):
    if not _try_start_scanning():
        raise HTTPException(status_code=400, detail="Skanowanie jest już w toku. Oczekuj na zakończenie.")

    try:
        background_tasks.add_task(run_scan_task, config)
    except Exception:
        _set_scanning(False)
        raise
    return {"message": f"Kolejkowano skanowanie projektu: {config.project_name}"}

@app.get("/scan/status")
def get_status():
    scAnt = _get_scanner()
    return {
        "is_scanning": scanning_in_progress(),
        "progress_percent": round(scAnt.getProgress(), 2),
        "images_taken": scAnt.images_taken,
        "images_to_take": scAnt.images_to_take
    }

@app.post("/camera/capture")
@rate_limit(max_calls=2, per_seconds=3)
def capture_single_image(output_path: str = "test_image.tif"):
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Zasób kamery zablokowany przez proces skanowania.")
    
    full_path = str(Path.cwd() / output_path)
    cam = _get_camera()
    cam.capture_image(full_path)
    return {"message": "Zdjęcie zrobione testowo", "path": full_path}

@app.post("/motor/home")
@rate_limit(max_calls=2, per_seconds=5)
def home_motors():
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Silniki zajęte przez proces skanowania.")
    try:
        scAnt = _get_scanner()
        scAnt.home()
    except HardwareCommunicationError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"message": "Zakończono bazowanie osi (G28)"}

class MotorMoveRequest(BaseModel):
    axis: str
    distance: float

@app.post("/motor/move")
@rate_limit(max_calls=5, per_seconds=1)
def move_motor(req: MotorMoveRequest):
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Silniki zajęte przez proces skanowania.")
    if req.axis.upper() not in ["X", "Y", "Z"]:
        raise HTTPException(status_code=400, detail="Nieprawidłowa oś (tylko X, Y, Z).")
    try:
        scAnt = _get_scanner()
        scAnt.moveRelative(req.axis, req.distance)
    except HardwareCommunicationError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"message": f"Przesunięto oś {req.axis} o {req.distance}"}

@app.post("/motor/disable")
def disable_motors():
    if scanning_in_progress():
        raise HTTPException(status_code=400, detail="Silniki zajęte przez proces skanowania.")
    try:
        scAnt = _get_scanner()
        scAnt.deEnergise()
    except HardwareCommunicationError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"message": "Silniki odblokowane (M84)"}

@app.post("/scan/cancel")
def cancel_scan():
    """Przerywa trwające skanowanie."""
    if not scanning_in_progress():
        raise HTTPException(status_code=400, detail="Brak aktywnego skanowania do anulowania.")
    scAnt = _get_scanner()
    scAnt.cancel_requested = True
    logging.info("Żądanie anulowania skanowania przyjęte.")
    return {"message": "Skanowanie zostanie przerwane po zakończeniu bieżącego zdjęcia."}

@app.get("/motor/position")
def motor_position():
    """Zwraca aktualną pozycję osi X/Y/Z z Moonrakera."""
    scAnt = _get_scanner()
    return scAnt.get_position()

async def mjpeg_generator():
    cam = _get_camera()
    while True:
        frame = cam.capture_jpeg_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        await asyncio.sleep(0.1)  # max ~10 FPS

@app.get("/camera/stream")
async def video_stream():
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
