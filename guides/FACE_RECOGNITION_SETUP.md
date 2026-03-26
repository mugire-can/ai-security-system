# 🧑‍🤝‍🧑 Face Recognition & Attendance Setup Guide

This guide walks through setting up face recognition for automated attendance tracking.

---

## 📁 Directory Structure

Face recognition requires a specific directory structure with registered face images:

```
data/known_faces/
├── Alice Smith/
│   ├── alice_01.jpg
│   ├── alice_02.jpg
│   └── alice_03.jpg
├── Bob Jones/
│   ├── bob_01.jpg
│   ├── bob_02.jpg
│   └── bob_03.jpg
└── Carol White/
    ├── carol_01.jpg
    └── carol_02.jpg
```

**Key Rules:**
- Each person gets one subdirectory named exactly as they should appear in reports
- Each subdirectory contains multiple face images (3-5 recommended)
- Image formats: `.jpg`, `.jpeg`, `.png`
- Image requirements:
  - Clear, well-lit face shots
  - Face takes up 30-70% of image
  - Minimal background clutter
  - Different angles/expressions improve accuracy

---

## 🚀 Quick Setup

### Method 1: Manual Directory Creation

```powershell
# Create directory structure
mkdir -p data/known_faces/"Alice Smith"
mkdir -p data/known_faces/"Bob Jones"
mkdir -p data/known_faces/"Carol White"

# Copy your face images:
copy C:\path\to\alice_photo1.jpg data/known_faces/"Alice Smith"/
copy C:\path\to\bob_photo1.jpg data/known_faces/"Bob Jones"/
```

### Method 2: Automated Setup Script

```bash
python scripts/setup_faces.py
# Interactive script to add people and images
```

---

## 📸 Best Practices for Face Images

### Capture Quality Images

1. **Lighting**: Well-lit, avoid harsh shadows
2. **Focus**: Face must be sharp and clear
3. **Angle**: Front-facing photos work best
4. **Framing**: Face fills 40-60% of image
5. **Background**: Neutral, non-distracting
6. **Variations**: Multiple photos of same person in different conditions

### Image Examples

**✅ GOOD** - Clear, front-facing, good lighting
- Face clearly visible and centered
- Eyes open, neutral expression
- No glasses covering eyes
- Good natural lighting

**❌ AVOID** - Poor quality images
- Side profile or extreme angle
- Dim or backlighting
- Face too small in image
- Blurred or out of focus
- Dark sunglasses covering eyes

---

## 🔧 Configuration

Once faces are set up, configure in `.env`:

```env
# Path to known_faces directory
KNOWN_FACES_DIR=data/known_faces

# How strict face matching is (0.0-1.0)
FACE_RECOGNITION_TOLERANCE=0.5
# Lower tolerance = stricter matching (default 0.5)
# If you get false positives, lower to 0.4
# If you get false negatives, raise to 0.6

# Attendance timing
WORK_START_TIME=08:00
WORK_END_TIME=18:00
```

---

## 📊 Attendance Tracking Features

Once configured, the system automatically:

- **Check-In**: Records first face detection at/after 08:00
- **Check-Out**: Records last face detection before 18:00
- **Status Tracking**:
  - `PRESENT` - Checked in and out on time
  - `LATE` - Checked in after work start
  - `EARLY_LEAVE` - Checked out before work end
  - `ABSENT` - Not detected during work day
- **Duration Tracking**: Calculates time spent
- **Reports**: CSV exports for HR systems

---

## 📈 Improving Accuracy

### The `FACE_RECOGNITION_TOLERANCE` Parameter

```python
# Current setting in config/settings.py
face_recognition_tolerance: float = 0.5
```

**Accuracy Tuning:**

| Tolerance | Behavior | Use Case |
|-----------|----------|----------|
| 0.3 | Very strict | High security, prevent spoofing |
| 0.4 | Strict | Corporate/school attendance |
| 0.5 | Balanced | Default (recommended) |
| 0.6 | Lenient | Quick throughput, larger distances |
| 0.7+ | Very lenient | Allow side profiles, distant faces |

**How to Test:**

1. After setting up faces, run demo:
   ```bash
   python main.py --demo
   ```
