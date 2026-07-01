# Wybieramy oficjalny lżejszy obraz Pythona 3.11
FROM python:3.11-slim

# Instalacja zależności systemowych niezbędnych dla działania libcamera (picamera2) i OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    v4l-utils \
    libcamera-dev \
    gcc \
    python3-dev \
    libcap-dev \
    rclone \
    && rm -rf /var/lib/apt/lists/*

# Ustawiamy katalog roboczy
WORKDIR /app

# Najpierw requirements.txt dla lepszego cache'owania warstw Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie całego kodu z repozytorium do kontenera
COPY . /app

# Wystawienie portu dla serwera FastAPI
EXPOSE 8000

# Zmienna systemowa zmuszająca Pythona do niesprawdzania bufora (logi od razu na stdout)
ENV PYTHONUNBUFFERED=1

# Domyślne uruchomienie serwera API
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
