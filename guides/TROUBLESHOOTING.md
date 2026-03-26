# 🆘 Troubleshooting Guide

Common issues and solutions for the AI Security System.

---

## Installation & Setup Issues

### Issue: `python` command not recognized

**Problem:**
```
python: The term 'python' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

**Solution:**
Use the `py` launcher (Windows) or `python3` (Linux/Mac):

```powershell
# Windows - Use py launcher
py -3.14 --version
py -3.14 -m pip install -r requirements.txt
py -3.14 main.py --demo

# Linux/Mac
python3 --version
python3 -m pip install -r requirements.txt
python3 main.py --demo
```

**Permanent Fix:**
Add Python to PATH:
1. Find Python installation: `py -3.14 -c "import sys; print(sys.executable)"`
2. Copy the directory (e.g., `C:\Users\...\Python314`)
3. Add to Windows PATH environment variable
4. Restart terminal

---

### Issue: Virtual environment has broken path

**Problem:**
```
did not find executable at 'C:\Python314\python.exe': The system cannot find the file specified.
```

**Solution:**
Recreate the virtual environment:

```powershell
# Deactivate current venv
deactivate

# Backup old one (optional)
ren venv venv.old

# Create fresh venv
py -3.14 -m venv venv

# Activate
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

### Issue: `pip install` fails with SSL error

**Problem:**
```
ERROR: Could not install packages due to an EnvironmentError: SSL certificate_verify_failed
```

**Solution:**

Option 1: Disable SSL verification (not recommended for production):
```powershell
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

Option 2: Update certificates:
```powershell
# Windows
pip install --upgrade certifi

# macOS
/Applications/Python\ 3.14/Install\ Certificates.command
```

---

### Issue: torch/ML library import errors with Python 3.14

**Problem:**
```
ImportError: torch distribution module initialization fails
```

**Context:** Python 3.14 is very new; some libraries have limited support.

**Solution:**

Option 1: Use Python 3.13 or earlier (if available)
```powershell
py -3.13 --version
py -3.13 -m venv venv
```

Option 2: Update to latest library versions
```powershell
pip install --upgrade torch ultralytics opencv-python
```

Option 3: Report to library maintainers (pytorch, ultralytics, etc.)

---

## Runtime Issues

### Issue: Demo runs but shows no people detected

**Problem:**
- Demo runs but attendance table is empty
- No activity in alerts

**Causes:**
1. Camera not focused/disabled
2. YOLO model not downloaded
3. Detection thresholds too high

**Solution:**

```bash
# Check model is downloaded
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Run with debug to see detection logs
python main.py --demo --debug

