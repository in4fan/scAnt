import asyncio
import httpx
import logging
import os
import time

logger = logging.getLogger("health_monitor")

# Konfiguracja adresu Moonrakera (konfigurowalny przez zmienną środowiskową)
MOONRAKER_URL = os.environ.get("MOONRAKER_URL", "http://localhost:7125")

# Globalny stan zdrowia urządzeń (eksponowany na zewnątrz)
health_status = {
    "klipper": {
        "status": "unknown",
        "failures": 0,
        "last_check": None
    },
    "camera": {
        "status": "unknown",
        "failures": 0,
        "last_check": None
    },
    "uptime_seconds": 0
}

_start_time = time.time()

async def ping_klipper():
    """Asynchroniczne sprawdzanie połączenia z Moonraker (Klipper API)."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        while True:
            try:
                # Używamy konfigurowalnego URL Moonrakera
                resp = await client.get(f"{MOONRAKER_URL}/printer/info")
                if resp.status_code == 200:
                    health_status["klipper"]["status"] = "online"
                else:
                    health_status["klipper"]["status"] = f"error_{resp.status_code}"
                    health_status["klipper"]["failures"] += 1
            except Exception as e:
                health_status["klipper"]["status"] = "offline"
                health_status["klipper"]["failures"] += 1
            
            health_status["klipper"]["last_check"] = time.time()
            
            if health_status["klipper"]["status"] != "online":
                logger.warning(f"Klipper/Moonraker problem. Status: {health_status['klipper']['status']}, URL: {MOONRAKER_URL}")
                
            await asyncio.sleep(15)  # Sprawdzaj co 15 sekund

async def ping_camera():
    """Sprawdzanie obecności fizycznej kamery."""
    while True:
        try:
            # W środowisku Linux RPi kamera HQ często figuruje jako /dev/video0
            # Możemy sprawdzić obecność interfejsu wideo:
            if os.path.exists("/dev/video0") or os.path.exists("/dev/vchiq"):
                health_status["camera"]["status"] = "online"
            else:
                health_status["camera"]["status"] = "offline"
                health_status["camera"]["failures"] += 1
        except Exception:
            health_status["camera"]["status"] = "error"
            health_status["camera"]["failures"] += 1

        health_status["camera"]["last_check"] = time.time()
        
        if health_status["camera"]["status"] != "online":
            logger.warning(f"Nie wykryto interfejsów kamery! (/dev/video0 lub /dev/vchiq)")
            
        await asyncio.sleep(20)  # Sprawdzaj co 20 sekund

async def log_uptime():
    """Okresowe logowanie stanu całego systemu na standardowe wyjście."""
    while True:
        uptime = int(time.time() - _start_time)
        health_status["uptime_seconds"] = uptime
        
        klipper_status = health_status['klipper']['status']
        cam_status = health_status['camera']['status']
        
        logger.info(f"[SYSTEM OK] Uptime: {uptime}s | Klipper: {klipper_status} | Kamera: {cam_status}")
        await asyncio.sleep(60)  # Raportuj do logów co minutę

_watchdog_tasks = []

def start_watchdogs():
    """Uruchamia wszystkie zadania w pętli zdarzeń asyncio."""
    global _watchdog_tasks
    logger.info("Uruchamianie wbudowanych Watchdogów (Klipper, Camera)...")
    _watchdog_tasks = [
        asyncio.create_task(ping_klipper()),
        asyncio.create_task(ping_camera()),
        asyncio.create_task(log_uptime()),
    ]

async def stop_watchdogs():
    """Anuluje wszystkie zadania watchdogów."""
    for task in _watchdog_tasks:
        task.cancel()
    if _watchdog_tasks:
        await asyncio.gather(*_watchdog_tasks, return_exceptions=True)
        _watchdog_tasks.clear()