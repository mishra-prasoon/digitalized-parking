# Digitalized Web-Based Parking Solution with ANPR & Pre-Booking

IGNOU BCSP-064 Project | Prasoon Mishra | Enrolment: 2350775112

## Overview
A Django-based parking management system with Automatic Number Plate Recognition (ANPR), advance slot booking, and online payments via Razorpay.

## Tech Stack
- Backend: Python 3.13, Django 5.2
- Database: PostgreSQL
- Computer Vision: OpenCV, Tesseract OCR
- Payments: Razorpay
- Frontend: HTML, CSS, JavaScript (vanilla)

## Modules
1. **accounts** — user/staff authentication, role-based access
2. **core** — ParkingSlot and Vehicle models
3. **booking** — advance slot reservation with overlap prevention
4. **parking** — slot allocation engine (row-locked, concurrency-safe), check-in/check-out, fee calculation
5. **anpr** — OpenCV/Tesseract number plate recognition pipeline
6. **gate** — Entry Gate Display and Exit Kiosk (camera/upload capture, manual fallback)
7. **payments** — Razorpay order creation and signature-verified payment confirmation

## Setup

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DB credentials, SECRET_KEY, RAZORPAY keys, DEVICE_API_KEY
python manage.py migrate
python manage.py seed_slots
python manage.py createsuperuser
python manage.py runserver
```

## Key Design Decisions
- Custom user model set up before first migration to avoid auth table conflicts.
- Slot occupancy is derived from live Transaction status (not a stored flag), preventing drift.
- Slot allocation uses `select_for_update(skip_locked=True)` for safe concurrent access — verified with an automated multi-thread concurrency test.
- ANPR confidence scoring only averages over text-containing OCR boxes (not blank regions) to avoid false rejections.
- Payment is confirmed only after server-side Razorpay signature verification, never on client callback alone.
- Razorpay webhook is a documented, deliberate scope exclusion (requires public URL / ngrok); client-side verify-on-callback is the primary path for this project.

## Testing
57+ automated tests across all apps, including a concurrency test for slot allocation. Run with:
```bash
python manage.py test
```

## Known Limitations
- Manual end-to-end Razorpay test-card payment verification pending (service layer is unit-tested and signature verification logic is covered).
- Entry/Exit camera capture uses browser `getUserMedia`; file upload is the reliable path for demo purposes since a webcam can't read a plate at typical gate distance.
