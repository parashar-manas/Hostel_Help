#!/usr/bin/env python3
"""
Hostel Assistant Chatbot – Modern redesigned UI with warm pastels.

Layout:
- Top: NOTICE BOARD (horizontal scroll)
- Main: CHATBOX (full width, modern design)
- Bottom: Quick info cards

Theme:
- Warm pastels with proper contrast
- Clean, modern design
- Removed details card for streamlined experience

Run locally:
  pip install flask google-generativeai python-dotenv
  export GEMINI_API_KEY=YOUR_KEY   # or set in .env
  python app.py
Then open http://127.0.0.1:5000/

On Vercel:
- Add a `vercel.json` pointing to this file.
- Vercel will call the `handler()` function.
"""

import os
import re
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path

from flask import Flask, request, jsonify, g, render_template_string
import google.generativeai as genai


# ------------------------- Config -------------------------
APP_NAME = "Hostel Assistant"
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY") or "AIzaSyAmpVKhIHj6x2pPxOJp9PbDrgtYs9gTFoM"  # ⚠️ Demo only. Replace for production.

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not configured.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

DB_PATH = Path("hostel_assistant.db")

# ------------------------- App -------------------------
app = Flask(__name__)

# ------------------------- DB Helpers -------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS complaints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  room TEXT,
  contact TEXT,
  category TEXT,
  details TEXT,
  status TEXT DEFAULT 'Open',
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS announcements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT,
  body TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS mess_menu (
  day TEXT PRIMARY KEY,
  breakfast TEXT,
  lunch TEXT,
  dinner TEXT
);

CREATE TABLE IF NOT EXISTS faqs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  question TEXT UNIQUE,
  answer TEXT
);

DELETE FROM faqs
WHERE id NOT IN (
  SELECT MIN(id)
  FROM faqs
  GROUP BY question
);

CREATE TABLE IF NOT EXISTS room_assignments (
  room_number TEXT PRIMARY KEY,
  student_name TEXT,
  contact TEXT,
  floor INTEGER,
  block TEXT
);

