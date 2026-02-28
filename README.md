# AI Security Camera System

An intelligent, camera-based monitoring platform that integrates computer-vision
AI to analyse human behaviour, track attendance, detect anomalies, and
immediately notify administrators of suspicious activity — suitable for
**schools**, **commercial centres**, **workplaces**, and **shops**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 👁️ **Real-time detection** | YOLOv8-powered detection of people, animals, vehicles, and objects |
| 🧠 **Behaviour analysis** | Classifies studying, working, loitering, running, fighting, theft attempts |
| 😊 **Emotion recognition** | DeepFace-based emotion analysis (angry, fear, happy, sad, …) |
| 🚨 **Instant admin alerts** | Email (SMTP/TLS) + webhook (Slack/Teams) with deduplication & cooldown |
| 🧑‍🤝‍🧑 **Face recognition roll-call** | Automatic check-in/check-out via `face_recognition` |
| ⏱️ **Time tracking** | Logs exact arrival and departure times, computes duration and status (late/early leave) |
| 🐾 **Anomaly detection** | Flags animals, unattended objects, vehicles in wrong zones |
| 💾 **Persistent storage** | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy ORM |
| 📊 **Admin dashboard** | Colour-coded real-time terminal UI |
| 🏫 **Multi-venue support** | School, commercial centre, workplace — configurable zone allow-lists |

---

## 🏗️ Project Structure

```
.
├── main.py                        # Entry point
├── requirements.txt               # Python dependencies
├── config/
│   └── settings.py                # All configuration (env-var overridable)
├── src/
│   ├── pipeline.py                # Central processing pipeline
│   ├── camera/
│   │   └── camera_manager.py      # Multi-camera thread management
│   ├── detection/
│   │   ├── person_detector.py     # YOLOv8 detection (people, animals, objects)
│   │   ├── behaviour_analyser.py  # Activity + suspicion scoring
│   │   ├── emotion_analyser.py    # DeepFace emotion recognition
│   │   └── anomaly_detector.py    # Non-human / out-of-zone anomalies
│   ├── attendance/
│   │   ├── roll_call.py           # Face-recognition identity matching
│   │   └── time_tracker.py        # Check-in / check-out / status
│   ├── alerts/
│   │   └── alert_manager.py       # Email + webhook alert dispatch
│   ├── database/
│   │   └── db_manager.py          # SQLAlchemy ORM models + session
│   └── dashboard/
│       └── admin_dashboard.py     # Terminal UI dashboard
└── tests/
    ├── test_behaviour_analyser.py
    ├── test_attendance.py
    ├── test_alert_manager.py
    ├── test_anomaly_detector.py
    └── test_database.py
```

---

## 🚀 Quick Start

### 0. Prerequisites

- **Python 3.10+** (see `.python-version`)
- **pip** or **conda** package manager
- For face recognition: CMake and build tools (Windows/Linux/macOS)
  - **Windows**: Install Visual Studio Build Tools or MinGW
  - **Linux**: `sudo apt-get install cmake libsm6 libxext6`
  - **macOS**: Install Xcode Command Line Tools: `xcode-select --install`

### 1. Clone & Setup Environment

```bash
# Clone the repository
git clone https://github.com/mugire-can/ai-security-system.git
cd ai-security-system

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### 2. Install Dependencies

**Option A: Full Installation (Recommended)**
```bash
pip install -r requirements.txt
```

**Option B: Minimal Installation**
```bash
# Detection only (no face recognition, emotion analysis)
pip install opencv-python ultralytics numpy pydantic
```

**Option C: Development Setup**
```bash
pip install -r requirements.txt
pip install black flake8 mypy isort  # Code quality tools
```

> ⚠️ **Heavy ML packages** (PyTorch, DeepFace, face-recognition with dlib) can take 
> 10-30 minutes to install depending on your system. Consider using pre-built wheels
> or GPU-optimized packages if available.

### 3. Add Known Faces (Optional - For Attendance/Roll-Call)

```
data/known_faces/
  Alice Smith/
    photo1.jpg
    photo2.jpg
  Bob Jones/
    photo.jpg
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
VENUE_TYPE=school        # school | commercial | workplace
VENUE_NAME="Central High School"
ADMIN_EMAIL=admin@school.edu
SMTP_HOST=smtp.gmail.com
SMTP_USER=alerts@school.edu
SMTP_PASSWORD=your-app-password
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...
DATABASE_URL=sqlite:///data/security_system.db
```

### 5. Run the System

**Demo Mode** (no real camera needed)
```bash
python main.py --demo
```

**Real Camera** (webcam index 0)
```bash
python main.py --camera-source 0 --venue-name "My School"
```

**IP Camera / RTSP Stream**
```bash
python main.py --camera-source "rtsp://admin:pass@192.168.1.50:554/stream"
```

**Video File** (for testing/debugging)
```bash
python main.py --camera-source /path/to/video.mp4
```

**With Debug Output**
```bash
python main.py --demo --debug
```

### 6. Run Tests

```bash
# All tests
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ -v --cov=src --cov-report=html