2. Check attendance reports to see accuracy
3. Adjust `FACE_RECOGNITION_TOLERANCE` if needed
4. Re-run tests to verify

---

## 🧪 Testing Face Recognition

### Verify Setup

```bash
# Test if faces load correctly
python -c "
from src.attendance.roll_call import RollCall
rc = RollCall()
print(f'Registered faces: {len(rc.known_face_names)}')
print(f'Names: {rc.known_face_names}')
"
```

### Run with Demo Data

```bash
python main.py --demo
# Watch attendance section - should show check-ins for: Alice, Bob, Carol
```

### Test with Real Webcam

```bash
# For testing, use camera index 0 (webcam)
python main.py --camera-source 0 --debug
# Press Ctrl+C to exit
```

---

## 🔐 Privacy & Security

**Data Protection:**

- Face encodings (not raw images) are stored
- Database file (`data/security_system.db`) is **NOT encrypted**
- For production: Use environment-based credentials
- **NEVER commit** actual face images to git

**Best Practices:**

1. Keep `data/` directory in `.gitignore` (already configured)
2. Restrict file permissions: `chmod 700 data/`
3. Use encrypted storage for production databases
4. Comply with GDPR/privacy regulations
5. Get consent before capturing faces

---

## 🆘 Troubleshooting

### Face not recognized

**Problem**: Person stands in front of camera but doesn't show in attendance

**Solutions**:
1. Check directory structure: `data/known_faces/YourName/` exists
2. Verify image quality: Face must be clear and well-lit
3. Lower tolerance: Set `FACE_RECOGNITION_TOLERANCE=0.4`
4. Add more reference images (5+ images help)
5. Check camera angle: Ensure face is clearly visible

### False positives (wrong person detected)

**Problem**: System incorrectly identifies person as someone else

**Solutions**:
1. Tighten tolerance: Set `FACE_RECOGNITION_TOLERANCE=0.4`
2. Add more varied reference images
3. Remove ambiguous images from known_faces
4. Ensure good lighting in known_faces images

### Slow performance

**Problem**: Face recognition is running slowly

**Solutions**:
1. Reduce image quality (compress JPGs)
2. Increase `ANALYSIS_FRAME_INTERVAL` (analyze every Nth frame)
3. Reduce number of registered people
4. Use GPU acceleration (CUDA-enabled GPU)

### File Structure Issues

**Problem**: System says "No known faces found"

**Check**:
```bash
# List directory structure
dir data/known_faces /s

# Should show:
# data/known_faces/
# ├── Person1/
# │   ├── image1.jpg
# │   └── image2.jpg
# └── Person2/
#     └── image1.jpg
```

---

## 📚 Advanced Configuration

### Emotion Recognition (Bonus)

The system also analyzes emotions. To see emotions in logs:

```bash
python main.py --debug  # Includes emotion in output
```

Detected emotions: angry, fear, happy, sad, surprise, neutral, disgust

### Custom Face Encodings

For large deployments (100+ people), pre-compute encodings:

```bash
python scripts/precompute_face_encodings.py
# Generates face_encodings.pkl for faster startup
```

### Integration with External Systems

Export attendance data:

```bash
# CSV export for HR systems
python scripts/export_attendance.py --start-date 2025-01-01 --end-date 2025-01-31 --output roster.csv
```

---

## 📖 Related Documentation

- [Main README](README.md) - Project overview
- [Architecture](ARCHITECTURE.md) - Technical details
- [Deployment](DEPLOYMENT.md) - Production setup
- [CONTRIBUTING](CONTRIBUTING.md) - Development guidelines

---

## ❓ FAQ

**Q: Can I use photos from the internet?**
A: Not recommended. Use photos where you control lighting and angle. Stock photos often have poor lighting or extreme angles.

**Q: How many faces can the system handle?**
A: Practically tested with 10-50 people. No theoretical limit, but performance degrades with very large datasets (1000+).

**Q: Does it work with masks/glasses?**
A: Yes, but accuracy drops. If face is partially covered, tolerance should be increased.

**Q: Is attendance data encrypted?**
A: No. For production, implement database-level encryption or use external databases with TLS.

