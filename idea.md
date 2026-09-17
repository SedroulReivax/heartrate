# CameraHeart — Project Idea & Design Document

A locally-hosted application that detects your heart rate in real time using nothing but your webcam, powered by rPPG (remote photoplethysmography). No wearables. No contact. Just a camera and some math.

---

## Tech Stack

### Frontend — TypeScript + React
| Tool | Why |
|---|---|
| **React + TypeScript** | Component-based UI, type safety, easy state management |
| **Vite** | Blazing fast local dev server, minimal config |
| **WebSocket (native browser API)** | Real-time bidirectional communication with the Python backend |
| **Canvas API** | Drawing live waveform graphs directly in the browser |
| **TailwindCSS** | Utility-first styling, easy to achieve a monochromatic terminal look |
| **Recharts / custom Canvas** | Animating the live pulse waveform |

### Backend — Python
| Tool | Why |
|---|---|
| **FastAPI** | Async HTTP + native WebSocket support in one framework |
| **OpenCV (`cv2`)** | Face detection, video frame capture from webcam, pixel-level color analysis |
| **MediaPipe** | Accurate, fast facial landmark detection to isolate ROI (forehead, cheeks) |
| **NumPy** | Efficient array math on raw pixel data |
| **SciPy** | Bandpass filtering to isolate heart rate frequency from noise |
| **`asyncio`** | Non-blocking webcam loop that streams data over WebSocket |

---

## How It Works (Data Flow)

```
[Webcam]
   |
   v
[Python / OpenCV]        — captures 30fps video frames from the system webcam
   |
   v
[MediaPipe Face Mesh]    — detects face landmarks, extracts forehead + cheek ROI
   |
   v
[Pixel Color Averaging]  — computes mean R, G, B channel values for ROI per frame
   |
   v
[Signal Buffer]          — accumulates ~10 seconds of color signal data (300 frames)
   |
   v
[Bandpass Filter]        — SciPy Butterworth filter (0.75–3.0 Hz = 45–180 BPM range)
   |
   v
[FFT Analysis]           — Fast Fourier Transform finds the dominant frequency = BPM
   |
   v
[WebSocket Stream]       — FastAPI pushes {bpm, signal[], confidence, stage} to UI
   |
   v
[React UI]               — renders terminal-style live dashboard in the browser
```

---

## What's in the UI

The UI has a strict **monochromatic terminal aesthetic** — think green-on-black, like a retro CRT monitor or a hacker's terminal. Everything is text-driven, with monospaced fonts, blinking cursors, and sharp borders made of ASCII box-drawing characters.

---

### UI Sections (Top to Bottom)

#### 1. Header / Status Bar
```
╔══════════════════════════════════════════════════════════════╗
║  CAMERAHEART v1.0.0          [●] LIVE        18:42:33 IST   ║
╚══════════════════════════════════════════════════════════════╝
```
- App name and version
- Live connection status indicator (blinking dot when active)
- Real-time clock

---

#### 2. Webcam Feed + ROI Overlay
```
╔═══════════════════════════╗
║   CAMERA FEED             ║
║  ┌─────────────────────┐  ║
║  │  [live webcam here] │  ║
║  │   ░░░░░░░░░░░░░░    │  ║  ← forehead ROI box (green outline)
║  │                     │  ║
║  │      ░░░░░░░░       │  ║  ← cheek ROI boxes
║  └─────────────────────┘  ║
║   ROI: FOREHEAD + CHEEKS  ║
╚═══════════════════════════╝
```
- Live webcam stream rendered as a `<video>` or `<canvas>` element in monochrome/green tint
- Overlaid bounding boxes for the regions of interest (forehead, cheeks) drawn by the backend and sent as coordinates to the frontend
- A label explains **what is being watched and why**

> **Explanation displayed in UI:**
> _"Tracking: forehead + upper cheek region. These areas have the highest density of superficial capillaries and produce the strongest rPPG signal. Each heartbeat causes a microsecond flush of blood through these vessels, producing a color change too subtle for the human eye — but not for the camera."_

