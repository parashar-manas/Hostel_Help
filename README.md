# Hostel Assistant Chatbot Using Retrained Google Gemini API
This project represents a domain-adapted AI chatbot for hostel management, built using Google’s Gemini API for natural language understanding and deployed with a clean, modern Flask-based web interface. Unlike a generic chatbot, this model has been fine-tuned on hostel-specific data (announcements, mess menus, complaints, FAQs), ensuring it provides highly accurate, context-aware, and production-ready responses.

Key Features:

1. Domain-Specific Fine-Tuning: The model was retrained with hostel-specific datasets, including announcements, menus, and complaint logs. This adaptation significantly improves accuracy and contextual relevance, making the system smarter and more reliable for real-world hostel scenarios.
2. Smart Announcement Board: A horizontally scrolling Notice Board that updates students with the latest hostel circulars and facility updates in real time.
3. Mess Menu Intelligence: Supports both daily and weekly mess menu queries. Automatically fetches meals based on the current date and time.
4. Complaint Management System: Users can register hostel-related complaints (plumbing, electricity, housekeeping, etc.). Complaints are stored in an SQLite database with auto-generated ticket IDs which enables future complaint tracking and resolution monitoring.
5. Interactive FAQs: The chatbot answers frequently asked hostel-related queries by fetching data directly from a structured database.
6. Natural Language Conversations: Powered by Gemini, the chatbot also engages in general-purpose conversation fallback when queries don’t match predefined intents.
7. Clean And Modern Web UI: Designed with pastel tones and intuitive layouts, including chatbox with Gemini-powered responses, quick info cards for key hostel details and scrolling announcements at the top.
8. Persistent Data With SQLite: Announcements, menus, FAQs, and complaints are stored in a lightweight SQLite DB, ensuring persistence across sessions.
9. Easy Deployment And Hosting: Works locally with Flask (python app.py). Also, fully deployed on Render for cloud access on https://hostel-help.onrender.com/.
