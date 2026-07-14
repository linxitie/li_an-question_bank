"""Create news-related tables"""
import sys
sys.stdout = open(sys.stdout.fileno(), 'w', buffering=1)  # line-buffered

print("Starting...", flush=True)

from app.core.database import engine, Base
print("Engine loaded", flush=True)

from app.models.models import NewsImage, NewsFavorite, NewsNote
print("Models loaded", flush=True)

Base.metadata.create_all(bind=engine)
print("Tables created successfully!", flush=True)
