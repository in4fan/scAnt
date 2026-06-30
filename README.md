# scAnt - Open Source 3D Scanner

[**scAnt**](https://peerj.com/articles/11155/) is an open-source, low-cost macro 3D scanner, designed to automate the creation of digital 3D models of insects of various sizes in full colour. **scAnt** provides example configurations for the scanning process, as well as scripts for stacking and masking of images to prepare them for the photogrammetry software of your choice. Some examples of models generated with **scAnt** can be found on http://bit.ly/ScAnt-3D as well as on our [Sketchfab Collection](https://sketchfab.com/EvoBiomech/collections/scant-collection)!

![](images/model_collection_showcase_04_updated.jpg)

The [**scAnt**](https://peerj.com/articles/11155/) paper can be found [here](https://peerj.com/articles/11155/):

Plum F, Labonte D. 2021. scAnt—an open-source platform for the creation of 3D models of arthropods (and other small objects) PeerJ 9:e11155 https://doi.org/10.7717/peerj.11155

All structural components of the scanner can be manufactured using 3D-printing and laser cutting; the required files are available for download in .ipt, .iam, .stl, and .svg format on our [thingiverse](https://www.thingiverse.com/thing:4694713) page.

![](images/scanner_3D_comp.png)

## Updates
- **scAnt 2.0 (New Architecture!)** The project has been fully migrated to a headless **Raspberry Pi** setup. It now relies on **Docker**, **Klipper** (with BTT SKR Pico), and the **RPI-HQ-CAMERA**. The old PyQt5 GUI and Pololu/Spinnaker dependencies have been replaced by a modern REST API (FastAPI) and CLI tool, ensuring a robust, zero-configuration deployment!
- **scAnt 1.3** New faster [stacking method](https://github.com/PetteriAimonen/focus-stack) and updated GUI with added post-processing functionality. We also combined post-processing steps into one file accessed through GUI and command line.
- **scAnt 1.2** Significantly improved image capture speed for FLIR cameras. As this increases the hardware demand during scanning, it may be advisable to run stacking and masking separately (see [provided python cli scripts](https://github.com/evo-biomech/scAnt/tree/master/scripts)), instead of during scanning. We also updated the respective stacking, masking, and meta data scripts to accomodate a wider range of applications.

> [!TIP]
> When using [Max Simon's]([simonmax@oregonstate.edu](mailto:simonmax@oregonstate.edu)) wonderful [scAnt reconstruction protocol](https://docs.google.com/document/d/1OiYXgazRmuOaInz6f8jFZRLZI9l8wS4ZWVEVKSMpMTQ/edit), use [THIS v1.2](https://github.com/evo-biomech/scAnt/releases/tag/V_1.2.0) release instead!


## Installation

**scAnt** has been fully reimagined for a headless Raspberry Pi architecture. It now runs exclusively via **Docker** to ensure all dependencies (such as Klipper, Moonraker, OpenCV, and picamera2) are perfectly isolated and require zero manual host configuration.

### Prerequisites
1. **Raspberry Pi 4 / 5** with Raspberry Pi OS (Bullseye/Bookworm).
2. **Docker** and **Docker Compose** installed on the Raspberry Pi.
3. **BTT SKR Pico** board flashed with Klipper, connected via USB.
Navigate to the root of the repository and execute (use `--progress=plain` to see full build logs):
```bash
docker compose up --build -d
```
This command will build the API Server and bind the required hardware components to the container.

### Hardware Setup
Please refer to our new [Hardware Wiring Documentation](docs/hardware_wiring.md) for details on connecting stepper motors and the BTT SKR Pico.
For the Klipper configuration, a pre-made file is available at [config/skr_pico_klipper.cfg](config/skr_pico_klipper.cfg).

### Usage
Once the Docker container is running, the REST API will be available at `http://<YOUR_RPI_IP>:8000`.
You can interact with the scanner using the built-in CLI tool from your terminal:
```bash
# Get the current scanner status
python scant_cli.py status

# Home the stepper motors (G28)
python scant_cli.py home

# Run a full scan sequence
python scant_cli.py scan --project "my_first_bug" --wait
```

### Post-Processing (EDOF & Focus Stacking)
Upewnij się, że malinka zgromadziła odpowiednią liczbę zdjęć, a w folderze `scans` masz projekt (np. `mucha_domowa`). Odpal u siebie roboczo kontener workera (tylko na czas przeliczania):

```bash
BUILDKIT_PROGRESS=plain docker compose -f docker-compose.worker.yml up --build -d
```
Kiedy kontener workera działa w tle, możesz pobrać i przetworzyć dane z Raspberry Pi:
```bash
# Pobranie danych z RPi na PC
python scant_cli.py fetch --project "my_first_bug" --host <IP_RASPBERRY_PI>

# Rozpoczęcie łączenia zdjęć (przez Dockera)
python scant_cli.py process --project "my_first_bug"
```

***

## Meshroom Guide

**Add your camera to the sensor database**

Within the directory of the downloaded Meshroom installation, go to the following folder and, if you can't find your camera, edit the file “**cameraSensors.db**” using any common text editor:

*…/Meshroom-2019.2.0/AliceVision/share/AliceVision/cameraSensors.db*

The entry should contain the following:

```bash
Make;Model;SensorWidth
```
Ensure to enter these details as they are listed in your project configuration file, thus, metadata of your stacked and masked images. There should be no spaces between the entries. If you are using the same FLIR camera as in the original **scAnt**, add the following line:

```bash
FLIR;BFS-U3-200S6C-C;13.1
```
Adding the correct sensor width is crucial in computing the camera intrinsics, such as distortion parameters, object scale, and distances. Otherwise the camera alignment, during feature matching and structure-from-motion steps are likely to fail.

Once these details have been added, launch **Meshroom** and drag your images named *…cutout.tif* into **Meshroom**. If the metadata and added camera sensor are recognised, a **green aperture icon** should be displayed over all images.

![](images/meshroom_correctly_loaded.png)

If not all images are listed, or the aperture icon remains red / yellow, execute the helper script “batch_fix_meta_data.py” to fix any issues resulting from your images' exif files. 

**Setting up the reconstruction pipeline**

*Try to run the pipeline with this configuration, before attempting to use approximated camera positions. Approximate positions should only be used if issues with the alignment of multiple camera poses arise, as fine differences in the scanner setup can cause poorer reconstruction results, without **guided matching** (available only in the **2020 version** of **Meshroom**)!*

1. **CameraInit**

- *No parameters need to be changed here.*
- However, ensure that only one element is listed under **Intrinsics**. If there is more than one, remove all images you imported previously, delete all elements listed under **Intrinsics**, and load your images again. If the issue persists, execute the helper script “batch_fix_meta_data.py” to fix any issues resulting from your images exif files. 

2. **FeatureExtraction**

- Enable Advanced Attributes** by clicking on the three dots at the upper right corner.
- Describer Types: Check **sift** and **akaze**
- Describer Preset: Normal (pick High if your subject has many fine structures)
- Force CPU Extraction: Uncheck

3. **ImageMatching**

- Max Descriptors: 10000
- Nb Matches: 200

4. **FeatureMatching**

- Describer Types: Check **sift** and **akaze**
- Guided Matching: Check

5. **StructureFromMotion**

- Describer Types: Check **sift** and **akaze**
- Local Bundle Adjustment: Check
- Maximum Number of Matches: 0 (ensures all matches are retained)

6. **PrepareDenseScene**

- *No parameters need to be changed here.*

7. **DepthMap**

- Downscale: 1 (use maximum resolution of each image to compute depth maps)

8. **DepthMapFilter**

- Min View Angle: 1
- Compute Normal Maps: Check

9. **Meshing**

- Estimate Space from SfM: Uncheck (while this will potentially produce “floaters” that need to be removed during post processing it assists in reserving very fine / long structures, such as antennae)
- Min Observations for SfM Space Estimation: 2 (only required if above attribute remains checked)
- Min Observations Angle for SfM Space Estimation: 5 (only required if above attribute remains checked)
- Max Input Points: 100000000
- simGaussianSizeInit: 5
- simGaussianSize: 5
- Add landmarks to the Dense Point Cloud: Check	

10. **MeshFiltering**

- Filter Large Triangles Factor: 40
- Smoothing Iterations: 2

11. Texturing

- Texture Side: 16384
- Unwrap Method: **LSCM** (will lead to larger texture files, but much higher surface quality)
- Texture File Type: png
- Fill Holes: Check

Now click on **start** and watch the magic happen. Actually, this is the best time to grab a cup of coffee, as the reconstruction process takes between 3 and 10 hours, depending on your step size, camera resolution, and system specs.

**Exporting the textured mesh:**

All outputs within Meshroom are automatically saved in the project’s environment. By right clicking on the **Texturing node** and choosing “**Open Folder**” the location of the created mesh (**.obj** file) is shown.

## Original paper
Plum F, Labonte D. 2021. scAnt—an open-source platform for the creation of 3D models of arthropods (and other small objects) 
PeerJ 9:e11155 https://doi.org/10.7717/peerj.11155

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
**scAnt** - Open Source 3D Scanner and Processing Pipeline

© Fabian Plum, 2020
[MIT License](https://choosealicense.com/licenses/mit/)
