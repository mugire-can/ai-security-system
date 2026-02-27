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

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> Heavy ML packages (PyTorch, DeepFace, face-recognition/dlib) are listed in
> `requirements.txt`. Install only what you need:
> * **Detection only**: `pip install ultralytics numpy opencv-python`
> * **Emotion analysis**: add `deepface`
> * **Face recognition**: add `face-recognition` (requires dlib / CMake)
> * **Alerts + database**: add `SQLAlchemy python-dotenv`

### 2. Add known faces (for roll-call / attendance)

```
data/known_faces/
  Alice Smith/
    photo1.jpg
    photo2.jpg
  Bob Jones/
    photo.jpg
```

### 3. Configure the system

Copy `.env.example` to `.env` and fill in your values:

```bash
VENUE_TYPE=school        # school | commercial | workplace
VENUE_NAME="Central High School"
KNOWN_FACES_DIR=data/known_faces
ADMIN_EMAIL=admin@school.edu
SMTP_HOST=smtp.gmail.com
SMTP_USER=alerts@school.edu
SMTP_PASSWORD=your-app-password
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...
```

### 4. Run

```bash
# Demo mode (no real camera needed — shows dashboard with mock data)
python main.py --demo

# Real camera (webcam index 0)
python main.py --camera-source 0 --venue-name "My School"

# IP camera / RTSP stream
python main.py --camera-source "rtsp://admin:pass@192.168.1.50:554/stream"

# Video file (for testing)
python main.py --camera-source /path/to/video.mp4
```

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
pip install pytest pytest-cov sqlalchemy numpy
python -m pytest tests/ -v
```

Expected output: **49 passed**.

---

## 🔒 Security & Privacy Notes

* **No video is stored by default** — only snapshots triggered by alerts.
* Face encodings are stored only locally; nothing is sent to the cloud.
* SMTP credentials must be provided via environment variables — never
  hardcoded in source.
* The system is designed to comply with GDPR "privacy by design" principles:
  the minimum personal data needed for each feature is collected and retained.

---

## 📄 License

MIT — see `LICENSE` for details.