---

#### 3. Stage Indicator / Pipeline Log
```
╔══════════════════════════════════════════╗
║  PIPELINE STATUS                         ║
║  [✓] Face detected                       ║
║  [✓] ROI locked                          ║
║  [~] Buffering signal...  ████░░░ 68%   ║
║  [ ] Filtering                           ║
║  [ ] FFT Analysis                        ║
║  [ ] BPM Ready                           ║
╚══════════════════════════════════════════╝
```
- Animated checklist showing exactly which stage of the pipeline is active
- A buffer progress bar showing how much signal data has been collected before the first BPM reading (requires ~10 seconds of clean signal)
- Each step has a brief tooltip/explanation explaining **why** that step exists

> **Explanation for each step shown inline:**
> - **Face detected** — _"MediaPipe locates 468 facial landmarks. Without a stable face lock, we have no signal source."_
> - **ROI locked** — _"The forehead and cheek polygon coordinates are extracted. Signal averaging is restricted to these zones to reduce skin-tone noise."_
> - **Buffering signal** — _"We need at least 10 seconds (~300 frames at 30fps) to build a meaningful waveform. A shorter window produces an inaccurate FFT."_
> - **Bandpass filter** — _"A Butterworth filter removes everything below 0.75 Hz (45 BPM) and above 3.0 Hz (180 BPM). This kills lighting flicker, head movement drift, and breathing artifacts."_
> - **FFT Analysis** — _"The Fast Fourier Transform converts our time-domain color signal into a frequency spectrum. The peak frequency in the 0.75–3.0 Hz band is your heart rate."_

---

#### 4. Live Pulse Waveform
```
╔════════════════════════════════════════════════════╗
║  rPPG WAVEFORM — GREEN CHANNEL                     ║
║                                                    ║
║  0.80 ┤         ╭─╮       ╭─╮       ╭──╮          ║
║  0.65 ┤    ╭────╯  ╰───╮──╯  ╰──────╯  ╰──        ║
║  0.50 ┤────╯           ╰╯                          ║
║       └────────────────────────────────────────    ║
║        t-10s           t-5s              now       ║
╚════════════════════════════════════════════════════╝
```
- A scrolling, real-time waveform plotted on an ASCII-style canvas
- Rendered using `<canvas>` with a bright green line on a black background
- Shows the raw green-channel color signal over the last 10 seconds
- Each "peak" in the waveform corresponds to one heartbeat

> **Explanation displayed below the chart:**
> _"This is the raw rPPG signal extracted from the green channel of your facial pixels. Green light is most strongly absorbed by oxyhemoglobin. Each peak corresponds to a cardiac pulse — a momentary increase in blood volume causing a dip in green light reflection."_

---

#### 5. Heart Rate Display
```
╔═══════════════════════════════╗
║   ♥ HEART RATE                ║
║                               ║
║         7 2  B P M            ║
║                               ║
║   Confidence:  ████████░░ 81% ║
║   Signal SNR:  14.3 dB        ║
║   Status:      STABLE         ║
╚═══════════════════════════════╝
```
- The big number — current BPM displayed in large ASCII-style digits
- Confidence score (how clean/strong the extracted signal was)
- Signal-to-noise ratio displayed
- Status: BUFFERING / UNSTABLE / STABLE / LOST

> **Explanation:**
> _"BPM is calculated by identifying the peak frequency in the FFT spectrum of the filtered rPPG signal. Confidence reflects the prominence of that peak relative to surrounding noise. A score below 60% means the signal is too noisy — try better lighting or reduce movement."_

---

#### 6. Frequency Spectrum (FFT Visualization)
```
╔═══════════════════════════════════════════╗
║  FFT SPECTRUM — FREQUENCY DOMAIN          ║
║                                           ║
║  Mag ┤                                   ║
║  1.0 ┤          ██                       ║
║  0.8 ┤         ████                      ║
║  0.6 ┤        ██████                     ║
║  0.4 ┤  ████████████████                 ║
║  0.2 ┤  ████████████████████████         ║
║      └──────┬──────────┬────────         ║
║           0.75Hz     3.0Hz              ║
║             ↑ valid HR range ↑           ║
╚═══════════════════════════════════════════╝
```
- Bar chart showing the FFT magnitude spectrum
- Highlighted band shows the valid heart rate range (0.75–3.0 Hz)
- The tallest bar in that band = the detected heart rate