# Lower detection threshold
export PERSON_CONFIDENCE_THRESHOLD=0.40
python main.py --demo
```

---

### Issue: Face recognition not working for attendance

**Problem:**
- Face recognition enabled but attendance shows "ABSENT" for everyone
- No check-ins occur

**Solutions:**

1. **Verify directory structure:**
   ```powershell
   # Should exist: data/known_faces/PersonName/photo.jpg
   Dir -Recurse data/known_faces/
   
   # Expected output:
   # data/known_faces/
   # ├── Alice Smith/
   # │   ├── alice_01.jpg
   # │   └── alice_02.jpg
   ```

2. **Check image quality:**
   - Images must be clear, well-lit
   - Face should fill 40-60% of image
   - Use varied angles (3-5 photos per person)

3. **Adjust tolerance:**
   ```env
   # In .env, try lower tolerance (stricter):
   FACE_RECOGNITION_TOLERANCE=0.4
   
   # Or higher tolerance (more lenient):
   FACE_RECOGNITION_TOLERANCE=0.6
   ```

4. **Test face detection directly:**
   ```bash
   python -c "
   from src.attendance.roll_call import RollCall
   rc = RollCall()
   print(f'Known names: {rc.known_face_names}')
   print(f'Face encodings loaded: {len(rc.known_face_encodings)}')
   "
   ```

See [FACE_RECOGNITION_SETUP.md](../guides/FACE_RECOGNITION_SETUP.md) for detailed setup.

---

### Issue: Slow performance, low FPS

**Problem:**
- Dashboard shows <10 FPS
- UI is laggy
- High CPU/GPU usage

**Diagnosis:**
```bash
python main.py --demo --debug
# Look for: "Frame latency: XXXms"
# > 100ms = slow, <30ms = good
```

**Solutions:**

1. **Reduce analysis frequency:**
   ```env
   ANALYSIS_FRAME_INTERVAL=10  # Analyze every 10th frame
   ```

2. **Use smaller model:**
   ```env
   YOLO_MODEL=yolov8n.pt  # nano (fast) instead of large
   ```

3. **Lower resolution:**
   ```env
   CAMERA_RESOLUTION_WIDTH=640
   CAMERA_RESOLUTION_HEIGHT=480
   ```

4. **Disable heavy analysis:**
   ```env
   ENABLE_EMOTION_ANALYSIS=false
   ENABLE_FACE_RECOGNITION=false
   ```

5. **Check GPU usage:**
   ```powershell
   # Should show GPU memory allocation
   python -c "import torch; print(torch.cuda.memory_allocated())"
   ```

See [PERFORMANCE_BENCHMARKS.md](../guides/PERFORMANCE_BENCHMARKS.md) for detailed tuning.

---

### Issue: Alerts not sending via email

**Problem:**
- Demo runs but no emails arrive
- Webhook alerts not working

**Cause:** SMTP configuration incorrect

**Solution:**

1. **Verify SMTP settings in .env:**
   ```env
   ADMIN_EMAIL=your-email@gmail.com
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-specific-password  # NOT regular password!
   ```

2. **For Gmail (common issue):**
   - Must use [App Password](https://myaccount.google.com/apppasswords), not regular password
   - Requires 2-step verification enabled on account
   - App Password is 16 characters (remove spaces)

3. **For Office 365:**
   ```env
   SMTP_HOST=smtp.office365.com
   SMTP_PORT=587
   ```

4. **For custom SMTP:**
   - Contact your email provider for SMTP details
   - Confirm port (587 or 25)
   - Verify TLS is enabled

5. **Test SMTP connection:**
   ```bash
   python -c "
   import smtplib
   from config.settings import DEFAULT_CONFIG
   
   cfg = DEFAULT_CONFIG.alert
   try:
       server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)
       server.starttls()
       server.login(cfg.smtp_user, cfg.smtp_password)
       print('✅ SMTP connection successful')
       server.quit()
   except Exception as e:
       print(f'❌ SMTP error: {e}')
   "
   ```

See [Email Configuration Guide](#email-configuration-guide) below.

---

### Issue: Database file grows too large

**Problem:**
- `data/security_system.db` grows to multi-GB
- Slow database queries

**Solution:**

Option 1: Archive old data (recommended):
```bash
# Export data older than 30 days
python scripts/archive_database.py --days 30 --output archive.csv

# Delete old records
python scripts/cleanup_database.py --days 30
```

Option 2: Upgrade to PostgreSQL (production):
```env
DATABASE_URL=postgresql://user:password@localhost:5432/security_system
```

PostgreSQL with proper indexes is faster even with large datasets.

---

### Issue: Port already in use

**Problem:**
```
address already in use
error: [Errno 48] Address already in use
```

**Cause:** Another process is using the port (usually previous instance)

**Solution:**

```powershell
# Find process using port 5000 (Flask)
netstat -ano | findstr :5000

# Kill the process (replace PID with actual number)
taskkill /PID 1234 /F

# Or use different port
export FLASK_PORT=5001
python main.py
```

---

## Deployment Issues

### Issue: Docker build fails

**Problem:**
```
ERROR: failed to solve: permission denied while trying to connect to Docker daemon
```

**Solution:**

```powershell
# Ensure Docker Desktop is running
docker ps

