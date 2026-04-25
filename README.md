# 🚗 Driver Drowsiness Detection System

> Real-time AI-based driver drowsiness detection with Telugu & English voice alerts using OpenCV and Twilio.

---

## 📌 Project Overview

This system monitors a driver's eye movements in real-time using a webcam or IP camera. When drowsiness is detected, it:
- Triggers a visual alert on the dashboard
- Plays an alarm (on Windows)
- Sends **Telugu + English voice calls** to the driver and family via Twilio
- Shares the **driver's live GPS location** in the call

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python + Flask | Backend web server |
| OpenCV (Haar Cascade) | Face & eye detection |
| Twilio Voice API | Telugu + English phone calls |
| HTML / CSS / JS | Live dashboard UI |
| GPS (Browser API) | Real-time location tracking |
| ngrok | Local to public URL sharing |

---

## 📁 Project Structure

```
driver-drowsiness/
│
├── app.py                # Main Flask application
├── requirements.txt      # Python dependencies
├── Procfile              # Render deployment config
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

---

## ⚙️ Setup & Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/YOUR-USERNAME/driver-drowsiness.git
cd driver-drowsiness
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup environment variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env and fill in your Twilio credentials
```

### 4. Run the app
```bash
python app.py
```

### 5. Open browser
```
http://localhost:5000
```

---

## 📱 IP Camera Setup (Optional)

To use your Android phone as a camera:
1. Install **IP Webcam** app (Google Play Store — free)
2. Open app → scroll down → tap **Start Server**
3. Note the URL e.g. `http://192.168.1.5:8080`
4. Add to `.env`:
   ```
   IP_CAM_URL=http://192.168.1.5:8080/video
   ```

---

## 🌐 Share Publicly with ngrok

```bash
# Install ngrok
pip install pyngrok

# Run your app first
python app.py

# In another terminal
ngrok http 5000
```
Copy the `https://xxxx.ngrok-free.app` URL and share it!

---

## ☁️ Deploy on Render (Free)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Add Environment Variables (from your `.env` file)
5. Click **Deploy**

---

## 🚨 How Drowsiness Detection Works

```
Camera → Frame Capture
       → Face Detection (Haar Cascade)
       → Eye Detection (within face region)
       → If eyes closed for 20+ frames → DROWSY
       → Alarm + Voice Call triggered
```

---

## 📞 Voice Call Content

| Recipient | Language | Message |
|---|---|---|
| Driver | Telugu | Drowsiness warning, stop vehicle |
| Driver | English | Vehicle number + GPS location |
| Family | Telugu | Emergency alert |
| Family | English | Vehicle number + location |

---



## 📄 License

This project is for educational purposes.
