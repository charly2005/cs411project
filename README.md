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