CREATE TABLE IF NOT EXISTS hostel_info (
  key TEXT PRIMARY KEY,
  value TEXT,
  description TEXT
);
"""

SEED_SQL = [
    # Complete weekly mess menu
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Monday", "Poha & Tea", "Dal Fry, Jeera Rice, Salad", "Roti, Mix Veg, Kheer")),
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Tuesday", "Idli Sambhar & Coffee", "Rajma Chawal, Pickle", "Roti, Paneer Butter Masala, Rice")),
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Wednesday", "Upma & Tea", "Chole Puri, Onion Salad", "Veg Pulao, Raita, Papad")),
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Thursday", "Aloo Paratha & Curd", "Kadhi Chawal, Pickle", "Roti, Aloo Gobi, Dal")),
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Friday", "Bread Sandwich & Tea", "Sambhar Rice, Coconut Chutney", "Roti, Chicken Curry/Paneer Makhani")),
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Saturday", "Puri Bhaji & Tea", "Veg Biryani, Boiled Egg, Raita", "Roti, Dal Tadka, Jeera Rice")),
    ("INSERT OR IGNORE INTO mess_menu(day,breakfast,lunch,dinner) VALUES (?,?,?,?)",
     ("Sunday", "Dosa Sambhar & Coffee", "Pav Bhaji, Butter", "Roti, Veg Kofta, Rice")),

    # Announcements
    ("INSERT INTO announcements(title, body, created_at) VALUES (?,?,?)",
     ("Water Filter Maintenance", "2nd-floor RO will be serviced today 2–4 PM. Use ground floor dispenser.", datetime.now().isoformat(timespec='seconds'))),
    ("INSERT INTO announcements(title, body, created_at) VALUES (?,?,?)",
     ("Power Backup Drill", "Brief generator test at 7:30 PM. Expect 2-minute switchover.", datetime.now().isoformat(timespec='seconds'))),
    ("INSERT INTO announcements(title, body, created_at) VALUES (?,?,?)",
     ("Laundry Schedule", "Laundry pickup: Mon/Wed/Fri at 9 AM. Return: Next day 5 PM.", datetime.now().isoformat(timespec='seconds'))),
     ("INSERT INTO announcements(title, body, created_at) VALUES (?,?,?)",
     ("Room Inspection", "Weekly room inspection on Saturday 11 AM. Please keep rooms tidy.", datetime.now().isoformat(timespec='seconds'))),
("INSERT INTO announcements(title, body, created_at) VALUES (?,?,?)",
     ("Study Hall Extension", "Study hall will remain open till midnight during exam week.", datetime.now().isoformat(timespec='seconds'))),

    # Comprehensive FAQs
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("What are visitor timings?", "Visitors are allowed 5–7 PM on weekdays, 10 AM–1 PM on Sundays. Valid ID required at gate.")),
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("Who is the warden?", "Ms. Priya Sharma. Contact: +91-98xxxxxx01, Office: Ground floor, 8 AM–6 PM.")),
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("What are mess timings?", "Breakfast: 7:30-9:30 AM, Lunch: 12:30-2:30 PM, Dinner: 7:30-9:30 PM")),
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("WiFi password?", "HostelWiFi2024. Speed: 50 Mbps. Contact IT desk for issues.")),
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("Laundry service?", "Pickup: Mon/Wed/Fri 9 AM. Return: Next day 5 PM. ₹50 per load.")),
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("Medical emergency?", "Call security: 9876543210. Nearest hospital: City General (2 km). First aid: Warden office.")),
    ("INSERT INTO faqs(question, answer) VALUES (?,?)",
     ("Room maintenance?", "Submit complaint via assistant or warden office. Electrical: 24hrs, Plumbing: Same day.")),

    # Sample room assignments
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("101", "Priya Singh", "+91-9876543201", 1, "A")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("102", "Anita Sharma", "+91-9876543202", 1, "A")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("103", "Meera Patel", "+91-9876543203", 1, "A")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("201", "Kavya Reddy", "+91-9876543204", 2, "A")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("202", "Sneha Gupta", "+91-9876543205", 2, "A")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("26", "Riya Jain", "+91-9876543206", 1, "B")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("301", "Divya Kumar", "+91-9876543207", 3, "A")),
    ("INSERT OR IGNORE INTO room_assignments(room_number, student_name, contact, floor, block) VALUES (?,?,?,?,?)",
     ("302", "Pooja Agarwal", "+91-9876543208", 3, "A")),

    # Hostel general information
    ("INSERT OR IGNORE INTO hostel_info(key, value, description) VALUES (?,?,?)",
     ("total_rooms", "150", "Total number of rooms in hostel")),
    ("INSERT OR IGNORE INTO hostel_info(key, value, description) VALUES (?,?,?)",
     ("total_floors", "4", "Number of floors")),
    ("INSERT OR IGNORE INTO hostel_info(key, value, description) VALUES (?,?,?)",
     ("mess_capacity", "200", "Maximum mess seating capacity")),
    ("INSERT OR IGNORE INTO hostel_info(key, value, description) VALUES (?,?,?)",
     ("warden_office", "Ground Floor, Block A", "Warden office location")),
    ("INSERT OR IGNORE INTO hostel_info(key, value, description) VALUES (?,?,?)",
     ("security_number", "9876543210", "24x7 security contact")),
]

def init_db():
    db = get_db()
    db.executescript(SCHEMA_SQL)
    for sql, params in SEED_SQL:
        try:
            db.execute(sql, params)
        except sqlite3.IntegrityError:
            pass
    db.commit()

with app.app_context():
    init_db()

# ------------------------- Utility -------------------------

def get_complete_menu(db):
    rows = db.execute("""
        SELECT * FROM mess_menu
        ORDER BY CASE day
          WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
          WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
          WHEN 'Sunday' THEN 7 END
    """).fetchall()
    return [dict(row) for row in rows]

def get_room_info(db, room_number=None):
    if room_number:
        row = db.execute("SELECT * FROM room_assignments WHERE room_number = ?", (str(room_number),)).fetchone()
        return dict(row) if row else None
    else:
        rows = db.execute("SELECT * FROM room_assignments ORDER BY CAST(room_number AS INTEGER)").fetchall()
        return [dict(row) for row in rows]

def get_hostel_info(db):
    rows = db.execute("SELECT * FROM hostel_info").fetchall()
    return {row['key']: row['value'] for row in rows}

def today_menu(db):
    day = datetime.now().strftime('%A')
    row = db.execute("SELECT * FROM mess_menu WHERE day=?", (day,)).fetchone()
    if not row:
        return {"day": day, "breakfast": "TBD", "lunch": "TBD", "dinner": "TBD"}
    return dict(row)

def get_announcements(db, limit=5):
    rows = db.execute("SELECT * FROM announcements ORDER BY datetime(created_at) DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]

def get_faqs(db):
    rows = db.execute("SELECT question, answer FROM faqs").fetchall()
    return [dict(r) for r in rows]

INTENT_SCHEMA = {
    "intents": [
        {"code": "MESS_INFO", "desc": "Ask about mess timings or today's menu"},
        {"code": "FACILITY_UPDATE", "desc": "Ask about outages or announcements"},
        {"code": "COMPLAINT_REGISTRATION", "desc": "Register a complaint"},
        {"code": "FAQ", "desc": "Ask general hostel FAQs"},
        {"code": "GENERIC", "desc": "Small talk or other"}
    ],
    "complaint_categories": ["Electricity", "Plumbing", "Cleanliness", "Security", "Other"],
}

SYSTEM_PROMPT = (
    "You are 'Hostel Assistant', a helpful AI for a women's hostel. "
    "You have COMPLETE information about mess menus (all 7 days), room assignments, and hostel facilities. "
    "Classify the user message and provide a SINGLE comprehensive answer using the provided CONTEXT. "
    "For COMPLAINT_REGISTRATION: extract 'category' and 'details'. If you have ALL needed info (room, issue type, details), set needs_followup=false. "
    "NEVER ask for information that was already provided in the conversation or context. "
    "CRITICAL: Return ONLY ONE valid JSON object with: intent, answer, needs_followup, slots. "
    "Do NOT include markdown, backticks, or extra formatting. "
    "Example: {\"intent\":\"MESS_INFO\",\"answer\":\"Saturday dinner: Roti, Dal Tadka, Jeera Rice\",\"needs_followup\":false,\"slots\":{}}"
)

def run_gemini_intent(message: str, context: dict, user_info: dict = None) -> dict:
    # Include user info in context if available
    enhanced_context = context.copy()
    if user_info:
        enhanced_context["user_profile"] = user_info
    
    prompt = {
        "role": "user",
        "parts": [{
            "text": (
                f"SYSTEM\n{SYSTEM_PROMPT}\n\n"
                f"INTENT_SCHEMA\n{json.dumps(INTENT_SCHEMA, ensure_ascii=False)}\n\n"
                f"CONTEXT (JSON)\n{json.dumps(enhanced_context, ensure_ascii=False)}\n\n"
                f"USER_MESSAGE\n{message}\n\n"
                "Respond ONLY with valid JSON. Do not include any markdown, code blocks, or extra text."
            )
        }]
    }
    try:
        resp = model.generate_content(prompt)
        raw = resp.text or "{}"
    except Exception:
        return {
            "intent": "GENERIC",
            "answer": "I'm having trouble reaching the AI right now. Please try again in a moment.",
            "needs_followup": False,
            "slots": {}
        }

    cleaned = raw.strip()

    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        json_lines, in_json = [], False
        for line in lines:
            if line.startswith('```'):
                if in_json: break
                in_json = True
                continue
            if in_json:
                json_lines.append(line)
        cleaned = '\n'.join(json_lines).strip()

    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)

    try:
        json_text = json_match.group(0) if json_match else cleaned
        payload = json.loads(json_text)
    except Exception:
        answer_text = cleaned.replace('```json', '').replace('```', '').strip()
        payload = {
            "intent": "GENERIC",
            "answer": answer_text if answer_text else "I understand your message but had trouble processing it. Could you please rephrase?",
            "needs_followup": False,
            "slots": {}
        }

    payload.setdefault("intent", "GENERIC")
    payload.setdefault("answer", "")
    payload.setdefault("needs_followup", False)
    payload.setdefault("slots", {})

    if not payload.get("answer"):
        if payload.get("intent") == "COMPLAINT_REGISTRATION":
            payload["answer"] = "I understand you want to register a complaint. Could you please provide more details?"
        else:
            payload["answer"] = "I received your message but need more information to help you properly."

    return payload

# ------------------------- API -------------------------

@app.get("/api/complaints")
def api_complaints():
    contact = request.args.get("contact")
    room = request.args.get("room")
    q = "SELECT id, category, details, status, created_at FROM complaints"
    params, clauses = [], []
    if contact:
        clauses.append("contact = ?"); params.append(contact)
    if room:
        clauses.append("room = ?"); params.append(room)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY id DESC LIMIT 50"
    rows = get_db().execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])

# ------------------------- Front-end (Modern Design) -------------------------
INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Hostel Assistant</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      /* Warm pastel palette with proper contrast */
      --bg-primary: #fefcf9;
      --bg-secondary: #ffffff;
      --bg-tertiary: #faf8f5;
      --bg-accent: #f8f4f0;
      
      --text-primary: #2d2a26;
      --text-secondary: #5d5954;
      --text-muted: #8b8680;
      --text-light: #a8a39e;
      
      --accent-peach: #ffd7cc;
      --accent-sage: #d4e5d4;
      --accent-lavender: #e6d7ff;
      --accent-cream: #fff5e6;
      --accent-blush: #ffe0e6;
      
      --border-light: #f0ebe6;
      --border-medium: #e5ddd5;
      --border-strong: #d9cfc4;
      
      --shadow-soft: 0 2px 12px rgba(45, 42, 38, 0.04);
      --shadow-medium: 0 8px 32px rgba(45, 42, 38, 0.08);
      --shadow-strong: 0 16px 48px rgba(45, 42, 38, 0.12);
      
      --radius-sm: 8px;
      --radius-md: 16px;
      --radius-lg: 24px;
      --radius-xl: 32px;
      
      --gradient-warm: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-tertiary) 100%);
    }

    * { 
      box-sizing: border-box; 
      margin: 0; 
      padding: 0; 
    }
    
    html, body { 
      height: 100vh;
      background: var(--gradient-warm);
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif; 
      color: var(--text-primary);
      overflow-x: hidden; /* Allow vertical scroll */
      font-feature-settings: "ss01", "ss02";
    }

    .main-container {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px;
      gap: 16px;
    }

    /* Header */
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 20px 32px;
      background: var(--bg-secondary);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-soft);
      backdrop-filter: blur(20px);
      border: 1px solid var(--border-light);
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo-icon {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--accent-peach), var(--accent-blush));
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 800;
      color: var(--text-primary);
    }

    .logo-text {
      font-size: 24px;
      font-weight: 800;
      background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .status-badge {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: var(--accent-sage);
      border-radius: 50px;
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      background: #22c55e;
      border-radius: 50%;
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }

    /* Notice Board */
    .notice-section {
      background: var(--bg-secondary);
      border-radius: var(--radius-lg);
      padding: 24px;
      box-shadow: var(--shadow-soft);
      border: 1px solid var(--border-light);
      overflow: hidden;
    }

    .section-title {
      font-size: 18px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title-icon {
      width: 20px;
      height: 20px;
      background: var(--accent-lavender);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
    }

    .notice-scroll {
      display: flex;
      gap: 16px;
      overflow-x: auto;
      padding: 4px 0;
      scroll-behavior: smooth;
    }

    .notice-scroll::-webkit-scrollbar {
      height: 4px;
    }

    .notice-card {
      min-width: 280px;
      background: linear-gradient(135deg, var(--accent-cream), var(--accent-peach));
      border-radius: var(--radius-md);
      padding: 20px;
      border: 1px solid var(--border-medium);
      flex-shrink: 0;
    }

    .notice-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 8px;
    }

    .notice-body {
      font-size: 14px;
      color: var(--text-secondary);
      line-height: 1.5;
    }

    @keyframes scroll-notices {
      0% { transform: translateX(0); }
      100% { transform: translateX(-100%); }
    }

    /* Chat Section */
    .chat-section {
      flex: 1;
      min-height: 400px;
      background: var(--bg-secondary);
      border-radius: var(--radius-lg);
      display: flex;
      flex-direction: column;
      box-shadow: var(--shadow-medium);
      border: 1px solid var(--border-light);
      overflow: hidden;
    }

    .chat-header {
      padding: 20px 24px;
      border-bottom: 1px solid var(--border-light);
      background: var(--bg-tertiary);
    }

    .chat-messages {
      flex: 1;
      padding: 24px;
      overflow-y: auto;
      scroll-behavior: smooth;
      min-height: 300px;
      max-height: 400px;
    }

    .message {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
      animation: fadeInUp 0.3s ease-out;
    }

    .message.user {
      flex-direction: row-reverse;
    }

    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      font-weight: 700;
      flex-shrink: 0;
      position: relative;
    }

    .avatar.bot {
      background: linear-gradient(135deg, var(--accent-sage), var(--accent-lavender));
      color: var(--text-primary);
    }

    .avatar.user {
      background: linear-gradient(135deg, var(--accent-peach), var(--accent-blush));
      color: var(--text-primary);
    }

    .message-bubble {
      max-width: 70%;
      padding: 16px 20px;
      border-radius: var(--radius-md);
      font-size: 15px;
      line-height: 1.6;
      box-shadow: var(--shadow-soft);
    }

    .message.bot .message-bubble {
      background: var(--bg-tertiary);
      border: 1px solid var(--border-light);
      color: var(--text-primary);
    }

    .message.user .message-bubble {
      background: linear-gradient(135deg, var(--accent-peach), var(--accent-cream));
      border: 1px solid var(--border-medium);
      color: var(--text-primary);
    }

    .typing-indicator {
      display: flex;
      gap: 4px;
      padding: 8px 0;
    }

    .typing-dot {
      width: 8px;
      height: 8px;
      background: var(--text-muted);
      border-radius: 50%;
      animation: typing 1.5s ease-in-out infinite;
    }

    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes typing {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-10px); }
    }

    /* Input Area */
    .chat-input {
      padding: 20px 24px;
      border-top: 1px solid var(--border-light);
      background: var(--bg-tertiary);
    }

    .input-container {
      display: flex;
      gap: 12px;
      align-items: flex-end;
    }

    .message-input {
      flex: 1;
      border: 1px solid var(--border-medium);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      background: var(--bg-secondary);
      font-family: inherit;
      font-size: 15px;
      line-height: 1.5;
      color: var(--text-primary);
      resize: none;
      min-height: 50px;
      max-height: 120px;
      outline: none;
      transition: all 0.2s ease;
    }

    .message-input:focus {
      border-color: var(--accent-peach);
      box-shadow: 0 0 0 4px rgba(255, 215, 204, 0.2);
      background: var(--bg-secondary);
    }

    .send-button {
      width: 50px;
      height: 50px;
      border: none;
      border-radius: var(--radius-md);
      background: linear-gradient(135deg, var(--accent-peach), var(--accent-blush));
      color: var(--text-primary);
      font-size: 18px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .send-button:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-medium);
    }

    .send-button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    /* Info Cards */
    .info-section {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 16px;
    }

    .info-card {
      background: var(--bg-secondary);
      border-radius: var(--radius-md);
      padding: 20px;
      box-shadow: var(--shadow-soft);
      border: 1px solid var(--border-light);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .info-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-medium);
    }

    .info-card-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .info-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 12px;
    }

    .info-item {
      text-align: center;
      padding: 12px;
      background: var(--bg-accent);
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-light);
    }

    .info-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }

    .info-value {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
    }

    /* Quick Actions */
    .quick-actions {
      display: flex;
      gap: 12px;
      margin-top: 16px;
      flex-wrap: wrap;
    }

    .quick-action {
      padding: 8px 16px;
      background: var(--accent-sage);
      border: 1px solid var(--border-medium);
      border-radius: 50px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary);
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .quick-action:hover {
      background: var(--accent-lavender);
      transform: translateY(-1px);
      box-shadow: var(--shadow-soft);
    }

    /* Success/Error States */
    .ticket-success {
      background: linear-gradient(135deg, var(--accent-sage), #bbf7d0);
      border: 1px solid #22c55e;
      border-radius: var(--radius-md);
      padding: 12px 16px;
      margin-top: 8px;
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Animations */
    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    /* Scrollbar Styling */
    ::-webkit-scrollbar {
      width: 6px;
    }

    ::-webkit-scrollbar-track {
      background: var(--bg-tertiary);
      border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb {
      background: var(--border-strong);
      border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
      background: var(--text-muted);
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .main-container {
        padding: 12px;
        gap: 12px;
      }

      .header {
        padding: 16px 20px;
      }

      .logo-text {
        font-size: 20px;
      }

      .notice-section,
      .chat-section {
        border-radius: var(--radius-md);
      }

      .chat-messages {
        padding: 16px;
      }

      .message-bubble {
        max-width: 85%;
        padding: 12px 16px;
      }

      .info-section {
        grid-template-columns: 1fr;
      }

      .quick-actions {
        justify-content: center;
      }
    }

    /* Focus States for Accessibility */
    .send-button:focus,
    .quick-action:focus {
      outline: 2px solid var(--accent-peach);
      outline-offset: 2px;
    }

    .message-input:focus {
      border-color: var(--accent-peach);
      box-shadow: 0 0 0 4px rgba(255, 215, 204, 0.2);
    }
  </style>
</head>
<body>
  <div class="main-container">
    <!-- Header -->
    <header class="header">
      <div class="logo">
        <div class="logo-icon">🏠</div>
        <div class="logo-text">Hostel Assistant</div>
      </div>
      <div class="status-badge">
        <div class="status-dot"></div>
        <span>Online</span>
      </div>
    </header>

    <!-- Notice Board -->
    <section class="notice-section">
      <div class="section-title">
        <div class="title-icon">📢</div>
        Notice Board
      </div>
      <div class="notice-scroll" id="notice-scroll">
        <!-- Notices will be populated here -->
      </div>
    </section>

    <!-- Chat Section -->
    <section class="chat-section">
      <div class="chat-header">
        <div class="section-title">
          <div class="title-icon">💬</div>
          Chat Assistant
        </div>
      </div>
      
      <div class="chat-messages" id="chat-messages">
        <!-- Messages will appear here -->
      </div>

      <div class="chat-input">
        <div class="input-container">
          <textarea 
            id="message-input" 
            class="message-input" 
            placeholder="Ask about mess timings, report issues, or chat with me..."
            rows="1"
          ></textarea>
          <button id="send-button" class="send-button">
            ↗️
          </button>
        </div>
        <div class="quick-actions">
          <div class="quick-action" onclick="sendQuickMessage('What\'s for lunch today?')">Today's Menu</div>
          <div class="quick-action" onclick="sendQuickMessage('What are the mess timings?')">Mess Timings</div>
          <div class="quick-action" onclick="sendQuickMessage('I want to register a complaint')">Report Issue</div>
          <div class="quick-action" onclick="sendQuickMessage('WiFi password')">WiFi Info</div>
        </div>
      </div>
    </section>

    <!-- Info Cards -->
    <section class="info-section">
      <div class="info-card">
        <div class="info-card-title">
          <div class="title-icon">🍽️</div>
          Today's Menu
        </div>
        <div class="info-grid" id="today-menu">
          <div class="info-item">
            <div class="info-label">Breakfast</div>
            <div class="info-value" id="today-breakfast">Loading...</div>
          </div>
          <div class="info-item">
            <div class="info-label">Lunch</div>
            <div class="info-value" id="today-lunch">Loading...</div>
          </div>
          <div class="info-item">
            <div class="info-label">Dinner</div>
            <div class="info-value" id="today-dinner">Loading...</div>
          </div>
          <div class="info-item">
            <div class="info-label">Day</div>
            <div class="info-value" id="today-day">Loading...</div>
          </div>
        </div>
      </div>

      <div class="info-card">
        <div class="info-card-title">
          <div class="title-icon">❓</div>
          Quick Help
        </div>
        <div id="quick-faqs">
          <!-- FAQ items will be populated here -->
        </div>
      </div>
    </section>
  </div>

<script>
// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const noticeScroll = document.getElementById('notice-scroll');

// Auto-resize textarea
messageInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// Add message to chat
function addMessage(text, sender = 'bot', isTicket = false) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}`;
  
  const avatar = document.createElement('div');
  avatar.className = `avatar ${sender}`;
  avatar.textContent = sender === 'user' ? 'You' : 'HA';
  
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  bubble.textContent = text;
  
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(bubble);
  
  if (isTicket) {
    const successDiv = document.createElement('div');
    successDiv.className = 'ticket-success';
    successDiv.innerHTML = '✅ Complaint registered successfully!';
    bubble.appendChild(successDiv);
  }
  
  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  
  return messageDiv;
}

// Show typing indicator
function showTyping() {
  const typingDiv = document.createElement('div');
  typingDiv.className = 'message bot typing-message';
  typingDiv.innerHTML = `
    <div class="avatar bot">HA</div>
    <div class="message-bubble">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;
  
  chatMessages.appendChild(typingDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  
  return typingDiv;
}

// Send message
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;
  
  messageInput.value = '';
  messageInput.style.height = 'auto';
  
  addMessage(text, 'user');
  sendButton.disabled = true;
  
  const typingIndicator = showTyping();
  
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: text,
        user: userInfo // Use global userInfo instead of calling getUserInfo()
      })
    });
    
    const data = await response.json();
    
    typingIndicator.remove();
    
    if (data.answer) {
      const isTicket = !!data.ticket_id;
      addMessage(data.answer, 'bot', isTicket);
    }
    
    // If it's a complaint registration and we need user info, prompt now
    if (data.intent === 'COMPLAINT_REGISTRATION' && data.needs_followup && !userInfo.prompted) {
      setTimeout(() => {
        getUserInfo();
      }, 1000);
    }
    
  } catch (error) {
    console.error('Error sending message:', error);
    typingIndicator.remove();
    addMessage('Sorry, I encountered an error. Please try again.', 'bot');
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
}

// Send quick message
function sendQuickMessage(message) {
  messageInput.value = message;
  sendMessage();
}

// Store user info globally to avoid repeated prompts
let userInfo = {
  name: localStorage.getItem('userName'),
  room: localStorage.getItem('userRoom'),
  contact: localStorage.getItem('userContact'),
  prompted: localStorage.getItem('userPrompted') === 'true'
};

// Get user info (only prompt once per session)
function getUserInfo() {
  // If we haven't prompted yet and don't have complete info, prompt now
  if (!userInfo.prompted && (!userInfo.name || !userInfo.room || !userInfo.contact)) {
    console.log('Prompting for user info...');
    
    if (!userInfo.name) {
      userInfo.name = prompt('Hi! Please enter your name for personalized assistance:');
      if (userInfo.name) localStorage.setItem('userName', userInfo.name);
    }
    
    if (!userInfo.room) {
      userInfo.room = prompt('Please enter your room number:');
      if (userInfo.room) localStorage.setItem('userRoom', userInfo.room);
    }
    
    if (!userInfo.contact) {
      userInfo.contact = prompt('Please enter your phone number or email:');
      if (userInfo.contact) localStorage.setItem('userContact', userInfo.contact);
    }
    
    userInfo.prompted = true;
    localStorage.setItem('userPrompted', 'true');
  }
  
  return userInfo;
}

// Load initial data
async function loadInitialData() {
  try {
    console.log('Loading initial data...');
    
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: '__context__'
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Received data:', data);
    
    const context = data._context || {};
    
    // Populate today's menu
    const todayMenu = context.today_menu || {};
    document.getElementById('today-day').textContent = todayMenu.day || 'Unknown';
    document.getElementById('today-breakfast').textContent = todayMenu.breakfast || 'TBD';
    document.getElementById('today-lunch').textContent = todayMenu.lunch || 'TBD';
    document.getElementById('today-dinner').textContent = todayMenu.dinner || 'TBD';
    
    // Populate announcements
    const announcements = context.announcements || [];
    console.log('Announcements:', announcements);
    
    if (announcements.length > 0) {
      noticeScroll.innerHTML = announcements.map(ann => `
        <div class="notice-card">
          <div class="notice-title">${ann.title}</div>
          <div class="notice-body">${ann.body}</div>
        </div>
      `).join('');
    } else {
      noticeScroll.innerHTML = '<div class="notice-card"><div class="notice-title">No announcements</div><div class="notice-body">Check back later for updates!</div></div>';
    }
    
    // Populate quick FAQs
    const faqs = context.faqs || [];
    const quickFaqs = document.getElementById('quick-faqs');
    
    if (faqs.length > 0) {
      quickFaqs.innerHTML = faqs.slice(0, 3).map(faq => `
        <div class="info-item" style="text-align: left; margin-bottom: 8px; cursor: pointer;" onclick="sendQuickMessage('${faq.question}')">
          <div class="info-label">${faq.question}</div>
        </div>
      `).join('');
    } else {
      quickFaqs.innerHTML = '<div class="info-item"><div class="info-label">FAQs loading...</div></div>';
    }
    
    console.log('Data populated successfully');
    
  } catch (error) {
    console.error('Error loading initial data:', error);
    
    // Set fallback data
    document.getElementById('today-day').textContent = 'Monday';
    document.getElementById('today-breakfast').textContent = 'Poha & Tea';
    document.getElementById('today-lunch').textContent = 'Dal Fry, Rice';
    document.getElementById('today-dinner').textContent = 'Roti, Mix Veg';
    
    noticeScroll.innerHTML = `
      <div class="notice-card">
        <div class="notice-title">Welcome!</div>
        <div class="notice-body">System is running. Data will load shortly.</div>
      </div>
    `;
    
    const quickFaqs = document.getElementById('quick-faqs');
    quickFaqs.innerHTML = `
      <div class="info-item" style="text-align: left; margin-bottom: 8px; cursor: pointer;" onclick="sendQuickMessage('What are mess timings?')">
        <div class="info-label">What are mess timings?</div>
      </div>
      <div class="info-item" style="text-align: left; margin-bottom: 8px; cursor: pointer;" onclick="sendQuickMessage('WiFi password?')">
        <div class="info-label">WiFi password?</div>
      </div>
    `;
  }
}

// Event listeners
sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
  console.log('App initializing...');
  
  try {
    await loadInitialData();
    console.log('Initial data loaded');
    
    // Only prompt for user info if it's the very first visit
    if (!userInfo.prompted) {
      getUserInfo();
    }
    
    // Add welcome message
    setTimeout(() => {
      const welcomeMsg = userInfo.name ? 
        `👋 Welcome back, ${userInfo.name}! How can I help you today?` :
        `👋 Welcome to Hostel Assistant! I'm here to help with mess info, complaints, facility updates, and general questions. How can I assist you today?`;
      addMessage(welcomeMsg);
    }, 500);
    
    messageInput.focus();
  } catch (error) {
    console.error('Initialization error:', error);
    addMessage("⚠️ Welcome! There was an issue loading some data, but I'm ready to chat. How can I help you?");
  }
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


# Provide a "context mode" when message == __context__ so the UI can hydrate
@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True)
    message = (data or {}).get("message", "").strip()
    user_meta = (data or {}).get("user", {})

    db = get_db()
    ctx = {
        "today_menu": today_menu(db),
        "complete_weekly_menu": get_complete_menu(db),
        "announcements": get_announcements(db),
        "faqs": get_faqs(db),
        "room_assignments": get_room_info(db),
        "hostel_info": get_hostel_info(db),
        "user_profile": user_meta
    }

    if message == "__context__":
        return jsonify({"_context": ctx})

    result = run_gemini_intent(message, ctx, user_meta)

    # Auto-create ticket if complaint is complete
    if result.get("intent") == "COMPLAINT_REGISTRATION" and not result.get("needs_followup"):
        slots = result.get("slots", {})
        category = slots.get("category") or "Other"
        details = slots.get("details") or ""
        name = user_meta.get("name") or None
        room = user_meta.get("room") or None
        contact = user_meta.get("contact") or None
        cur = db.execute(
            "INSERT INTO complaints(name, room, contact, category, details, created_at) VALUES (?,?,?,?,?,?)",
            (name, room, contact, category, details, datetime.now().isoformat(timespec='seconds')),
        )
        db.commit()
        ticket_id = cur.lastrowid
        result["ticket_id"] = ticket_id
        if "logged" not in (result.get("answer") or "").lower():
            ack = f"Your complaint has been logged (Ticket #{ticket_id}) under '{category}'. We will update you upon resolution."
            result["answer"] = (result.get("answer") or "").strip() + "\n\n" + ack

    return jsonify(result)

# ------------------------- Vercel Handler -------------------------
def handler(request, response=None):
    """Vercel entrypoint"""
    return app(request.environ, response.start_response)

# ------------------------- Local Run -------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

