# GPU worker setup

Windows x64 and Ubuntu x64 use three isolated workers. ZED decodes the source and measures depth, SpatialHub fits the target with FoundationPose, and DeepLabCut trains and evaluates the keypoint model. Playback of prepared projects on macOS uses the desktop installer.

## Prepare the machine

Install the **ZED SDK 5.5.x CUDA 12 variant** for the machine's OS, including its matching CUDA toolkit and neural depth support. Use a supported NVIDIA GPU and the driver recommended for that SDK and toolkit. The pose worker needs an NVIDIA OpenGL 4.3 context. On Ubuntu the driver must also supply EGL for offscreen rendering. Check that `nvidia-smi` recognizes the GPU. [ZED SDK downloads](https://www.stereolabs.com/developers/release/5.5) · [Stereolabs hardware requirements](https://docs.stereolabs.com/docs/development/zed-sdk/specifications)

## Provision the installed app

Open a terminal in the directory containing the installed `skellyclicker-backend` executable. This is the desktop bundle’s `backend` resource directory. For an AppImage, mount it with `--appimage-mount` in another terminal and locate the backend inside the printed mount path. Run these commands as the same user who runs the desktop app.

Windows PowerShell

```powershell
.\skellyclicker-backend.exe --provision-gpu
.\skellyclicker-backend.exe --check-gpu
```

Ubuntu

```bash
./skellyclicker-backend --provision-gpu
./skellyclicker-backend --check-gpu
```

Provisioning uses the bundled uv executable and requires network access to download CPython, hash-locked Python packages, and the two FoundationPose model files at a fixed revision. Allow several GB for both the installed workers and the download cache. The versions include pyzed 5.5, SpatialHub 0.1.7, ONNX Runtime GPU 1.23.2, DeepLabCut 3.0.2 and PyTorch 2.7.1 with CUDA 12.8. The ZED SDK may prepare its NEURAL depth model for the device on first use, and the initial DLC run may fetch pretrained backbone weights. [ZED Python API](https://docs.stereolabs.com/docs/development/api-languages/python) · [FoundationPose models](https://huggingface.co/SpatialHub/foundationpose/tree/7f3c15896eeed50a3f024260543525c6f1d036f4) · [PyTorch CUDA distributions](https://pytorch.org/get-started/previous-versions/)

The setup command creates a fresh generation under `%LOCALAPPDATA%\SkellyClicker\gpu` or `${XDG_DATA_HOME:-~/.local/share}/SkellyClicker/gpu`. Set `SKELLYCLICKER_GPU_HOME` in both the terminal and the app environment to use a different drive. For a custom SDK location set `ZED_SDK_ROOT_DIR`, with its libraries visible to the system loader. Windows also accepts `SKELLYCLICKER_ZED_SDK_BIN` and the toolkit's `CUDA_PATH`.

Setup activates the new generation after verifying the ZED API version, initializing both ONNX model sessions with the CUDA provider and performing a GPU tensor operation with the DLC interpreter. It removes a failed generation; a successful replacement leaves older generations available for running jobs. The app reads the active generation on subsequent requests. Existing training interpreter selections still take precedence where explicitly configured. Run the installed-app reference recording checks to qualify decoding, fitting, training and inference.
