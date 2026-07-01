import os
import time
import logging
import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None

logger = logger.getLogger(__name__)

try:
    from picamera2 import Picamera2
except ImportError:
    logger.warning("Biblioteka picamera2 nie jest zainstalowana lub skrypt nie jest uruchomiony na Raspberry Pi. Kamera będzie działać w trybie symulacji.")
    Picamera2 = None

class CameraController:
    """
    Kontroler do obsługi RPI-HQ-CAMERA z wykorzystaniem picamera2.
    """
    def __init__(self):
        self.picam2 = None
        if Picamera2 is not None:
            try:
                self.picam2 = Picamera2()
                # Skonfiguruj dla wysokiej rozdzielczości (zdjęcia statyczne / stils)
                config = self.picam2.create_still_configuration()
                self.picam2.configure(config)
                self.picam2.start()
                logger.info("Kamera RPI-HQ uruchomiona pomyślnie.")
            except Exception as e:
                logger.error(f"Nie udało się zainicjalizować kamery picamera2: {e}")
                self.picam2 = None

    def configure_exposure(self, exposure_time_us=None, gain=None, awb_mode='auto'):
        """
        Pozwala na ręczną konfigurację parametrów naświetlania.
        exposure_time_us: Czas naświetlania w mikrosekundach.
        gain: Wzmocnienie analogowe (odpowiednik ISO).
        awb_mode: Tryb balansu bieli.
        """
        if self.picam2 is None:
            logger.debug(f"Symulacja: configure_exposure(exposure={exposure_time_us}, gain={gain}, awb={awb_mode})")
            return
            
        controls = {}
        if exposure_time_us is not None:
            controls["ExposureTime"] = exposure_time_us
        if gain is not None:
            controls["AnalogueGain"] = gain
            
        # Zależnie od wersji picamera2, AwbMode może wymagać int'a, 
        # ale większość prostych ustawień obsługuje mapowanie string.
        # W razie problemów można usunąć lub dostosować awb_mode.
        # controls["AwbMode"] = awb_mode
        
        try:
            self.picam2.set_controls(controls)
            logger.info(f"Parametry kamery zostały zaktualizowane: {controls}")
        except Exception as e:
            logger.error(f"Błąd podczas ustawiania parametrów kamery: {e}")

    def capture_image(self, img_name: str):
        """
        Główna metoda używana przez kontroler skanera do robienia zdjęcia.
        """
        if self.picam2 is None:
            logger.info(f"Symulacja zrzutu ekranu: Zapisuję plik na sucho -> {img_name}")
            time.sleep(0.1) # Symulacja czasu robienia zdjęcia
            # Generujemy minimalny poprawny obrazek testowy
            dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
            if cv2 is not None:
                cv2.putText(dummy_img, "SYMULACJA", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imwrite(img_name, dummy_img)
            return
            
        try:
            # capture_file robi zdjęcie w formacie zadanym przez rozszerzenie img_name (np. .jpg, .tif)
            self.picam2.capture_file(img_name)
            logger.info(f"Zdjęcie zapisane pomyślnie: {img_name}")
        except Exception as e:
            logger.error(f"Błąd podczas robienia zdjęcia ({img_name}): {e}")

    def start_preview(self):
        """
        Włącza podgląd wideo.
        """
        if self.picam2:
            self.picam2.start()
            logger.info("Podgląd kamery uruchomiony.")

    def stop_preview(self):
        """
        Zatrzymuje podgląd wideo.
        """
        if self.picam2:
            self.picam2.stop()
            logger.info("Podgląd kamery zatrzymany.")

    def exit_cam(self):
        """
        Bezpieczne zamknięcie połączenia z kamerą.
        """
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
            logger.info("Połączenie z kamerą zamknięte.")

    def capture_jpeg_frame(self):
        """Pobiera pojedynczą klatkę jako strumień bajtów JPEG dla GUI."""
        if self.picam2 is None or cv2 is None:
            # Tryb symulacji: wygeneruj szum / obraz testowy
            img = np.zeros((480, 640, 3), dtype=np.uint8)
            if cv2 is not None:
                cv2.putText(img, "KAMERA - TRYB SYMULACJI", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                ret, jpeg = cv2.imencode('.jpg', img)
                return jpeg.tobytes()
            return b""
        
        try:
            # Capture numpy array z picamera2
            array = self.picam2.capture_array("main")
            # Konwersja RGB do BGR dla poprawnych kolorów w OpenCV
            array_bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            # Kodowanie do JPEG ze zmniejszoną jakością dla płynności
            ret, jpeg = cv2.imencode('.jpg', array_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            return jpeg.tobytes()
        except Exception as e:
            logger.error(f"Błąd podczas pobierania klatki wideo: {e}")
            return b""
