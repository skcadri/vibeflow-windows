# 🎙️ VibeFlow — Windows Voice Dictation

<img width="420" height="111" alt="image" src="https://github.com/user-attachments/assets/3b10fa7e-f3a5-4abc-ac25-c0e48b8eaf9d" />

A fast, local, **Windows** voice-dictation app (a Wispr Flow–style tool). Hold a
hotkey, talk, and your words are transcribed on-device and pasted at your cursor
in any application. Speech-to-text runs **fully offline** using
[Parakeet-TDT v2 (ONNX)](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx),
with a glassmorphic floating waveform while you speak.

> ℹ️ This is the **Windows** edition (Python + PyQt6). A separate native macOS
> rewrite lives on other branches.

---

## 🤖 Install it with your AI agent (easiest)

Paste the block below to an AI coding agent (Claude Code, Cursor, Copilot, etc.)
on the **Windows PC** you want to install it on. It will set everything up and
then tell you how to use it.

```text
Please install "VibeFlow", a Windows voice-dictation app, from
https://github.com/skcadri/vibeflow — and when done, explain how I use it.

Steps:
1. Clone the repo to C:\Users\<me>\vibeflow (or use it if already cloned).
2. From the repo root, create a Python 3.10+ virtual environment named "venv":
       python -m venv venv
3. Install dependencies:
       venv\Scripts\python -m pip install --upgrade pip
       venv\Scripts\python -m pip install -r requirements.txt
4. Do a first run to download the speech model (~2.4 GB, one time only). Run it
   from the src folder so the package resolves:
       cd src
       ..\venv\Scripts\python -m medasr
   Wait until the log says "Parakeet-TDT ready!", then it's installed. It runs
   in the system tray (no main window).
5. Make it easy to launch: create a Desktop shortcut AND a Startup-folder entry
   that both run the windowless launcher, so it auto-starts to the tray at login:
       Target:  wscript.exe "C:\Users\<me>\vibeflow\VibeFlow.vbs"
   (Startup folder: shell:startup)
6. Finally, tell me how to use it: press and hold Ctrl+Win, speak, release to
   paste at the cursor; Esc cancels; double-click the tray icon for settings.

Notes: it's a GPU/CPU ONNX app — no separate CUDA/PyTorch install is needed.
The model downloads to the HuggingFace cache on first run. If onnxruntime-gpu
fails on a machine with no NVIDIA GPU, install "onnx-asr[hub]" instead.
```

---

## ✨ Features

- **Global hotkey** — hold `Ctrl+Win`, speak, release to paste at the cursor
- **100% local & offline** — Parakeet-TDT v2 via ONNX Runtime (GPU or CPU)
- **Glassmorphic overlay** — a frosted pill with a live Siri-style waveform
- **Pastes anywhere** — clipboard paste works in any app (Word, browsers, chat…)
- **History** — every transcript saved to a local SQLite database
- **Custom vocabulary** — bias recognition toward names / domain terms
- **Optional AI formatting** — local LLM cleanup (paragraphs, lists) — off by default
- **System tray** — model switching, CPU/GPU toggle, and settings

## 🖐️ Usage

1. The app lives in the **system tray** (no main window).
2. Put your cursor in any text field.
3. **Press and hold `Ctrl+Win`** — the glass waveform appears — and speak.
4. **Release** to transcribe and paste at the cursor.
5. Press **`Esc`** while recording to cancel.
6. **Double-click the tray icon** for Settings (model, CPU/GPU, vocabulary, history, formatting).

## 🛠️ Manual install

```powershell
# From the repo root
python -m venv venv
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt

# First run (downloads the ~2.4 GB model once), from the src folder
cd src
..\venv\Scripts\python -m medasr
```

Then just double-click **`VibeFlow.vbs`** to launch silently to the tray. To
auto-start at login, drop a shortcut to `VibeFlow.vbs` into your Startup folder
(`Win+R` → `shell:startup`).

> The launchers (`VibeFlow.bat` / `VibeFlow.vbs`) are path-independent and expect
> a `venv` in the repo root.

## 📦 Requirements

- Windows 10 / 11
- Python 3.10+
- ~2.4 GB disk for the speech model (cached in your HuggingFace folder)
- Optional: an NVIDIA GPU (CUDA) for faster transcription — CPU works fine too

## ⚙️ Configuration

Edit `config/settings.yaml` for hotkey, audio, and UI options, or use the
in-app Settings window (double-click the tray icon).

## 📁 Project layout

```
vibeflow/
├── VibeFlow.bat / VibeFlow.vbs   # launchers (silent → tray)
├── requirements.txt
├── config/settings.yaml          # configuration
└── src/medasr/                   # application package
    ├── __main__.py               # entry point  (python -m medasr)
    ├── app.py                    # controller / state machine
    ├── audio/  input/  transcription/  postprocessing/
    └── ui/                       # tray, settings, glass overlay (assets/overlay.html)
```

## 📝 License

GPL-3.0
