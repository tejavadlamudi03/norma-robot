# NormaCore

> **🏆 Hackathon submission (Berlin AI × Robotics).** This fork adds **[`claude-supervisor/`](claude-supervisor/)** — an LLM (Claude) that drives the ElRobot arm for a real pick-and-place and supervises the SmolVLA policy, preempting it with direct joint commands when it fails. See **[claude-supervisor/README.md](claude-supervisor/README.md)** for the architecture.

### The Unified Toolkit for Physical System Development & Operations

**NormaCore** is a unified toolkit designed to facilitate the development and deployment of physical systems. From complex robotics to distributed sensor networks and hobby projects, the system provides a solid foundation to manage them all. To achieve this goal, the platform combines a unified API, high-performance data pipelines, and visual tooling to help you build and manage your entire ecosystem as one.

**Developer experience sits at the heart of our design philosophy.**

To fully realize the potential of this approach, we had to build a lot from scratch, rethinking traditional solutions from a practical perspective. This includes not just software, but complete hardware systems like our **7+1 DoF robotic arm** with a **parallel jaw gripper** - tools designed to open up a whole new dimension of applications for home and research robotics without significant cost or investment.

## What's inside

| Project | Path | Description |
|---|---|---|
| **ElRobot** | [`hardware/elrobot/`](hardware/elrobot/) | Fully 3D-printed 7+1 DoF robotic arm for imitation learning |
| **Parallel Jaw Gripper** | [`hardware/pgripper/`](hardware/pgripper/) | Modular gripper for the SO-101 arm |
| **Station** | [`software/station/bin/station/`](software/station/bin/station/) | Real-time robotics platform — data collection, inference, control. Single binary, web UI |
| **SmolVLA fine-tune** | [`software/ai/smolvla_py/`](software/ai/smolvla_py/) | Train + deploy a [SmolVLA](https://huggingface.co/docs/lerobot/smolvla) policy on the SO-101 arm |
| **Gremlin** | [`shared/gremlin_go/`](shared/gremlin_go/) · [`shared/gremlin_py/`](shared/gremlin_py/) | High-performance Protobuf SDK for Go and Python — used across the station + drivers stack |
| **🏆 Claude Supervisor** | [`claude-supervisor/`](claude-supervisor/) | **Hackathon:** an LLM (Claude) controlling the ElRobot arm — pick-and-place + supervising/preempting the SmolVLA policy |
| **Color Sorting & Gesture Q&A** | [`software/station/examples/`](software/station/examples/) | Robot that sorts colored caps and answers questions with physical gestures |

**Website:** [normacore.dev](https://normacore.dev)

**Follow us:**
- 🐦 [X/Twitter](https://x.com/norma_core_dev)
- 🎥 [YouTube](https://www.youtube.com/@normacoredev)
- 💼 [LinkedIn](https://www.linkedin.com/company/normacore/)
- 📢 [Reddit](https://www.reddit.com/r/NormaCore/)

**Join & Contribute:**
- 💬 [Discord](https://discord.gg/Z4Ytw3QfHP) - Chat with the community
- 🐙 [GitHub](https://github.com/norma-core/norma-core) - Source code & issues

---

# Norma Robot — Color Sorting & Gesture Q&A

A physical robot arm that:
- **Sorts colored caps** (red → right, blue → left, other → forward) using camera + AWS Bedrock Claude for color detection and SmolVLA for motion
- **Answers questions with gestures** (yes / no / laugh) using voice input (Whisper) + Claude for reasoning + SmolVLA for motion

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Hardware & Software Requirements](#hardware--software-requirements)
- [Environment Setup](#environment-setup)
- [Project Structure](#project-structure)
- [Color Sorting Robot](#color-sorting-robot)
- [Gesture Q&A Oracle](#gesture-qa-oracle)
- [Training Guide](#training-guide)
- [Troubleshooting](#troubleshooting)

---

## System Architecture

```mermaid
graph TD
    subgraph Hardware
        CAM0[Camera 0\n10 fps · ~19 KB/frame]
        CAM1[Camera 1\n10 fps · ~13 KB/frame]
        ARM[Robot Arm\n8 × ST3215 Servo Motors]
    end

    subgraph NormaCore Station
        STN["./station --web --tcp\nlocalhost:8889 web UI\nlocalhost:8888 TCP API"]
        QUEUE[inference/normvla\nframe queue\njoints + images]
    end

    subgraph AI Pipeline
        VLA[SmolVLA Policy\nfine-tuned on demonstrations]
        STATS[stats.safetensors\nnormalization mean / std]
        CHUNK["Action Chunk\n25-step temporal smoothing\nreplan_every=25 ticks"]
    end

    subgraph Language Understanding
        WHISPER[Whisper STT\nvoice → text]
        BEDROCK[AWS Bedrock\nClaude Haiku]
    end

    CAM0 -->|JPEG stream| STN
    CAM1 -->|JPEG stream| STN
    ARM -->|joint positions norm| STN
    STN --> QUEUE
    QUEUE -->|observation batch| VLA
    STATS -->|normalize / unnormalize| VLA
    VLA --> CHUNK
    CHUNK -->|SyncWrite commands| ARM
    WHISPER -->|transcript| BEDROCK
    BEDROCK -->|color / gesture decision| VLA
```

---

## Hardware & Software Requirements

### Hardware
| Component | Detail |
|---|---|
| Robot arm | NormaCore with 8 × ST3215 servos |
| Bus serial | `5B61034836` (right / orange arm) |
| Motor IDs | `1, 2, 3, 4, 5, 6, 7, 8` |
| Cameras | 2 × USB cameras at 10.1 fps |
| GPU | NVIDIA RTX 4060 8 GB (or equivalent CUDA GPU) |
| Microphone | Any USB or built-in mic for voice input |

### Software
| Package | Purpose |
|---|---|
| Python 3.10 | Runtime |
| PyTorch 2.x + CUDA | Model inference & training |
| SmolVLA | VLA policy (`software/ai/smolvla_py`) |
| boto3 | AWS Bedrock Claude API |
| openai-whisper | Speech-to-text |
| sounddevice | Microphone recording |
| Pillow | Image processing |
| uv | Fast Python package manager |

---

## Environment Setup

### 1. Start NormaCore Station

```bash
# In a dedicated terminal — keep running the whole time
./station --web --tcp
```

Serves:
- `http://localhost:8889` — web UI for manual arm control & recording
- `tcp://localhost:8888` — Python client API

### 2. AWS Credentials (for Bedrock Claude)

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

Model used: `us.anthropic.claude-haiku-4-5-20251001-v1:0`
> Must use the `us.` cross-region inference profile prefix — plain model IDs fail with on-demand throughput.

### 3. Install Dependencies

```bash
cd software/ai/smolvla_py
uv sync
```

---

## Project Structure

```
software/station/examples/
├── color-sorting/
│   └── color_sort.py        # Color sorting robot (main script)
├── gesture/
│   ├── gesture_test.py      # Test gestures by typing yes/no/laugh
│   ├── oracle.py            # Q&A oracle — voice + text input → gesture
│   ├── oracle_simple.py     # Lightweight HTTP server for iPhone browser
│   └── oracle_web.py        # HTTPS server with MediaRecorder voice
└── read_tags.py             # Extract episode tags from station recording

software/ai/smolvla_py/
├── scripts/
│   └── train.py             # Fine-tune SmolVLA on demonstration data
├── smolvla/                 # Model architecture
└── checkpoints/             # Saved checkpoints (gitignored — too large)
    ├── color-sort-v3/final/
    └── yes-no-laugh-v2/final/
```

---

## Color Sorting Robot

### How It Works

```mermaid
flowchart TD
    START([Loop starts]) --> GRAB[Fetch latest frame from cam0]
    GRAB --> CROP["Center-crop image\n⅓ width × ⅓ height\nfocuses on cap area"]
    CROP --> CLAUDE{"AWS Bedrock Claude\nWhat color is this cap?\nwarm yellow lighting context"}
    CLAUDE -->|red| TR["task = 'push the cap to the right'"]
    CLAUDE -->|blue| TB["task = 'push the cap to the left'"]
    CLAUDE -->|other| TO["task = 'push the cap forward'"]
    TR & TB & TO --> HOME["go_home()\n30-step smooth interpolation\nat 20 Hz"]
    HOME --> PREDICT["SmolVLA.predict_action_chunk()\nobservation: state + cam0 + cam1 + task"]
    PREDICT --> EXEC["Execute chunk position by position\ntick by tick at 10 fps"]
    EXEC --> REPLAN{"chunk_pos ≥ replan_every\n(25 ticks)?"}
    REPLAN -->|yes| PREDICT
    REPLAN -->|no| NEXTTICK[Next tick]
    NEXTTICK --> DONE{"exec_ticks\ncomplete?\n~150 ticks = 15 sec"}
    DONE -->|no| EXEC
    DONE -->|yes| HOME2["Return to home\nLoop again"]
    HOME2 --> GRAB
```

**Color → task string mapping:**

| Detected color | Task string |
|---|---|
| Red | `push the cap to the right` |
| Blue | `push the cap to the left` |
| Other / none | `push the cap forward` |

**Home position (normalized, 8 joints):**
```python
HOME_POSITION_NORM = [0.51, 0.02, 0.43, 0.98, 0.47, 0.65, 0.54, 0.04]
```
> Derived from the mean of the first frame of each training episode.

---

### Recording a Dataset (Color Sort)

1. Open station web UI at `http://localhost:8889`
2. Manually drive arm to push a red cap to the right — tag the episode `red_start` / `red_stop`
3. Repeat for blue (`blue_start` / `blue_stop`) and other (`other_start` / `other_stop`)
4. Aim for **30+ episodes per color**

Generate parquet files:

```bash
cd software/station/examples

# Red cap
uv run python read_tags.py
# Follow the printed commands, e.g.:
uv run python ../../ai/smolvla_py/scripts/generate_dataset.py \
  --tag-start red_start --tag-stop red_stop \
  --task "push the cap to the right" \
  --episode-duration 45 \
  --output ../../../datasets/dataset_red

# Blue cap
uv run python ../../ai/smolvla_py/scripts/generate_dataset.py \
  --tag-start blue_start --tag-stop blue_stop \
  --task "push the cap to the left" \
  --episode-duration 45 \
  --output ../../../datasets/dataset_blue

# Other cap
uv run python ../../ai/smolvla_py/scripts/generate_dataset.py \
  --tag-start other_start --tag-stop other_stop \
  --task "push the cap forward" \
  --episode-duration 45 \
  --output ../../../datasets/dataset_other
```

---

### Training (Color Sort)

```mermaid
graph LR
    D1[dataset_red.parquet] --> T
    D2[dataset_blue.parquet] --> T
    D3[dataset_other.parquet] --> T
    D4[dataset_other_caps.parquet] --> T
    T["train.py\n5000 steps · batch 16\n~2.5 hours on RTX 4060"] --> CK[checkpoints/color-sort-v3/final/]
```

```bash
cd software/ai/smolvla_py

uv run python scripts/train.py \
  --parquets \
    ../../../datasets/dataset_red.parquet \
    ../../../datasets/dataset_blue.parquet \
    ../../../datasets/dataset_other.parquet \
    ../../../datasets/dataset_other_caps.parquet \
  --steps 5000 \
  --batch-size 16 \
  --lr 1e-4 \
  --warmup-steps 500 \
  --decay-steps 15000 \
  --decay-lr 2.5e-6 \
  --weight-decay 1e-4 \
  --grad-clip 10.0 \
  --output checkpoints/color-sort-v3
```

---

### Running (Color Sort)

```bash
cd software/ai/smolvla_py

uv run python ../../station/examples/color-sorting/color_sort.py \
  --checkpoint checkpoints/color-sort-v3/final \
  --bus-serial 5B61034836 \
  --task-style push \
  --camera-index 2 \
  --obs-cameras 0,2 \
  --exec-ticks 150 \
  --max-delta-ticks 0
```

**Flags:**

| Flag | Default | Description |
|---|---|---|
| `--checkpoint` | required | Path to `final/` checkpoint folder |
| `--bus-serial` | required | `5B61034836` |
| `--task-style` | `push` | `push` for v2/v3, `pickup` for old checkpoints |
| `--camera-index` | `2` | Camera used for color detection (overhead) |
| `--obs-cameras` | `0,2` | Physical camera indices → model cam0, cam1 |
| `--exec-ticks` | 150 | Ticks per push (~15 sec at 10 fps) |
| `--max-delta-ticks` | 0 | Safety cutoff — 0 disables |

**Terminal output:**
```
[Claude cam2] raw='red' → detected: RED
[predict] current=[0.51 0.02 ...] chunk[0]=[0.52 0.03 ...] chunk[-1]=[0.62 0.37 ...]
```

Press `Ctrl+C` → robot smoothly returns to home.

---

## Gesture Q&A Oracle

### How It Works

```mermaid
flowchart TD
    INPUT([Waiting for input]) --> CHOICE{"Input mode"}
    CHOICE -->|"Press Enter\n(empty line)"| MIC["🎤 Record microphone\nfor 4 seconds\nWhisper transcribes"]
    CHOICE -->|Type question| TYPED[Typed text]
    MIC --> Q[Question string]
    TYPED --> Q

    Q --> CLAUDE2{"AWS Bedrock Claude\nAnalyze question"}

    CLAUDE2 -->|"Yes/no question\nMath: 2+2=4?\nGeneral knowledge"| YN["gesture = yes or no\nbased on correct answer"]
    CLAUDE2 -->|"Funny / joke\nSay laugh / lol\nAbsurd statement"| LA[gesture = laugh]

    YN & LA --> REPLY[Print Claude reply to terminal]
    REPLY --> HOME3["go_home()\nSmooth 30-step transition"]
    HOME3 --> REP1["Perform gesture × rep 1\n60 ticks"]
    REP1 --> REP2["Perform gesture × rep 2\nno home between reps"]
    REP2 --> HOME4[Return to home]
    HOME4 --> INPUT
```

**Gesture → task string mapping:**

| Gesture | Task string |
|---|---|
| Yes | `nod yes` |
| No | `shake no` |
| Laugh | `laugh` |

**Home position for gestures:**
```python
GESTURE_HOME = [0.484, 0.036, 0.452, 0.965, 0.500, 0.627, 0.496, 0.964]
```

---

### Recording a Dataset (Gesture)

1. Open station web UI at `http://localhost:8889`
2. Record nodding yes motion — tag `yes_start` / `yes_stop`
3. Record shaking no motion — tag `no_start` / `no_stop`
4. Record laugh/wobble motion — tag `laugh_start` / `laugh_stop`
5. Aim for **30+ episodes per gesture** (min 20 for laugh)

Generate parquets:

```bash
cd software/station/examples

uv run python ../../ai/smolvla_py/scripts/generate_dataset.py \
  --tag-start yes_start --tag-stop yes_stop \
  --task "nod yes" \
  --episode-duration 10 \
  --output ../../../datasets/dataset_yes

uv run python ../../ai/smolvla_py/scripts/generate_dataset.py \
  --tag-start no_start --tag-stop no_stop \
  --task "shake no" \
  --episode-duration 10 \
  --output ../../../datasets/dataset_no

uv run python ../../ai/smolvla_py/scripts/generate_dataset.py \
  --tag-start laugh_start --tag-stop laugh_stop \
  --task "laugh" \
  --episode-duration 10 \
  --output ../../../datasets/dataset_laugh
```

---

### Training (Gesture)

```mermaid
graph LR
    G1[dataset_yes.parquet] --> GT
    G2[dataset_no.parquet] --> GT
    G3[dataset_laugh.parquet] --> GT
    GT["train.py\n5000 steps · batch 16\n~2.5 hours on RTX 4060"] --> GCK[checkpoints/yes-no-laugh-v2/final/]
```

```bash
cd software/ai/smolvla_py

uv run python scripts/train.py \
  --parquets \
    ../../../datasets/dataset_yes.parquet \
    ../../../datasets/dataset_no.parquet \
    ../../../datasets/dataset_laugh.parquet \
  --steps 5000 \
  --batch-size 16 \
  --lr 1e-4 \
  --warmup-steps 500 \
  --decay-steps 15000 \
  --decay-lr 2.5e-6 \
  --weight-decay 1e-4 \
  --grad-clip 10.0 \
  --output checkpoints/yes-no-laugh-v2
```

---

### Running (Gesture)

```bash
cd software/ai/smolvla_py

uv run python ../../station/examples/gesture/oracle.py \
  --checkpoint checkpoints/yes-no-laugh/final \
  --bus-serial 5B61034836 \
  --exec-ticks 100 \
  --max-delta-ticks 0
```

```
=== Robot Oracle ===
  • Press Enter (empty) → speak your question
  • Type a question    → press Enter to send
  • Type 'quit'        → exit

You (type or Enter to speak): Is the sky blue?
  Thinking ...
  Robot: Yes, the sky appears blue due to Rayleigh scattering.
  Gesture: YES × 2
```

**All oracle.py flags:**

| Flag | Default | Description |
|---|---|---|
| `--checkpoint` | required | Path to `final/` checkpoint |
| `--bus-serial` | required | `5B61034836` |
| `--exec-ticks` | 100 | Ticks per gesture rep |
| `--max-delta-ticks` | 0 | Safety limit — 0 disables |
| `--whisper-model` | `base` | `tiny` fastest · `medium` most accurate |
| `--record-seconds` | 4.0 | Mic recording duration in seconds |
| `--claude-model` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model ID |

---

## Training Guide

### Episode count recommendations

| Class | Minimum | Recommended | Notes |
|---|---|---|---|
| Red | 20 | 30+ | Consistent cap placement |
| Blue | 20 | 30+ | Consistent cap placement |
| Other | 20 | 30+ | Use different colored caps |
| Yes | 20 | 30+ | Same speed every episode |
| No | 20 | 30+ | Same speed every episode |
| Laugh | 20 | 30+ | Most difficult — needs most data |

### Tips for clean data

1. **Always start from home** — move arm to exact home pose, hold still 3 sec before tagging start
2. **Consistent lighting** — record and run under same lights
3. **Smooth motions** — no pauses mid-gesture
4. **Place caps at same spot** — mark position on table with tape
5. **Short clean episodes** — 45 sec for sorting, 10 sec for gestures

### Training time on RTX 4060

| Batch size | Steps | Time | VRAM |
|---|---|---|---|
| 8 | 5000 | ~1.6 hr | ~3.7 GB |
| 16 | 5000 | ~2.5 hr | ~5.5 GB |
| 16 | 8000 | ~4.0 hr | ~5.5 GB |

### Loss targets

| Loss | Meaning |
|---|---|
| > 0.25 | Poor — need more data or steps |
| 0.17–0.25 | Acceptable |
| < 0.17 | Good |
| < 0.12 | Excellent |

---

## Troubleshooting

### Robot not moving at all (`sent=0 aborted=N`)
```bash
--max-delta-ticks 0   # disable safety limit
```

### Robot misses the cap
- Place cap at exactly the same position as during recording
- Check `--task-style push` matches your checkpoint
- Increase `--exec-ticks 200` to give more time

### Claude detects wrong color
Check terminal: `[Claude cam2] raw='...' → detected: ...`
- Ensure warm yellow light doesn't shift colors
- Improve: add more variation in dataset

### AWS ValidationException
Use `us.` prefix on model ID:
```
us.anthropic.claude-haiku-4-5-20251001-v1:0    ✅
anthropic.claude-haiku-4-5-20251001-v1:0        ❌
```

---

## Hardware Info Reference

| Property | Value |
|---|---|
| Camera FPS | 10.1 fps |
| cam0 avg JPEG size | 19 KB |
| cam1 avg JPEG size | 13 KB |
| Motor protocol | ST3215 SyncWrite |
| Target position register | `0x2A` |
| Action / State dimensions | 8 |
| Bus serial | `5B61034836` |