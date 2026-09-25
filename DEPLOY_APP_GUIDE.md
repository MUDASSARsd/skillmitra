# 🏆 SIH Winning Deployment Playbook: SkillMitra App

To **win Smart India Hackathon (SIH)**, your deployment must succeed across **three critical scenarios**:
1. **Jury Booth Table (100% Offline):** When hall Wi-Fi drops, your app must run smoothly with zero latency.
2. **Jury's Smartphone Test (Zero Internet Hotspot):** When judges ask *"Can I test this on my phone right now?"*, they can connect and install the app on their phone.
3. **Public 24/7 Cloud App (100% Free):** For remote judges, pre-jury evaluations, or presentation slides.

---

## 🚀 Tier 1: 1-Click Native Desktop App (Jury Table / Offline)

You can launch SkillMitra directly as a **standalone desktop application** with no browser bars or tabs:

1. In the project folder, simply double-click:
   ```cmd
   LAUNCH_APP.bat
   ```
2. What happens automatically:
   - Starts the FastAPI AI engine in the background on port `8000`.
   - Opens the app in **standalone application window mode** (using Edge/Chrome `--app` engine).
   - Shows the clean, distraction-free desktop app window with its own taskbar icon.
   - Fully offline: 2,814 NQR qualifications, 11,222 eligibility routes, local audio, and sub-second deterministic recommendations.

---

## 📱 Tier 2: Instant Phone App Demo (Via Mobile Hotspot - 0 Internet Needed!)

Judges are always impressed when they can test the app on their own phone during the evaluation:

1. Turn on your mobile hotspot (laptop and phone connected to the same hotspot). **No active data/internet is required.**
2. Open Command Prompt on your laptop and find your local IP:
   ```cmd
   ipconfig
   ```
   Look for `IPv4 Address` (e.g. `192.168.43.15`).
3. Start the server allowing network access:
   ```cmd
   .\.venv\Scripts\python.exe -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
   ```
4. On the judge's phone (Android or iPhone), open Chrome or Safari and type:
   ```
   http://192.168.43.15:8000/app
   ```
5. Tap **"📲 Install App"** (or in Chrome: *Menu ➔ Install app / Add to Home screen*).
6. **Result:** An app icon named **SkillMitra** appears on their home screen like a native Play Store app!

---

## ☁️ Tier 3: 100% Free Cloud Deployment (Render.com)

To give judges a public URL (e.g. `https://skillmitra.onrender.com/app`) that anyone can open anywhere:

### Step 1: Push Project to GitHub
1. Create a repository on GitHub (e.g., `skillmitra`).
2. In this folder:
   ```bash
   git init
   git add .
   git commit -m "SkillMitra SIH Final Release"
   git branch -M main
   git remote add origin https://github.com/<your-username>/skillmitra.git
   git push -u origin main
   ```

### Step 2: Deploy Free on Render (Zero Credit Card Needed)
1. Go to [Render.com](https://render.com) and sign up for a **Free Account**.
2. Click **New +** ➔ **Web Service**.
3. Connect your GitHub repository.
4. Render will automatically detect the included [`render.yaml`](./render.yaml):
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free ($0/month)
5. Under **Environment Variables**, add:
   - `GEMINI_API_KEY`: *(Your free Google AI Studio API key)*
   - `SKILLMITRA_RUNTIME`: `cloud`
6. Click **Create Web Service**.
7. In ~3 minutes, your live URL is active (e.g., `https://skillmitra-xxxx.onrender.com/app`).

---

## 🎯 Jury Presentation Tips to Win SIH

1. **Highlight the Hybrid Edge:**
   - Explain to the jury: *"Most teams fail when the internet fails. SkillMitra is built with a dual-engine architecture: an ultra-fast offline core running local NQR vector mapping and local speech for rural connectivity, with seamless cloud neural TTS and Gemini flash-lite when connected."*
2. **Show Multilingual Story Understanding:**
   - Tell a full story in Hindi or Telugu: *"I passed 10th class, worked as an electrician for 2 years in Hyderabad, and want a job."*
   - Show how the AI extracts all 5 profile fields simultaneously in 1 turn, without getting stuck in counter-question loops.
3. **Show Ground Truth & Verifiable Evidence:**
   - Point to the bottom cards: Real NQR qualification codes, Skill India Digital course catalogue links, PM-AJAY GIA subsidy status, and actual active job postings.