# If not running, start it:
# - Windows: Start Docker Desktop from Start menu
# - Linux: sudo systemctl start docker

# Try build again
docker-compose build
```

---

### Issue: Containers can't communicate

**Problem:**
- Containers start but services can't reach each other
- API can't reach Python core

**Solution:**

```bash
# Check Docker network
docker network ls

# Verify services are on same network
docker-compose ps

# Check logs for connection errors
docker-compose logs api
docker-compose logs python-core

# Manually test connection
docker run --network ai-security-system_default curlimages/curl http://python-core:5000/health
```

---

## Email Configuration Guide

### Gmail (Free)

1. Enable 2-step verification: https://myaccount.google.com/security
2. Generate app password: https://myaccount.google.com/apppasswords
3. Configure:
   ```env
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-16-char-app-password
   ADMIN_EMAIL=your-email@gmail.com
   ```

### Office 365 / Outlook

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=your-email@company.com
SMTP_PASSWORD=your-password
ADMIN_EMAIL=your-email@company.com
```

### SendGrid

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.your-api-key
ADMIN_EMAIL=notifications@yourdomain.com
```

### AWS SES

```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com  # Region-specific
SMTP_PORT=587
SMTP_USER=your-smtp-username
SMTP_PASSWORD=your-smtp-password
ADMIN_EMAIL=verified-email@yourdomain.com
```

---

## Webhook Configuration

### Slack

1. Create incoming webhook: https://api.slack.com/messaging/webhooks
2. Configure:
   ```env
   ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_WEBHOOK_ID
   ```

### Microsoft Teams

1. Create incoming webhook in Teams channel
2. Configure:
   ```env
   ALERT_WEBHOOK_URL=https://outlook.webhook.office.com/webhookb2/YOUR_WEBHOOK_ID
   ```

### Discord

1. Create webhook in Discord server settings
2. Configure:
   ```env
   ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID
   ```

---

## Performance Debugging

### Check FPS and latency

```bash
python main.py --debug 2>&1 | grep -i "frame\|latency"

# Output shows:
# Frame capture: 22ms
# Detection: 18ms
# Analysis: 45ms
# Total: 85ms → 11.7 FPS
```

### Profile CPU/GPU usage

```bash
# Monitor while running
python main.py --demo &
sleep 2

# Windows - Task Manager (GUI)
# Or use PowerShell:
Get-Process python | Select-Object ProcessName, CPU, Memory

# GPU (NVIDIA)
nvidia-smi -l 1
```

---

## Getting More Help

If issues persist:

1. **Check logs:**
   ```bash
   python main.py --debug 2>&1 | tee debug.log
   # Review debug.log for specific error messages
   ```

2. **Run tests:**
   ```bash
   pytest tests/ -v
   # If tests fail, system has deeper issues
   ```

3. **Review documentation:**
   - [README.md](../README.md) - Project overview
   - [ARCHITECTURE.md](../ARCHITECTURE.md) - System design
   - [DEPLOYMENT.md](../DEPLOYMENT.md) - Production setup
   - [PERFORMANCE_BENCHMARKS.md](../guides/PERFORMANCE_BENCHMARKS.md) - Tuning

4. **Report issues on GitHub** (if applicable)

---

## Quick Reference: Common Commands

```bash
# Development
python main.py --demo                      # Run demo
python main.py --debug                     # Debug logging
pytest tests/ -v                           # Run all tests
python scripts/setup_database.py --seed    # Initialize DB with test data

# Configuration
cp .env.example .env                       # Create .env from template
nano .env                                  # Edit configuration

# Maintenance
python scripts/setup_database.py --backup  # Backup database
python scripts/cleanup_database.py --days 30  # Archive old data

# Docker
docker-compose build                       # Build containers
docker-compose up                          # Start services
docker-compose logs -f api                 # View service logs
```

