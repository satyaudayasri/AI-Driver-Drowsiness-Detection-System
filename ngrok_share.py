"""
ngrok_share.py — Run this to share your app publicly in seconds!

Usage:
    python ngrok_share.py

Requirements:
    pip install pyngrok
"""

import threading
import time
from pyngrok import ngrok
import subprocess
import sys


def start_flask():
    subprocess.run([sys.executable, "app.py"])


def main():
    print("=" * 50)
    print("🚀 Driver Drowsiness — ngrok Share Tool")
    print("=" * 50)

    # Start Flask in background thread
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Wait for Flask to start
    print("⏳ Starting Flask app...")
    time.sleep(3)

    # Open ngrok tunnel
    print("🌐 Opening ngrok tunnel...")
    tunnel = ngrok.connect(5000)
    public_url = tunnel.public_url

    print("\n" + "=" * 50)
    print(f"✅ Your app is LIVE at:")
    print(f"👉  {public_url}")
    print("=" * 50)
    print("\nShare this link with anyone!")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        ngrok.disconnect(public_url)
        ngrok.kill()


if __name__ == "__main__":
    main()
