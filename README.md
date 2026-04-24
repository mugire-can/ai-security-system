# AI Security Camera System

Live monitoring platform for schools, shopping centers, shops, and workplaces.
It ingests camera feeds, runs AI-based incident detection, stores events, and
sends alerts through the dashboard, email, and webhooks.

## What It Detects

- Suspicious behavior: fighting, loitering, running, theft heuristics
- Accident indicators: fallen-person or person-down events
- Object anomalies: animals, unattended items, vehicles in restricted zones
- Facility faults from custom CV labels: fire, smoke, water leaks, electrical hazards
- Threat labels from custom CV models: weapon-related detections
- System issues: stalled or offline camera feeds and repeated read failures

## Architecture

The main runtime is the Python pipeline:

1. Camera feeds are opened by `src/camera/camera_manager.py`.
2. The pipeline in `src/pipeline.py` runs detection, behavior analysis,
   anomaly analysis, attendance, alerting, and persistence.
3. Alerts are written to the database and shown in the dashboard.

Optional service folders exist for supporting components:

- `services/go/alert_dispatcher`: alert queue / dispatch service
- `services/go/camera_streamer`: camera registration and health service
- `services/typescript/api`: API gateway
- `services/rust/video_optimizer`: frame optimization service

If you only want the core system, start with Python. The extra services are not
required for local demo mode.

## Project Layout

```text
.
├── main.py
├── config/
├── src/
├── services/
├── tests/
├── scripts/
└── data/
```

Main code paths:

- `src/pipeline.py`: top-level processing pipeline
- `src/detection/`: detectors and post-processing
- `src/alerts/`: email/webhook alerting
- `src/database/`: SQLAlchemy models and storage
- `src/dashboard/`: terminal dashboard

## Quick Start

### Demo Mode

```bash
python main.py --demo
```

### Local Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts/setup_database.py
python main.py --demo
```

### Real Camera

```bash
python main.py --camera-source 0
python main.py --camera-source "rtsp://user:password@camera-ip/stream"
```

## Configuration

Copy `.env.example` to `.env` and edit only what you need.

Important variables:

- `VENUE_TYPE`: `school`, `commercial`, or `workplace`
- `YOLO_MODEL`: model path or weights name
- `DATABASE_URL`: default `sqlite:///data/security_system.db`
- `ALERT_COOLDOWN_SECONDS`: duplicate alert suppression window
- `LOITERING_THRESHOLD_SECONDS`: dwell time before loitering alert
- `CAMERA_STALL_SECONDS`: feed stall threshold
- `MAX_CONSECUTIVE_READ_FAILURES`: degraded camera threshold
- `SMTP_*` and `ALERT_WEBHOOK_URL`: external alert delivery

The runtime creates local data under `data/`.

## Custom Model Labels

Standard YOLO handles people, animals, vehicles, and common carried objects.
For facility faults or direct threats, use a custom model that emits labels
such as:

- `fire`, `flame`
- `smoke`
- `water_leak`, `leak`, `flood`, `spill`
- `electrical_spark`, `short_circuit`, `arc_flash`
- `knife`, `gun`, `weapon`
- `fallen_person`, `person_down`

These labels are mapped into higher-level alerts automatically.

## Alert Types

- `fight`: violent close-range movement
- `loitering`: stationary presence above threshold
- `suspicious_behaviour`: generic suspicious behavior including falls
- `intrusion`: direct threat label routed as a high-priority alert
- `anomaly`: object, facility, or person-down anomaly
- `other`: camera or system-health issue

## Deployment

The repo includes:

- `docker-compose.yml`
- `Dockerfile.python`
- Go services for alerting and camera status
- TypeScript API service
- Rust video optimizer service

Basic Docker flow:

```bash
docker-compose build
docker-compose up
```

Useful ports:

- `3000`: TypeScript API
- `5000`: Python core
- `8080`: Go alert dispatcher
- `8081`: Go camera streamer
- `8082`: Rust video optimizer
- `5432`: PostgreSQL
- `6379`: Redis

## Troubleshooting

- If `pytest` is not on PATH, use `python -m pytest`.
- If the checked-in database is missing, recreate it with:
  `python scripts/setup_database.py`
- If camera feeds fail repeatedly, the pipeline now raises health alerts
  instead of failing silently.
- If you want better facility-fault detection, you need a custom model with
  explicit labels for those hazards.

## Development

Workflow:

1. Create a branch.
2. Install dependencies.
3. Make the change.
4. Run `python -m pytest tests -q`.
5. Update this README if behavior changed.

Code expectations:

- Keep functions small and explicit.
- Add tests for new behavior.
- Prefer clear thresholds/config over hidden magic values.

## Testing

Run:

```bash
python -m pytest tests -q
```

Current result in this workspace:

- `194 passed`
- `1 skipped` for an environment-specific Go formatting check

## Notes

- Runtime artifacts are ignored by git.
- The old checked-in SQLite database was removed.
- Real production accuracy depends on camera placement, model quality, and
  whether your model exposes the labels you expect.
