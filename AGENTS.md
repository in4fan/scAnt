# scAnt

Open-source 3D scanner for arthropods — Raspberry Pi + BTT SKR Pico (Klipper) + RPI-HQ-CAMERA.

## Architecture

- **REST API** (FastAPI) — `api_server.py`, runs in Docker with `network_mode: host`
- **CLI** — `scant_cli.py` talks to the API
- **Post-processing worker** — separate Compose file (`docker-compose.worker.yml`) for EDOF/focus stacking
- **No PyQt5 GUI** — headless RPi only
- **Klipper** via Moonraker HTTP API (not direct `ticcmd`)

## Commands

```bash
# Full stack (API + hardware)
docker compose up --build -d

# Post-processing worker (run on PC, not RPi)
BUILDKIT_PROGRESS=plain docker compose -f docker-compose.worker.yml up --build -d

# Fetch scans from RPi to PC
python scant_cli.py fetch --project "name" --host <RPI_IP>

# Process scans (stack + mask)
python scant_cli.py process --project "name"

# Run tests (needs Docker running)
pytest
```

## Key hardware requirements

- Container runs `privileged: true` with devices mapped: `/dev/vchiq`, `/dev/video0`, `/dev/dma_heap` (kernel 6.1+)
- Camera: picamera2 only (no FLIR/DSLR support)
- Stepper motor control via Moonraker HTTP API
- Scan storage: `./scans` volume mapped into container

## Conventions

- Console-first logging: `PYTHONUNBUFFERED=1`, never redirect to `/dev/null`
- Built-in watchdogs for Klipper/Moonraker connection and camera status (reported to stdout)
- Use `gh` (GitHub CLI) instead of `git` for version control
- Docker-only: zero dependencies on host beyond Docker + Compose
