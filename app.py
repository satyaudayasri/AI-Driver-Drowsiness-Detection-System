import os
import threading
import cv2
from flask import Flask, Response, render_template_string, request, jsonify
from twilio.rest import Client
from dotenv import load_dotenv

# ================== LOAD ENV ==================
load_dotenv()

ACCOUNT_SID   = os.getenv("ACCOUNT_SID", "")
AUTH_TOKEN    = os.getenv("AUTH_TOKEN", "")
FROM_NUMBER   = os.getenv("FROM_NUMBER", "")
DRIVER_NUMBER = os.getenv("DRIVER_NUMBER", "")
FAMILY_NUMBER = os.getenv("FAMILY_NUMBER", "")
IP_CAM_URL    = os.getenv("IP_CAM_URL", "")   # e.g. http://192.168.1.5:8080/video

client = Client(ACCOUNT_SID, AUTH_TOKEN) if ACCOUNT_SID else None

# ================== GLOBALS ==================
VEHICLE_NUMBER    = os.getenv("VEHICLE_NUMBER", "AP09AB1234")
eye_closed_frames = 0
THRESHOLD         = 20
alert_sent        = False
status            = "LIVE"
driver_location   = "Location not fetched yet"
driver_maps_link  = ""
alarm_playing     = False


# ================== CAMERA SETUP ==================
def open_camera():
    """Try IP camera first, fall back to local webcam."""
    if IP_CAM_URL:
        print(f"📷 Trying IP Camera: {IP_CAM_URL}")
        cap = cv2.VideoCapture(IP_CAM_URL)
        if cap.isOpened():
            print("✅ IP Camera connected!")
            return cap
        print("⚠️  IP Camera failed, falling back to webcam...")

    for idx in [0, 1]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            print(f"✅ Local camera {idx} opened.")
            return cap

    print("❌ No camera found.")
    return None


cap = open_camera()
if cap:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS,          30)

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
eye_cascade  = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml")


# ================== ALARM (Cross-platform) ==================
def play_alarm():
    """Works on Windows, Linux, Mac & cloud servers."""
    global alarm_playing
    if alarm_playing:
        return
    alarm_playing = True

    def _beep():
        global alarm_playing
        try:
            # Windows only
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 600)
        except ImportError:
            # Linux/Mac/Cloud → log only (no speaker on server)
            print("🔔 ALARM! Driver drowsy!")
        alarm_playing = False

    threading.Thread(target=_beep, daemon=True).start()


# ================== TWIML BUILDERS ==================
def build_twiml_driver(vehicle, location):
    vehicle_readable = ", ".join(list(vehicle))
    loc_clean = (location
                 .replace("Lat:", "latitude")
                 .replace("Lon:", "longitude")
                 .replace("±", "plus or minus")
                 .replace("(", "").replace(")", ""))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Google.te-IN-Standard-A" language="te-IN">
    హెచ్చరిక! మీరు నిద్రపోతున్నారు. ప్రమాదం జరగవచ్చు.
  </Say>
  <Pause length="1"/>
  <Say voice="Polly.Raveena" language="en-IN">
    Drowsiness alert for vehicle number {vehicle_readable}.
    Driver is falling asleep at the wheel.
  </Say>
  <Pause length="1"/>
  <Say voice="Polly.Raveena" language="en-IN">
    Current location: {loc_clean}.
  </Say>
  <Pause length="1"/>
  <Say voice="Google.te-IN-Standard-A" language="te-IN">
    దయచేసి వాహనాన్ని వెంటనే ఆపండి. విశ్రాంతి తీసుకోండి.
  </Say>
