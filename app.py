import os
import threading
from flask import Flask, request, jsonify, render_template_string
from twilio.rest import Client
from dotenv import load_dotenv

# ================== LOAD ENV ==================
load_dotenv()

ACCOUNT_SID    = os.getenv("ACCOUNT_SID", "")
AUTH_TOKEN     = os.getenv("AUTH_TOKEN", "")
FROM_NUMBER    = os.getenv("FROM_NUMBER", "")
DRIVER_NUMBER  = os.getenv("DRIVER_NUMBER", "")
FAMILY_NUMBER  = os.getenv("FAMILY_NUMBER", "")
VEHICLE_NUMBER = os.getenv("VEHICLE_NUMBER", "AP09AB1234")
THRESHOLD      = int(os.getenv("THRESHOLD", "20"))

client = Client(ACCOUNT_SID, AUTH_TOKEN) if ACCOUNT_SID else None

# ================== GLOBALS ==================
alert_sent       = False
driver_location  = "Location not fetched yet"
driver_maps_link = ""


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
    loc          = driver_location
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


@app.route('/update_location', methods=['POST'])
def update_location():
    global driver_location, driver_maps_link
    data = request.get_json()
    if data:
        lat              = data.get('lat', '')
        lon              = data.get('lon', '')
        acc              = data.get('accuracy', '')
        driver_location  = f"Lat: {lat}, Lon: {lon} (±{acc}m)"
        driver_maps_link = f"https://maps.google.com/?q={lat},{lon}"
        print(f"📍 Location updated: {driver_location}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400


@app.route('/drowsy_alert', methods=['POST'])
def drowsy_alert():
    """Called by the browser when face-api.js detects drowsiness."""
    global alert_sent
    data     = request.get_json()
    is_drowsy = data.get('drowsy', False)

    if is_drowsy and not alert_sent:
        alert_sent = True
        print("🚨 DROWSY ALERT from browser — Sending voice calls...")
        send_alert_async()
        return jsonify({"status": "alert_sent"})
    elif not is_drowsy:
        alert_sent = False
        return jsonify({"status": "reset"})
    return jsonify({"status": "already_alerted"})


@app.route('/get_status')
def get_status():
    return jsonify({
        "location":  driver_location,
        "map":       driver_maps_link,
        "threshold": THRESHOLD,
        "vehicle":   VEHICLE_NUMBER,
    })


@app.route('/')
def index():
    return render_template_string(HTML_PAGE, vehicle=VEHICLE_NUMBER, threshold=THRESHOLD)


# ================== HTML PAGE ==================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="te">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Driver Drowsiness Detection</title>
<script defer src="https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
  .header {
    background: linear-gradient(90deg, #020617, #0f172a);
    padding: 18px 30px; text-align: center;
    font-size: 22px; font-weight: bold; color: #38bdf8;
    border-bottom: 2px solid #1e3a5f;
  }
  .header span { font-size: 14px; color: #7dd3fc; display: block; margin-top: 4px; }
  .container { display: flex; padding: 24px; gap: 20px; flex-wrap: wrap; }
  .video-wrap { flex: 2; min-width: 300px; position: relative; }
  .video-wrap video {
    width: 100%; border-radius: 12px;
    border: 3px solid #38bdf8;
    box-shadow: 0 0 20px #38bdf844; display: block;
  }
  .video-wrap canvas {
    position: absolute; top: 0; left: 0;
    width: 100%; height: 100%;
    border-radius: 12px; pointer-events: none;
  }
  .side { flex: 1; display: flex; flex-direction: column; gap: 16px; min-width: 220px; }
  .card {
    background: #020617; padding: 20px; border-radius: 12px;
    box-shadow: 0 0 12px #38bdf830; text-align: center; border: 1px solid #1e3a5f;
  }
  .card h3 { color: #7dd3fc; margin-bottom: 10px; font-size: 14px; }
  .card p  { font-size: 18px; font-weight: bold; }
  .status-live    { color: #22c55e; font-size: 24px !important; }
  .status-drowsy  { color: #ef4444; font-size: 22px !important; animation: blink 0.6s step-start infinite; }
  .status-loading { color: #f59e0b; font-size: 15px !important; }
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
    font-size: 12px; color: #64748b; text-align: left; line-height: 1.6;
  }
  .info-box strong { color: #7dd3fc; }
  #startBtn {
    background: #0284c7; color: white; border: none;
    padding: 12px 24px; border-radius: 8px; font-size: 16px;
    cursor: pointer; width: 100%; margin-top: 8px;
  }
  #startBtn:hover { background: #0369a1; }
  #startBtn:disabled { background: #334155; cursor: not-allowed; }
</style>
</head>
<body>

<div class="header">
  🚗 Driver Drowsiness Detection Dashboard
  <span>వాహన చోదకుడి నిద్ర హెచ్చరిక వ్యవస్థ</span>
</div>

<div class="container">
  <div class="video-wrap">
    <video id="video" autoplay muted playsinline></video>
    <canvas id="overlay"></canvas>
  </div>

  <div class="side">
    <div class="card">
      <h3>🚘 Vehicle Number</h3>
      <p>{{ vehicle }}</p>
    </div>

    <div class="card">
      <h3>📊 Driver Status</h3>
      <p id="statusText" class="status-loading">⏳ Loading AI Models...</p>
      <div class="call-badge" id="callBadge">📞 Calls పంపబడ్డాయి!</div>
      <button id="startBtn" onclick="startCamera()" disabled>📷 Start Camera</button>
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
      <span class="gps-badge gps-wait" id="gpsBadge">⏳ GPS వస్తోంది…</span><br><br>
      <a class="map-link" id="mapLink" href="#" target="_blank">📌 Google Maps లో చూడండి</a>
    </div>

    <div class="card">
      <div class="info-box">
        <strong>ℹ️ How it works:</strong><br>
        Camera runs in your <strong>browser</strong>.<br>
        Detection uses <strong>face-api.js</strong> (runs locally).<br>
        Server only triggers <strong>Twilio calls</strong>.<br><br>
        <strong>📞 Alert:</strong> Telugu + English Voice Calls
      </div>
    </div>
  </div>
</div>

<audio id="alarmAudio" loop src="https://www.soundjay.com/buttons/sounds/beep-07a.mp3"></audio>

<script>
const THRESHOLD = {{ threshold }};
let eyeClosedFrames = 0;
let alertSent       = false;
let alarmPlaying    = false;
const MODEL_URL     = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model';

// ===== Load face-api.js Models =====
async function loadModels() {
  try {
    await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
    await faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_URL);
    document.getElementById('statusText').textContent = '✅ Ready — Start Camera';
    document.getElementById('statusText').className   = 'status-live';
    document.getElementById('startBtn').disabled      = false;
  } catch(e) {
    console.error(e);
    document.getElementById('statusText').textContent = '❌ Model load failed. Reload page.';
  }
}

// ===== Start Webcam =====
async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const video  = document.getElementById('video');
    video.srcObject = stream;
    video.onloadedmetadata = () => {
      const canvas    = document.getElementById('overlay');
      canvas.width    = video.videoWidth;
      canvas.height   = video.videoHeight;
      runDetection(video, canvas);
    };
    document.getElementById('startBtn').disabled      = true;
    document.getElementById('startBtn').textContent   = '📷 Camera Active';
    document.getElementById('statusText').textContent = 'LIVE ✔';
    document.getElementById('statusText').className   = 'status-live';
  } catch(e) {
    alert('❌ Camera access denied. Please allow camera in your browser and reload.');
  }
}

// ===== Detection Loop =====
async function runDetection(video, canvas) {
  const ctx     = canvas.getContext('2d');
  const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });

  async function detect() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (video.readyState >= 2) {
      const result = await faceapi.detectSingleFace(video, options).withFaceLandmarks(true);

      if (result) {
        const lm       = result.landmarks;
        const leftEye  = lm.getLeftEye();
        const rightEye = lm.getRightEye();
        const avgEAR   = (getEAR(leftEye) + getEAR(rightEye)) / 2;

        // Draw face rectangle
        const b = result.detection.box;
        ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 2;
        ctx.strokeRect(b.x, b.y, b.width, b.height);

        // Draw eye contours
        const eyeColor = avgEAR < 0.22 ? '#ef4444' : '#22c55e';
        drawEyeContour(ctx, leftEye,  eyeColor);
        drawEyeContour(ctx, rightEye, eyeColor);

        if (avgEAR < 0.22) {
          eyeClosedFrames++;
        } else {
          if (eyeClosedFrames > 0) eyeClosedFrames--;
          if (eyeClosedFrames === 0 && alertSent) resetAlert();
        }
      } else {
        if (eyeClosedFrames > 0) eyeClosedFrames--;
      }

      updateUI(!!result);

      if (eyeClosedFrames >= THRESHOLD && !alertSent) {
        alertSent = true;
        triggerAlert();
      }
    }

    requestAnimationFrame(detect);
  }

  detect();
}

