import os
import shutil
from datetime import datetime
from config import BASE_DIR

def perform_db_backup(max_backups: int = 7) -> str:
    """
    Creates a timestamped snapshot of marketplace.db in /backups/
    and keeps only the most recent `max_backups` copies.
    """
    db_path = os.path.join(BASE_DIR, 'marketplace.db')
    backup_dir = os.path.join(BASE_DIR, 'backups')
    
    if not os.path.exists(db_path):
        return "Source database does not exist yet."

    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"marketplace_backup_{timestamp}.db"
    backup_dest = os.path.join(backup_dir, backup_filename)

    # Copy database file safely
    shutil.copy2(db_path, backup_dest)

    # Rotate old backups: keep only the newest `max_backups`
    all_backups = sorted(
        [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith('marketplace_backup_')],
        key=os.path.getmtime
    )

    while len(all_backups) > max_backups:
        oldest_backup = all_backups.pop(0)
        try:
            os.remove(oldest_backup)
        except OSError:
            pass

    return backup_filename