</Response>""".strip()


def build_twiml_family(vehicle, location):
    vehicle_readable = ", ".join(list(vehicle))
    loc_clean = (location
                 .replace("Lat:", "latitude")
                 .replace("Lon:", "longitude")
                 .replace("±", "plus or minus")
                 .replace("(", "").replace(")", ""))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Google.te-IN-Standard-A" language="te-IN">
    అత్యవసర హెచ్చరిక! మీ వాహన చోదకుడు నిద్రపోతున్నారు.
  </Say>
  <Pause length="1"/>
  <Say voice="Polly.Raveena" language="en-IN">
    Emergency alert for vehicle number {vehicle_readable}.
    The driver appears to be drowsy and may be in danger.
  </Say>
  <Pause length="1"/>
  <Say voice="Polly.Raveena" language="en-IN">
    Driver location: {loc_clean}.
  </Say>
  <Pause length="1"/>
  <Say voice="Google.te-IN-Standard-A" language="te-IN">
    దయచేసి వెంటనే చోదకుడిని సంప్రదించండి లేదా సహాయం పంపండి.
  </Say>
</Response>""".strip()


# ================== CALL FUNCTION ==================
def make_call(to_number, twiml_message):
    if not client:
        print("⚠️  Twilio not configured. Skipping call.")
        return
    try:
        call = client.calls.create(twiml=twiml_message, from_=FROM_NUMBER, to=to_number)
        print(f"✅ Call → {to_number} | SID: {call.sid}")
    except Exception as e:
        print(f"❌ Call Error → {to_number}: {e}")


def send_alert_async():
    loc = driver_location
    driver_twiml = build_twiml_driver(VEHICLE_NUMBER, loc)
    family_twiml = build_twiml_family(VEHICLE_NUMBER, loc)

    def _do_calls():
        import time
        print(f"📞 Calling driver: {DRIVER_NUMBER}")
        make_call(DRIVER_NUMBER, driver_twiml)
        delay = 3 if FAMILY_NUMBER != DRIVER_NUMBER else 35
        time.sleep(delay)
        print(f"📞 Calling family: {FAMILY_NUMBER}")
        make_call(FAMILY_NUMBER, family_twiml)

    threading.Thread(target=_do_calls, daemon=True).start()


# ================== FLASK APP ==================
app = Flask(__name__)


