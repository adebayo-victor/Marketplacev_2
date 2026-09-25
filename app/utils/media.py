import os
import time
from werkzeug.utils import secure_filename
from flask import current_app

def upload_image(file, subfolder='products') -> str:
    """
    Intelligent uploader:
    1. Checks if Cloudinary is configured via environment variables.
    2. If configured, uploads directly to Cloudinary CDN and returns secure HTTPS URL.
    3. If not, safely falls back to saving in app/static/uploads/<subfolder>/.
    """
    if not file or file.filename == '':
        return None

    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')

    # 1. Cloudinary Upload (Production CDN)
    if cloud_name and api_key and api_secret:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )
            
            upload_result = cloudinary.uploader.upload(
                file,
                folder=f"marketplace/{subfolder}",
                resource_type="auto"
            )
            return upload_result.get('secure_url')
        except Exception as e:
            print(f"Cloudinary upload failed, falling back to local: {e}")

    # 2. Local Fallback (Development)
    filename = secure_filename(file.filename)
    dest_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(dest_folder, exist_ok=True)
    
    unique_filename = f"{int(time.time())}_{filename}"
    file.save(os.path.join(dest_folder, unique_filename))
    return unique_filename


def resolve_media_url(image_value: str, subfolder='products') -> str:
    """
    Returns the appropriate URL for an image:
    - If it's already a full Cloudinary URL (starts with http), returns it as-is.
    - If it's a local filename, resolves via static uploads folder.
    """
    if not image_value:
        return ''
    if image_value.startswith('http://') or image_value.startswith('https://'):
        return image_value
    return f"/static/uploads/{subfolder}/{image_value}"
