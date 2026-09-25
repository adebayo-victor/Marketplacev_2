import os
import re
import time
from werkzeug.utils import secure_filename
from flask import current_app

def upload_image(file, subfolder='products') -> str:
    """Uploads image to Cloudinary CDN if credentials exist, otherwise saves locally."""
    if not file or file.filename == '':
        return None

    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')

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

    # Local Fallback
    filename = secure_filename(file.filename)
    dest_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(dest_folder, exist_ok=True)
    
    unique_filename = f"{int(time.time())}_{filename}"
    file.save(os.path.join(dest_folder, unique_filename))
    return unique_filename


def delete_image(image_url: str, subfolder='products'):
    """
    Cleans up storage: Deletes file from Cloudinary CDN or local disk 
    when a product or kiosk is removed.
    """
    if not image_url or image_url.startswith('default_'):
        return

    # 1. Cloudinary File Cleanup
    if 'res.cloudinary.com' in image_url:
        try:
            import cloudinary
            import cloudinary.uploader
            
            # Extract public_id from Cloudinary URL (e.g. marketplace/products/12345)
            match = re.search(r'/upload/(?:v\d+/)?(.+?)\.[a-zA-Z0-9]+$', image_url)
            if match:
                public_id = match.group(1)
                cloudinary.uploader.destroy(public_id)
                print(f"Cleaned up Cloudinary file: {public_id}")
        except Exception as e:
            print(f"Cloudinary delete error: {e}")
        return

    # 2. Local Disk Cleanup
    try:
        local_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder, image_url)
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"Cleaned up local file: {local_path}")
    except Exception as e:
        print(f"Local delete error: {e}")