> **Explanation:**
> _"The FFT decomposes the rPPG waveform into its constituent frequencies. The x-axis is frequency (Hz), the y-axis is magnitude (signal strength). The highest peak within the valid heart rate window (0.75–3.0 Hz) is identified as your heart rate frequency. 1.2 Hz = 72 BPM."_

---

#### 7. Terminal Log
```
╔═══════════════════════════════════════════════════════════╗
║  SYSTEM LOG                                               ║
║  > [18:42:10] WebSocket connected to ws://localhost:8000  ║
║  > [18:42:11] Backend: MediaPipe initialized              ║
║  > [18:42:11] Backend: Webcam opened (device 0, 30fps)   ║
║  > [18:42:12] Face detected. ROI locked.                  ║
║  > [18:42:22] Signal buffer full. First BPM computed.     ║
║  > [18:42:22] BPM: 72 | Confidence: 81% | SNR: 14.3dB    ║
║  > [18:42:23] BPM: 73 | Confidence: 79% | SNR: 13.8dB    ║
║  > _                                                      ║
╚═══════════════════════════════════════════════════════════╝
```
- Scrolling terminal-style log of real-time events
- Blinking cursor at the end
- Gives developers and curious users a raw view of what's happening inside the pipeline

---

## Color Palette (Monochromatic Terminal Theme)

| Element | Color |
|---|---|
| Background | `#0a0a0a` (near black) |
| Primary text / waveform | `#00ff41` (classic terminal green) |
| Dim / secondary text | `#005c18` (dark muted green) |
| Borders / box characters | `#1a4a1a` |
| Highlight / BPM number | `#39ff14` (neon green) |
| Warning / unstable state | `#ffff00` (amber — only non-green color) |
| Error / lost state | `#ff0000` (red — only for critical loss) |
| Font | `JetBrains Mono`, `Fira Code`, or `Courier New` |

---

## Local Setup Flow

```
git clone ...
cd cameraheart

# Backend
cd backend
pip install -r requirements.txt
python main.py          # starts FastAPI on ws://localhost:8000

# Frontend
cd frontend
npm install
npm run dev             # starts Vite on http://localhost:5173
```

Browser opens → webcam permission granted → pipeline starts → BPM appears within ~10 seconds.

---

## Project Folder Structure

```
cameraheart/
├── backend/
│   ├── main.py              # FastAPI app, WebSocket endpoint
│   ├── capture.py           # OpenCV webcam capture loop
│   ├── roi.py               # MediaPipe face mesh + ROI extraction
│   ├── signal_processor.py  # Bandpass filter + FFT + BPM calculation
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── CameraFeed.tsx       # webcam + ROI overlay
│   │   │   ├── PipelineStatus.tsx   # stage checklist
│   │   │   ├── Waveform.tsx         # live scrolling pulse chart
│   │   │   ├── HeartRateDisplay.tsx # big BPM number
│   │   │   ├── FFTSpectrum.tsx      # frequency bar chart
│   │   │   └── TerminalLog.tsx      # scrolling event log
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts      # WebSocket connection + state
│   │   └── types.ts                 # shared TypeScript types
│   ├── index.html
│   ├── vite.config.ts
│   └── tailwind.config.ts
│
├── basic_idea.md
└── idea.md
```

---

## Why This Is Interesting

This project sits at the intersection of **computer vision**, **signal processing**, and **real-time web technology**. It demonstrates that your phone or laptop camera already contains enough information to measure your vitals — your heart is silently painting your face with a color you can't see, and we're building the software to see it.

> **This is not a medical device.** Results are for educational and experimentation purposes only.
