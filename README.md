# 🚑 CareRoute Desktop App  
### *AI-powered medical triage with location-based facility recommendations*

CareRoute is a desktop application built with **Python, PySide6, Google Gemini AI, and Google Maps APIs**.  
It provides a safe, user-friendly triage experience by combining:

- AI-generated urgency assessments  
- Hard-coded safety override rules  
- Real-time geolocation + facility search  
- A clean, modern desktop GUI  
- Local history tracking  

This project demonstrates how AI, rules-based logic, and maps services can integrate to support safer, more informed healthcare decisions.

---

## ✨ Features

### 🔹 AI Triage Engine (Gemini)
- Analyzes symptoms + optional vitals  
- Returns: **urgency level**, **severity score**, **medical explanation**, **red flags**  
- Always outputs JSON in a structured format  

### 🔹 Safety Rule Layer
Overrides Gemini if critical symptoms appear:
- Chest pain + breathing difficulty → **ER**
- Respiratory distress → **URGENT or ER**
- Fever ≥ 40°C → escalate recommendation  
Ensures conservative, safe outcomes.

### 🔹 Facility Recommendations (Google Maps)
- Converts user’s address → GPS coordinates  
- Searches nearby **ERs**, **urgent cares**, **clinics**, or **pharmacies**  
- Calculates real geographic distance using the Haversine formula  
- Provides clickable Google Maps navigation links  

### 🔹 Desktop UI (PySide6)
- Clean and responsive interface  
- Multi-page navigation (Home → Result → History)  
- Severity scale visualization  
- Scrollable facility and history lists  

### 🔹 Local History System
- Saves past triage results to `history.json`  
- Displays user history with timestamps, severity, and symptoms  
- Allows replaying past assessments  

---

## 🛠 Tech Stack

| Component | Technology |
|----------|------------|
| Desktop UI | PySide6 (Qt for Python) |
| AI Model | Google Gemini 2.5 Flash |
| Geolocation | Google Geocoding API |
| Facility Search | Google Places Nearby Search API |
| Language | Python 3 |
| Storage | Local JSON |
| Build Tool | Makefile |

---

# 📦 Installation Guide for CareRoute Desktop App

Follow these steps to install and run the CareRoute desktop application.

---

## 🔑 Step 0 — Get your API keys

### 0.1 — Get a Gemini API key (GEMINI_API_KEY)

1. Go to **Google AI Studio**:  
   https://aistudio.google.com  
2. Sign in with your Google account.  
3. In the left sidebar, click **API keys** (or “Get API Key”).  
4. Create a **new API key** for “Gemini API in Google AI Studio”.  
5. Copy the generated key → this will be your:  
   GEMINI_API_KEY 

---

### 0.2 — Get a Google Maps API key (GOOGLE_MAPS_API_KEY)

You’ll use **Google Cloud Console** for this.

1. Go to **Google Cloud Console**:  
   https://console.cloud.google.com  
2. Sign in with your Google account.  
3. Create a **new project** (or select an existing one).  
4. In the left menu, go to **APIs & Services → Library**.  
5. Enable the following APIs for your project:
   - **Geocoding API**
   - **Places API** (for nearby search / details)
6. Go to **APIs & Services → Credentials**.  
7. Click **“Create credentials” → “API key”**.  
8. Copy the generated key → this will be your:  
   GOOGLE_MAPS_API_KEY  
9. Click on the key to open settings and:
   - Under **API restrictions**, restrict it to at least:
     - Geocoding API  
     - Places API  
10. Make sure **billing is enabled** for your Google Cloud project, or the APIs may not work in production.

> Keep this key **secret**. Do not commit it to GitHub or share it publicly.

---

## **Step 1 — Create a `.env` file**

Inside the project folder, create a file named: **.env**

Add your API keys:

GEMINI_API_KEY= PUT KEY HERE

GOOGLE_MAPS_API_KEY= PUT KEY HERE

---

## **Step 2 — Build the virtual environment**

Run the following command in your terminal: **make build**

This will:

- Create the `.venv/` virtual environment  
- Install all dependencies  
- Prepare the application to run  

Expected output: Virtualenv ready at .venv

---

## Step 3 — Run the application

Start the desktop app with: **make run**

If successful, you will see: **Starting CareRoute desktop app...**

---

## Step 4 — (Optional) Build a standalone executable

If you want to package the application: **make package**

This generates:

- `dist/careroute` (macOS/Linux)  
- `dist/careroute.exe` (Windows)

---

## Step 5 — (Optional) Clean the project

To remove the virtual environment and build files: **make clean**

This removes:

- `.venv/`  
- `build/`  
- `dist/`  
- PyInstaller `.spec` files  

# To run the unit test
1. Install (if missing) coverage with `pip install coverage` (Or via other package manager of choice)
2. Add coverage to system parameters (This is usually NOT necessary unless the prompt suggests otherwise) 
3. Run `coverage run unit_test.py`
4. Wait for the test to conclude and run `coverage report` for statistics

## 👥 Contributors

- **Jiahao Hu**  
  *Project Manager / Backend Developer*  
  - Overall project coordination  
  - AI triage logic (Gemini integration + safety rules)  
  - Google Maps API integration and facility recommendation logic  

- **Yiguo Yu**  
  *GUI Developer*  
  - Desktop UI design and implementation (PySide6)  
  - User interaction flow and interface optimization  

- **Nofer Xue**  
  *Testing / GUI Developer*  
  - Functional testing and edge case validation  
  - Bug reporting and usability feedback  

- **Charles Yao**  
  *Backend Developer*  
  - Model API integration  
  - Voice Input devlopment