def generate_frames():
    global eye_closed_frames, alert_sent, status

    if not cap:
        # No camera — send blank frame with message
        import numpy as np
        blank = np.zeros((480, 640, 3), dtype="uint8")
        cv2.putText(blank, "No Camera Found", (120, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        ret, buf = cv2.imencode('.jpg', blank)
        while True:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

    while True:
        success, frame = cap.read()
        if not success:
            break

        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray  = cv2.equalizeHist(gray)

        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5,
            minSize=(80, 80), flags=cv2.CASCADE_SCALE_IMAGE
        )

        face_detected = len(faces) > 0

        for (x, y, w, h) in faces:
            roi_gray  = gray[y:y+h, x:x+w]
            roi_color = frame[y:y+h, x:x+w]
            eyes = eye_cascade.detectMultiScale(
                roi_gray, scaleFactor=1.05, minNeighbors=4, minSize=(20, 20)
            )
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 200, 0), 2)
            for (ex, ey, ew, eh) in eyes:
                cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (0, 255, 0), 2)

            if len(eyes) < 2:
                eye_closed_frames += 1
            else:
                eye_closed_frames = 0
                alert_sent        = False
                status            = "LIVE"

        if not face_detected:
            eye_closed_frames = 0

        if eye_closed_frames >= THRESHOLD:
            status = "DROWSY"
            cv2.putText(frame, "DROWSY!", (30, 90),
                        cv2.FONT_HERSHEY_DUPLEX, 1.8, (0, 0, 255), 3)
            play_alarm()
            if not alert_sent:
                alert_sent = True
                print("🚨 DROWSY ALERT — Sending voice calls...")
                send_alert_async()
        else:
            if status == "LIVE":
                cv2.putText(frame, "LIVE", (30, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 220, 0), 2)

        cv2.putText(frame, f"Closed: {eye_closed_frames}/{THRESHOLD}",
                    (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# ================== ROUTES ==================
@app.route('/update_location', methods=['POST'])
def update_location():
    global driver_location, driver_maps_link
    data = request.get_json()
    if data:
        lat  = data.get('lat', '')
        lon  = data.get('lon', '')
        acc  = data.get('accuracy', '')
        driver_location  = f"Lat: {lat}, Lon: {lon} (±{acc}m)"
        driver_maps_link = f"https://maps.google.com/?q={lat},{lon}"
        print(f"📍 Location updated: {driver_location}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400


@app.route('/get_status')
def get_status():
    return jsonify({
        "status":    status,
        "location":  driver_location,
        "map":       driver_maps_link,
        "frames":    eye_closed_frames,
        "threshold": THRESHOLD
    })


@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="te">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Driver Drowsiness Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    min-height: 100vh;
  }
  .header {
    background: linear-gradient(90deg, #020617, #0f172a);
    padding: 18px 30px;
    text-align: center;
    font-size: 22px;
    font-weight: bold;
    color: #38bdf8;
    border-bottom: 2px solid #1e3a5f;
  }
  .header span { font-size: 14px; color: #7dd3fc; display: block; margin-top: 4px; }
  .container { display: flex; padding: 24px; gap: 20px; flex-wrap: wrap; }
  .video-wrap { flex: 2; min-width: 300px; }
  .video-wrap img {
    width: 100%; border-radius: 12px;
    border: 3px solid #38bdf8;
    box-shadow: 0 0 20px #38bdf844;
  }
  .side { flex: 1; display: flex; flex-direction: column; gap: 16px; min-width: 220px; }
  .card {
    background: #020617; padding: 20px; border-radius: 12px;
    box-shadow: 0 0 12px #38bdf830; text-align: center;
    border: 1px solid #1e3a5f;
  }
  .card h3 { color: #7dd3fc; margin-bottom: 10px; font-size: 14px; }
  .card p  { font-size: 18px; font-weight: bold; }
  .status-live   { color: #22c55e; font-size: 24px !important; }
  .status-drowsy { color: #ef4444; font-size: 22px !important; animation: blink 0.6s step-start infinite; }
  @keyframes blink { 50% { opacity: 0; } }
  .loc-text { font-size: 12px !important; word-break: break-all; color: #94a3b8; }
  .map-link { color: #38bdf8; font-size: 13px; text-decoration: none; }
  .map-link:hover { text-decoration: underline; }
  .bar-wrap { background: #1e293b; border-radius: 6px; height: 12px; overflow: hidden; margin-top: 8px; }
  .bar-fill { height: 100%; background: #22c55e; transition: width 0.3s, background 0.3s; }
  .gps-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; margin-top: 6px; }
  .gps-ok   { background: #14532d; color: #4ade80; }
  .gps-wait { background: #451a03; color: #fb923c; }
  .call-badge {
    display: none; background: #7f1d1d; color: #fca5a5;
    padding: 8px; border-radius: 8px; font-size: 13px;
    font-weight: bold; margin-top: 8px;
    animation: blink 0.8s step-start infinite;
  }
  .info-box {
    background: #0c1a2e; border: 1px solid #1e3a5f;
    border-radius: 8px; padding: 12px;
    font-size: 12px; color: #64748b;
    text-align: left; line-height: 1.6;
  }
  .info-box strong { color: #7dd3fc; }
</style>
</head>
<body>
<div class="header">
  🚗 Driver Drowsiness Detection Dashboard
  <span>వాహన చోదకుడి నిద్ర హెచ్చరిక వ్యవస్థ</span>
</div>
<div class="container">
  <div class="video-wrap">
    <img src="/video" alt="Live Feed">
  </div>
  <div class="side">
    <div class="card">
      <h3>🚘 Vehicle Number</h3>
      <p>{{ vehicle }}</p>
    </div>
    <div class="card">
      <h3>📊 Driver Status</h3>
      <p id="statusText" class="status-live">LIVE</p>
      <div class="call-badge" id="callBadge">📞 Calls పంపబడ్డాయి!</div>
    </div>
    <div class="card">
      <h3>👁 Eye Closed Frames</h3>
      <p id="frameCount">0 / {{ threshold }}</p>
      <div class="bar-wrap">
        <div class="bar-fill" id="frameBar" style="width:0%"></div>
      </div>
    </div>
    <div class="card">
      <h3>📍 GPS Location</h3>
      <p class="loc-text" id="locText">GPS కోసం వేచి ఉంది…</p>
      <span class="gps-badge gps-wait" id="gpsBadge">⏳ GPS వస్తోంది…</span>
      <br><br>
      <a class="map-link" id="mapLink" href="#" target="_blank">📌 Google Maps లో చూడండి</a>
    </div>
    <div class="card">
      <div class="info-box">
        <strong>📞 Alert Method:</strong><br>
        Telugu + English Voice Calls<br><br>
        <strong>Call Content:</strong><br>
        • Telugu drowsiness warning<br>
        • English vehicle number<br>
        • English GPS location<br>
        • Telugu stop vehicle instruction<br><br>
        <strong>Voice:</strong> Google Telugu + Polly Indian English
      </div>
    </div>
  </div>
</div>

<script>
function startGPS() {
  if (!navigator.geolocation) { return; }
  navigator.geolocation.watchPosition(
    function(pos) {
      const lat = pos.coords.latitude.toFixed(6);
      const lon = pos.coords.longitude.toFixed(6);
      const acc = Math.round(pos.coords.accuracy);
      document.getElementById('gpsBadge').textContent = '✅ GPS యాక్టివ్';
      document.getElementById('gpsBadge').className   = 'gps-badge gps-ok';
      document.getElementById('locText').textContent  = `Lat: ${lat}, Lon: ${lon} (±${acc}m)`;
      document.getElementById('mapLink').href         = `https://maps.google.com/?q=${lat},${lon}`;
      fetch('/update_location', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ lat, lon, accuracy: acc })
      });
    },
    function() {
      document.getElementById('locText').textContent  = 'GPS అనుమతి తిరస్కరించబడింది';
      document.getElementById('gpsBadge').textContent = '❌ GPS లేదు';
      document.getElementById('gpsBadge').className   = 'gps-badge gps-wait';
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
  );
}

let prevStatus = 'LIVE';
function pollStatus() {
  fetch('/get_status')
    .then(r => r.json())
    .then(d => {
      const el    = document.getElementById('statusText');
      const bar   = document.getElementById('frameBar');
      const cnt   = document.getElementById('frameCount');
      const badge = document.getElementById('callBadge');

      el.textContent = d.status === 'DROWSY' ? '⚠ నిద్రపోతున్నారు! DROWSY!' : 'LIVE ✔';
      el.className   = d.status === 'DROWSY' ? 'status-drowsy' : 'status-live';

      badge.style.display = (d.status === 'DROWSY' && prevStatus !== 'DROWSY') ? 'block' :
                             d.status !== 'DROWSY' ? 'none' : badge.style.display;
      prevStatus = d.status;

      const pct = Math.min((d.frames / d.threshold) * 100, 100);
      bar.style.width      = pct + '%';
      bar.style.background = pct > 70 ? '#ef4444' : pct > 40 ? '#f59e0b' : '#22c55e';
      cnt.textContent      = `${d.frames} / ${d.threshold}`;

      if (d.location && d.location !== 'Location not fetched yet') {
        document.getElementById('locText').textContent = d.location;
      }
      if (d.map) document.getElementById('mapLink').href = d.map;
    });
}

startGPS();
setInterval(pollStatus, 800);
</script>
</body>
</html>
""", vehicle=VEHICLE_NUMBER, threshold=THRESHOLD)


@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
