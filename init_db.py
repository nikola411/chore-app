"""
Run once to initialise the database tables.

    python init_db.py
"""
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app import app
from models import db

with app.app_context():
    db.create_all()
    print("Database tables created. Open http://localhost:5000/members to add household members.")