// ===== Eye Aspect Ratio (EAR) =====
function getEAR(eye) {
  const A = dist(eye[1], eye[5]);
  const B = dist(eye[2], eye[4]);
  const C = dist(eye[0], eye[3]);
  return (A + B) / (2.0 * C);
}
function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}
function drawEyeContour(ctx, eye, color) {
  ctx.beginPath();
  eye.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
  ctx.closePath();
  ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
}

// ===== UI Update =====
function updateUI(faceFound) {
  const pct = Math.min((eyeClosedFrames / THRESHOLD) * 100, 100);
  const bar = document.getElementById('frameBar');
  bar.style.width      = pct + '%';
  bar.style.background = pct > 70 ? '#ef4444' : pct > 40 ? '#f59e0b' : '#22c55e';
  document.getElementById('frameCount').textContent = `${eyeClosedFrames} / ${THRESHOLD}`;

  const st = document.getElementById('statusText');
  if (eyeClosedFrames >= THRESHOLD) {
    st.textContent = '⚠ నిద్రపోతున్నారు! DROWSY!';
    st.className   = 'status-drowsy';
  } else if (faceFound) {
    st.textContent = 'LIVE ✔';
    st.className   = 'status-live';
  } else {
    st.textContent = 'చూస్తున్నాను... Watching...';
    st.className   = 'status-loading';
  }
}

