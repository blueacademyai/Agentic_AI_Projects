import subprocess
import sys
import time
from multiprocessing import Process
import uvicorn
from fastapi_app import app
from pyngrok import ngrok
import os

FASTAPI_PORT = 8000
STREAMLIT_PORT = 8501

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=FASTAPI_PORT, reload=False)

def run_streamlit():
    subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
        "--server.port", str(STREAMLIT_PORT), "--server.address", "0.0.0.0"
    ])

# 🔑 Add your ngrok token here
ngrok.set_auth_token("32dJQKfHs5geoRx9KWjg2Iutk03_7PXV7oab74fFrW95G84Vf")

# Start FastAPI in a separate process
p1 = Process(target=run_fastapi, daemon=True)
p1.start()

# ⏳ Wait for FastAPI to boot
time.sleep(5)
fastapi_tunnel = ngrok.connect(FASTAPI_PORT, "http")
fastapi_url = fastapi_tunnel.public_url
print("🚀 FastAPI Public URL:", fastapi_url + "/docs")

# Pass FastAPI URL into Streamlit as an env var
os.environ["FASTAPI_URL"] = fastapi_url

# Start Streamlit
run_streamlit()

# ⏳ Wait for Streamlit
time.sleep(10)
streamlit_tunnel = ngrok.connect(STREAMLIT_PORT, "http")
print("💻 Streamlit Public URL:", streamlit_tunnel.public_url)

# Keep alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping...")
    p1.terminate()
