import os
import time
import requests
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class HardwareCommunicationError(RuntimeError):
    """Raised when communication with the motion controller fails."""

class ScannerController:
    """
    Kontroler skanera komunikujący się z Klipperem za pośrednictwem API Moonraker.
    Zastępuje starą implementację opartą na komendach 'ticcmd' dla sterowników Pololu.
    """
    def __init__(self, moonraker_url="http://localhost:7125"):
        self.moonraker_url = moonraker_url
        self.stepper_names = ["X", "Y", "Z"]

        # Domyślne limity bezpieczeństwa (fallback jeśli nie uda się pobrać z Moonrakera)
        # Wartości te powinny być zgodne z konfiguracją Klippera w skr_pico_klipper.cfg
        self.stepper_maxPos = [45, 160, 0]   # mm/deg
        self.stepper_minPos = [0, -160, -450]

        # Pobierz rzeczywiste limity z Klippera (jeśli dostępne)
        self._fetch_klipper_limits()

        # Ustawienia skanowania (krok w mm/deg)
        self.scan_stepSize = [5, 8, 50]
        self.scan_pos = [None, None, None]
        
        # Inicjalizacja list skanowania
        self.setScanRange(stepper=0, min_val=0, max_val=45, step=self.scan_stepSize[0])
        self.setScanRange(stepper=1, min_val=0, max_val=160, step=self.scan_stepSize[1])
        self.setScanRange(stepper=2, min_val=-250, max_val=-80, step=self.scan_stepSize[2])

        self.completedRotations = 0
        self.completedStacks = 0
        self.cancel_requested = False
        
        # Inicjalizacja zmiennych na potrzeby postępu
        self.images_taken = 0
        self.images_to_take = len(self.scan_pos[0]) * len(self.scan_pos[1]) * len(self.scan_pos[2])
        self.progress = self.getProgress()
        self.outputFolder = ""
        self.cam = None

    def correctName(self, val):
        """Formatowanie nazwy pliku (uzupełnianie zerami)"""
        val_int = int(val)
        sign = "n" if val_int < 0 else "p"
        return f"{sign}{abs(val_int):05d}"

    def _fetch_klipper_limits(self):
        """Pobiera rzeczywiste limity pozycji z konfiguracji Klippera przez Moonraker."""
        try:
            resp = requests.get(
                f"{self.moonraker_url}/printer/objects/query?configfile",
                timeout=5
            )
            resp.raise_for_status()
            data = resp.json()
            config = data.get("result", {}).get("status", {}).get("configfile", {}).get("config", {})
            
            # Parsowanie limitów dla każdej osi
            for axis in ["x", "y", "z"]:
                section = config.get(f"stepper_{axis}", {})
                if section:
                    pos_min = section.get("position_min")
                    pos_max = section.get("position_max")
                    if pos_min is not None and pos_max is not None:
                        idx = self.stepper_names.index(axis.upper())
                        self.stepper_minPos[idx] = float(pos_min)
                        self.stepper_maxPos[idx] = float(pos_max)
                        logger.info(f"Zaktualizowano limity osi {axis.upper()}: min={pos_min}, max={pos_max}")
        except Exception as e:
            logger.warning(f"Nie udało się pobrać limitów z Klippera: {e}. Użyto wartości domyślnych.")

    def send_gcode(self, gcode: str):
        """Wysyła polecenie G-Code do Klippera przez Moonrakera z retry logic."""
        logger.debug(f"Wysyłanie G-Code: {gcode}")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.moonraker_url}/printer/gcode/script", 
                    json={"script": gcode},
                    timeout=5
                )
                response.raise_for_status()
                return  # Sukces
            except requests.exceptions.RequestException as e:
                logger.error(f"Błąd komunikacji z Moonrakerem przy wysyłaniu '{gcode}' (próba {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Czekaj przed retry
                else:
                    raise HardwareCommunicationError(
                        f"Nie udało się wysłać komendy do Moonrakera po {max_retries} próbach: {gcode}"
                    ) from e

    def wait_for_moves(self, settle_time=0.5):
        """
        Czeka na zakończenie ruchu (M400) i dodaje czas na ustabilizowanie drgań,
        co jest kluczowe w makrofotografii (settle time).
        Polluje status toolhead aby upewnić się że ruch się zakończył.
        """
        self.send_gcode("M400")
        
        # Polluj status toolhead aby sprawdzić czy ruch się zakończył
        max_polls = 20
        for _ in range(max_polls):
            try:
                resp = requests.get(
                    f"{self.moonraker_url}/printer/objects/query?toolhead",
                    timeout=3
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("result", {}).get("status", {}).get("toolhead", {})
                    # Sprawdź czy homing jest zakończony
                    if not status.get("homing", False):
                        break
            except Exception:
                pass
            time.sleep(0.25)
        
        # Proste opóźnienie na wygaszenie drgań mechanicznych przed zrobieniem zdjęcia.
        time.sleep(settle_time)

    def deEnergise(self):
        """Wyłącza silniki krokowe (odpowiednik M18 / M84)"""
        logger.info("Wyłączanie silników...")
        self.send_gcode("M84")

    def home(self, stepper=None):
        """Bazowanie osi (G28)"""
        axis = ""
        if stepper is not None:
            axis = self.stepper_names[stepper]
            logger.info(f"Bazowanie osi {axis}...")
            self.send_gcode(f"G28 {axis}")
        else:
            logger.info("Bazowanie wszystkich osi...")
            self.send_gcode("G28")
            
        self.wait_for_moves(settle_time=1.0)

    def moveToPosition(self, stepper, pos):
        """Przesuwa daną oś na podaną pozycję absolutną"""
        # Limity bezpieczeństwa (z pobranych wartości z Klippera lub domyślnych)
        if pos > self.stepper_maxPos[stepper]:
            logger.warning(f"Pozycja {pos} przekracza max {self.stepper_maxPos[stepper]} — ograniczono.")
            pos = self.stepper_maxPos[stepper]
        elif pos < self.stepper_minPos[stepper]:
            logger.warning(f"Pozycja {pos} poniżej min {self.stepper_minPos[stepper]} — ograniczono.")
            pos = self.stepper_minPos[stepper]

        axis = self.stepper_names[stepper]
        logger.info(f"Ruch osi {axis} na pozycję {pos}")
        
        # Używamy G0 z wybraną posuwnością (F). F3000 = 50mm/s
        self.send_gcode(f"G0 {axis}{pos} F3000")
        self.wait_for_moves(settle_time=0.4)

    def moveRelative(self, axis_name: str, distance: float):
        """Przesuwa daną oś o podany dystans (ruch relatywny)"""
        logger.info(f"Ruch relatywny osi {axis_name} o {distance}")
        # G91 włącza tryb relatywny, po ruchu wracamy do absolutnego G90
        self.send_gcode("G91")
        self.send_gcode(f"G0 {axis_name.upper()}{distance} F3000")
        self.send_gcode("G90")
        self.wait_for_moves(settle_time=0.4)

    def setScanRange(self, stepper, min_val, max_val, step):
        """Oblicza listę pozycji do zeskanowania dla konkretnej osi"""
        # Walidacja z limitami z Klippera
        if max_val > self.stepper_maxPos[stepper]:
            logger.warning(f"max_val={max_val} przekracza limit {self.stepper_maxPos[stepper]} — ograniczono.")
            max_val = self.stepper_maxPos[stepper]
        if min_val < self.stepper_minPos[stepper]:
            logger.warning(f"min_val={min_val} poniżej limitu {self.stepper_minPos[stepper]} — ograniczono.")
            min_val = self.stepper_minPos[stepper]

        self.scan_stepSize[stepper] = step
        if step <= 0:
            logger.error(f"Krok skanowania dla osi {self.stepper_names[stepper]} musi być > 0 (otrzymano {step}).")
            self.scan_pos[stepper] = np.array([min_val])
            return

        self.scan_pos[stepper] = np.array(np.arange(int(min_val), int(max_val) + 1, int(self.scan_stepSize[stepper])), dtype=int)
        
        if len(self.scan_pos[stepper]) == 0:
            logger.warning(f"Błąd wejścia: brak punktów skanowania dla osi {self.stepper_names[stepper]} (min={min_val}, max={max_val}, step={step}).")
            self.scan_pos[stepper] = np.array([min_val])

    def getProgress(self):
        if self.images_to_take == 0:
            return 0
        return 100.0 * (self.images_taken / self.images_to_take)

    def initCam(self, cam):
        self.cam = cam

    def runScan(self):
        logger.info("Rozpoczynamy skanowanie...")
        self.completedRotations = 0
        self.completedStacks = 0
        self.images_to_take = len(self.scan_pos[0]) * len(self.scan_pos[1]) * len(self.scan_pos[2])
        self.images_taken = 0
        self.progress = 0
        self.cancel_requested = False

        for posX in self.scan_pos[0]:
            if self.cancel_requested:
                logger.info("Skanowanie anulowane przez użytkownika.")
                break
            self.moveToPosition(0, posX)
            
            for posY in self.scan_pos[1]:
                if self.cancel_requested:
                    logger.info("Skanowanie anulowane przez użytkownika.")
                    break
                # Dla stołu obrotowego pozycje Y cyklicznie wracają do zera
                current_y = posY + (self.completedRotations * self.stepper_maxPos[1]) % 360
                self.moveToPosition(1, current_y)
                
                for posZ in self.scan_pos[2]:
                    if self.cancel_requested:
                        logger.info("Skanowanie anulowane przez użytkownika.")
                        break
                    self.moveToPosition(2, posZ)
                    
                    img_name = os.path.join(
                        self.outputFolder,
                        f"x_{self.correctName(posX)}_y_{self.correctName(posY)}_step_{self.correctName(posZ)}_.tif"
                    )

                    if self.cam:
                        self.cam.capture_image(img_name=img_name)
                    
                    self.images_taken += 1
                    self.progress = self.getProgress()
                    logger.info(f"Postęp skanowania: {self.progress:.1f}%")

                self.completedStacks += 1
            self.completedRotations += 1

        logger.info("Skanowanie zakończone. Powrót do pozycji bazowej.")
        # Powrót do pozycji początkowej (domyślnej) - wartości do dostosowania!
        self.moveToPosition(0, 19)
        self.moveToPosition(1, (self.completedRotations * self.stepper_maxPos[1]) % 360)
        self.moveToPosition(2, -20)

    def get_position(self):
        """Odczytuje aktualną pozycję osi z Moonrakera."""
        try:
            resp = requests.get(
                f"{self.moonraker_url}/printer/objects/query?gcode_move",
                timeout=3
            )
            resp.raise_for_status()
            data = resp.json()
            pos = data.get("result", {}).get("status", {}).get("gcode_move", {}).get("position", [None, None, None])
            return {"x": pos[0], "y": pos[1], "z": pos[2]}
        except requests.exceptions.RequestException as e:
            logger.error(f"Błąd odczytu pozycji z Moonrakera: {e}")
            raise HardwareCommunicationError(f"Nie udało się odczytać pozycji: {e}") from e

if __name__ == '__main__':
    from camera_controller import CameraController
    
    logger.info("Testowanie komunikacji Klipper/Moonraker oraz RPI-HQ-CAMERA")
    
    scAnt = ScannerController()
    cam = CameraController()
    scAnt.initCam(cam)

    # Ustawiamy katalog roboczy na wyniki
    scAnt.outputFolder = str(Path.cwd() / "test_scans")
    if not os.path.exists(scAnt.outputFolder):
        os.makedirs(scAnt.outputFolder)

    # 1. Bazowanie
    scAnt.home()

    # 2. Szybki test ruchu
    scAnt.moveToPosition(0, 19)
    scAnt.moveToPosition(1, 20)
    scAnt.moveToPosition(1, 0)
    scAnt.moveToPosition(2, -20)

    # 3. Test zrobienia zdjęcia
    test_img = os.path.join(scAnt.outputFolder, "testy_mac_testface.tif")
    scAnt.cam.capture_image(img_name=test_img)

    # Wyłączenie silników i kamery
    scAnt.deEnergise()
    scAnt.cam.exit_cam()
    logger.info("Demo testowe zakończone sukcesem!")
