import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Security Key (replace with an environment variable in production)
    SECRET_KEY = os.environ.get('SECRET_KEY', 'marketplace-dev-key-change-in-production-2026')
    
    # SQLite Database location
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(BASE_DIR, 'marketplace.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder for product images, logos, and ad banners
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    
    # Allowed image formats
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
