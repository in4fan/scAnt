import os
import time
import requests
import logging
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ScannerController:
    """
    Kontroler skanera komunikujący się z Klipperem za pośrednictwem API Moonraker.
    Zastępuje starą implementację opartą na komendach 'ticcmd' dla sterowników Pololu.
    """
    def __init__(self, moonraker_url="http://localhost:7125"):
        self.moonraker_url = moonraker_url
        self.stepper_names = ["X", "Y", "Z"]

        # UWAGA: W przeciwieństwie do starego systemu (który operował na mikrokrokach np. 50000),
        # Klipper operuje na milimetrach (mm) lub stopniach (w zależności od rotation_distance).
        # Poniższe limity i zakresy należy dostosować do fizycznych wymiarów w mm/stopniach!
        self.stepper_maxPos = [45, 160, 0]   # Przykładowe wartości w mm/deg
        self.stepper_minPos = [0, -160, -450]

        # Ustawienia skanowania (krok w mm/deg)
        self.scan_stepSize = [5, 8, 50]
        self.scan_pos = [None, None, None]
        
        # Inicjalizacja list skanowania
        self.setScanRange(stepper=0, min_val=0, max_val=45, step=self.scan_stepSize[0])
        self.setScanRange(stepper=1, min_val=0, max_val=160, step=self.scan_stepSize[1])
        self.setScanRange(stepper=2, min_val=-250, max_val=-80, step=self.scan_stepSize[2])

        self.completedRotations = 0
        self.completedStacks = 0
        
        # Inicjalizacja zmiennych na potrzeby postępu
        self.images_taken = 0
        self.images_to_take = len(self.scan_pos[0]) * len(self.scan_pos[1]) * len(self.scan_pos[2])
        self.progress = self.getProgress()
        self.outputFolder = ""
        self.cam = None

    def correctName(self, val):
        """Formatowanie nazwy pliku (uzupełnianie zerami)"""
        val_abs = abs(int(val))
        return f"{val_abs:05d}"

    def send_gcode(self, gcode: str):
        """Wysyła polecenie G-Code do Klippera przez Moonrakera"""
        logging.debug(f"Wysyłanie G-Code: {gcode}")
        try:
            response = requests.post(
                f"{self.moonraker_url}/printer/gcode/script", 
                json={"script": gcode},
                timeout=5
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd komunikacji z Moonrakerem przy wysyłaniu '{gcode}': {e}")

    def wait_for_moves(self, settle_time=0.5):
        """
        Czeka na zakończenie ruchu (M400) i dodaje czas na ustabilizowanie drgań,
        co jest kluczowe w makrofotografii (settle time).
        """
        self.send_gcode("M400")
        # Proste opóźnienie na wygaszenie drgań mechanicznych przed zrobieniem zdjęcia.
        time.sleep(settle_time)

    def deEnergise(self):
        """Wyłącza silniki krokowe (odpowiednik M18 / M84)"""
        logging.info("Wyłączanie silników...")
        self.send_gcode("M84")

    def home(self, stepper=None):
        """Bazowanie osi (G28)"""
        axis = ""
        if stepper is not None:
            axis = self.stepper_names[stepper]
            logging.info(f"Bazowanie osi {axis}...")
            self.send_gcode(f"G28 {axis}")
        else:
            logging.info("Bazowanie wszystkich osi...")
            self.send_gcode("G28")
            
        self.wait_for_moves(settle_time=1.0)

    def moveToPosition(self, stepper, pos):
        """Przesuwa daną oś na podaną pozycję absolutną"""
        # Limity bezpieczeństwa
        if pos > self.stepper_maxPos[stepper]:
            pos = self.stepper_maxPos[stepper]
        elif pos < self.stepper_minPos[stepper]:
            pos = self.stepper_minPos[stepper]

        axis = self.stepper_names[stepper]
        logging.info(f"Ruch osi {axis} na pozycję {pos}")
        
        # Używamy G0 z wybraną posuwnością (F). F3000 = 50mm/s
        self.send_gcode(f"G0 {axis}{pos} F3000")
        self.wait_for_moves(settle_time=0.4)

    def moveRelative(self, axis_name: str, distance: float):
        """Przesuwa daną oś o podany dystans (ruch relatywny)"""
        logging.info(f"Ruch relatywny osi {axis_name} o {distance}")
        # G91 włącza tryb relatywny, po ruchu wracamy do absolutnego G90
        self.send_gcode("G91")
        self.send_gcode(f"G0 {axis_name.upper()}{distance} F3000")
        self.send_gcode("G90")
        self.wait_for_moves(settle_time=0.4)

    def setScanRange(self, stepper, min_val, max_val, step):
        """Oblicza listę pozycji do zeskanowania dla konkretnej osi"""
        if max_val > self.stepper_maxPos[stepper]:
            max_val = self.stepper_maxPos[stepper]
        elif min_val < self.stepper_minPos[stepper]:
            min_val = self.stepper_minPos[stepper]

        self.scan_stepSize[stepper] = step
        self.scan_pos[stepper] = np.array(np.arange(int(min_val), int(max_val), int(self.scan_stepSize[stepper])), dtype=int)
        
        if len(self.scan_pos[stepper]) == 0:
            logging.warning(f"Błąd wejścia: brak punktów skanowania dla osi {self.stepper_names[stepper]}.")
            self.scan_pos[stepper] = np.array([0])

    def getProgress(self):
        if self.images_to_take == 0:
            return 0
        return 100.0 * (self.images_taken / self.images_to_take)

    def initCam(self, cam):
        self.cam = cam

    def runScan(self):
        logging.info("Rozpoczynamy skanowanie...")
        self.images_to_take = len(self.scan_pos[0]) * len(self.scan_pos[1]) * len(self.scan_pos[2])
        self.images_taken = 0

        for posX in self.scan_pos[0]:
            self.moveToPosition(0, posX)
            
            for posY in self.scan_pos[1]:
                # W przypadku stołu obrotowego możemy sumować pełne obroty,
                # ale dla Klippera łatwiej zresetować oś pozycją G92 lub używać pozycji relatywnych.
                # Zostawiamy logikę absolutną tak jak było w oryginale, 
                # ale z wartościami odpowiednimi dla nowej jednostki.
                current_y = posY + self.completedRotations * self.stepper_maxPos[1]
                self.moveToPosition(1, current_y)
                
                for posZ in self.scan_pos[2]:
                    self.moveToPosition(2, posZ)
                    
                    img_name = os.path.join(
                        self.outputFolder,
                        f"x_{self.correctName(posX)}_y_{self.correctName(posY)}_step_{self.correctName(posZ)}_.tif"
                    )

                    if self.cam:
                        self.cam.capture_image(img_name=img_name)
                    
                    self.images_taken += 1
                    self.progress = self.getProgress()
                    logging.info(f"Postęp skanowania: {self.progress:.1f}%")

                self.completedStacks += 1
            self.completedRotations += 1

        logging.info("Skanowanie zakończone. Powrót do pozycji bazowej.")
        # Powrót do pozycji początkowej (domyślnej) - wartości do dostosowania!
        self.moveToPosition(0, 19)
        self.moveToPosition(1, self.completedRotations * self.stepper_maxPos[1])
        self.moveToPosition(2, -20)

if __name__ == '__main__':
    from camera_controller import CameraController
    
    logging.info("Testowanie komunikacji Klipper/Moonraker oraz RPI-HQ-CAMERA")
    
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
    logging.info("Demo testowe zakończone sukcesem!")