# Specific test file
python -m pytest tests/test_behaviour_analyser.py -v
```

---

## 📋 System Requirements

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **Python** | 3.10 - 3.14 | See `.python-version` |
| **RAM** | 8GB+ | 16GB+ recommended for ML models |
| **Disk** | 10GB+ | For PyTorch and models |
| **Camera** | Webcam or RTSP | USB, IP, RTSP supported |
| **GPU** | Optional | NVIDIA CUDA 12.1+ for acceleration |

---

## 🔧 Configuration Reference

All settings live in `config/settings.py` and can be overridden with
environment variables.

| Setting | Env var | Default | Description |
|---|---|---|---|
| Venue type | `VENUE_TYPE` | `school` | school / commercial / workplace |
| YOLO model | `YOLO_MODEL` | `yolov8n.pt` | Model weights path or HF name |
| Admin email | `ADMIN_EMAIL` | — | Recipient for alert emails |
| Alert cooldown | — | 60 s | Minimum seconds between identical alerts |
| Loitering threshold | — | 120 s | Dwell time that triggers a loitering alert |
| Face tolerance | — | 0.5 | Lower = stricter face matching |
| Work start | `WORK_START_TIME` | `08:00` | Expected check-in time |
| Work end | `WORK_END_TIME` | `18:00` | Expected check-out time |
| Database URL | `DATABASE_URL` | `sqlite:///data/security_system.db` | SQLAlchemy URL |

---

## 🏷️ Supported Alert Types

| Alert type | Trigger |
|---|---|
| `suspicious_behaviour` | Behaviour with suspicion score ≥ 65 % |
| `loitering` | Stationary in an area for > 2 minutes |
| `fighting` | Two people in close proximity with rapid movement |
| `theft_attempt` | Detected reaching toward foreign objects |
| `running` | Person running at high speed |
| `intrusion` | Person in a restricted zone |
| `anomaly` | Animal, unattended bag, vehicle in pedestrian zone |
| `unattended_object` | Bag/package left alone for > 3 minutes |

---

## 🧪 Running Tests

```bash
# All tests with verbose output
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
python -m pytest tests/test_behaviour_analyser.py -v
```

**Expected output**: All core tests pass. Coverage target: >80% for src/

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- PR process.

### Quick contribution checklist:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure tests pass (`pytest tests/ -v`)
5. Commit with clear messages
6. Push and open a Pull Request.

---

## 🔒 Security & Privacy Notes

* **No video is stored by default** — only snapshots triggered by alerts.
* Face encodings are stored only locally; nothing is sent to the cloud.
* SMTP credentials must be provided via environment variables — never hardcoded in source.
* The system is designed to comply with GDPR "privacy by design" principles.
* For security concerns, please email instead of opening public issues.

---

## 📊 Project Status

- **Status**: Alpha (0.1.0)
- **Python**: 3.10 - 3.14
- **CI/CD**: GitHub Actions (tests on push/PR)
- **Coverage**: See [Codecov](https://codecov.io)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/mugire-can/ai-security-system/issues)
- **Discussions**: [GitHub Discussions](https://github.com/mugire-can/ai-security-system/discussions)
- **Documentation**: See README sections above