// ===== Alert =====
function triggerAlert() {
  document.getElementById('callBadge').style.display = 'block';
  document.getElementById('alarmAudio').play().catch(() => {});
  alarmPlaying = true;
  fetch('/drowsy_alert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drowsy: true })
  });
}
function resetAlert() {
  alertSent    = false;
  alarmPlaying = false;
  const a = document.getElementById('alarmAudio');
  a.pause(); a.currentTime = 0;
  document.getElementById('callBadge').style.display = 'none';
  fetch('/drowsy_alert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drowsy: false })
  });
}

// ===== GPS =====
function startGPS() {
  if (!navigator.geolocation) return;
  navigator.geolocation.watchPosition(pos => {
    const lat = pos.coords.latitude.toFixed(6);
    const lon = pos.coords.longitude.toFixed(6);
    const acc = Math.round(pos.coords.accuracy);
    document.getElementById('gpsBadge').textContent = '✅ GPS యాక్టివ్';
    document.getElementById('gpsBadge').className   = 'gps-badge gps-ok';
    document.getElementById('locText').textContent  = `Lat: ${lat}, Lon: ${lon} (±${acc}m)`;
    document.getElementById('mapLink').href         = `https://maps.google.com/?q=${lat},${lon}`;
    fetch('/update_location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lon, accuracy: acc })
    });
  }, () => {
    document.getElementById('locText').textContent  = 'GPS అనుమతి తిరస్కరించబడింది';
    document.getElementById('gpsBadge').textContent = '❌ GPS లేదు';
    document.getElementById('gpsBadge').className   = 'gps-badge gps-wait';
  }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 });
}

window.addEventListener('load', () => {
  loadModels();
  startGPS();
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
