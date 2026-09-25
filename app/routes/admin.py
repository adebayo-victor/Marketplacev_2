import os
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, Store, Product, Order

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Restricts access to Master Admins only, with a first-time claim prompt if no admin exists."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            # Check if any admin exists in the system
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count == 0:
                flash('No Master Admin exists yet. You can claim Master access below.', 'warning')
                return redirect(url_for('admin.claim_master'))
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def overview():
    """Master Command Center: Platform vitals and kiosk registry."""
    total_merchants = User.query.count()
    total_kiosks = Store.query.count()
    total_orders = Order.query.count()
    
    # Calculate Average Kiosks Per Merchant
    avg_kiosks = round(total_kiosks / total_merchants, 2) if total_merchants > 0 else 0.0
    
    # Total platform visitor impressions
    total_views = db.session.query(db.func.sum(Store.views_count)).scalar() or 0

    kiosks = Store.query.order_by(Store.created_at.desc()).all()

    return render_template(
        'admin/overview.html',
        total_merchants=total_merchants,
        total_kiosks=total_kiosks,
        avg_kiosks=avg_kiosks,
        total_views=total_views,
        total_orders=total_orders,
        kiosks=kiosks
    )


@admin_bp.route('/kiosk/<int:store_id>/template', methods=['GET', 'POST'])
@admin_required
def edit_template(store_id):
    """In-browser HTML Template Inspector & Code Editor for any kiosk."""
    store = Store.query.get_or_404(store_id)

    if request.method == 'POST':
        raw_html = request.form.get('custom_html', '')
        store.custom_html = raw_html
        db.session.commit()
        flash(f'HTML template for "{store.name}" updated successfully!', 'success')
        return redirect(url_for('admin.edit_template', store_id=store.id))

    return render_template('admin/template_editor.html', store=store)


@admin_bp.route('/system/env', methods=['GET', 'POST'])
@admin_required
def env_manager():
    """Secure Secrets & Environment Variables Manager (Writes directly to .env on disk)."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    
    # Tracked secret keys
    # In app/routes/admin.py, update target_keys to:
    target_keys = [
        'SECRET_KEY',
        'CLOUDINARY_CLOUD_NAME',
        'CLOUDINARY_API_KEY',
        'CLOUDINARY_API_SECRET',
        'AI_API_KEY',
        'OPENROUTER_API_KEY'  # <--- Added
    ]

    if request.method == 'POST':
        new_env_data = {}
        for key in target_keys:
            val = request.form.get(key, '').strip()
            if val:
                new_env_data[key] = val
                os.environ[key] = val  # Update active runtime environment

        # Safely write to .env file
        try:
            with open(env_path, 'w') as f:
                for k, v in new_env_data.items():
                    f.write(f"{k}={v}\n")
            flash('Environment secrets updated safely on server disk!', 'success')
        except Exception as e:
            flash(f'Error writing .env file: {e}', 'danger')

        return redirect(url_for('admin.env_manager'))

    # Read existing values
    current_values = {key: os.environ.get(key, '') for key in target_keys}

    return render_template('admin/env_manager.html', env_values=current_values)


@admin_bp.route('/claim-master', methods=['GET', 'POST'])
@login_required
def claim_master():
    """Allows the first merchant to safely promote themselves to Master Admin."""
    admin_count = User.query.filter_by(is_admin=True).count()
    if admin_count > 0 and not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        passphrase = request.form.get('passphrase', '').strip()
        # Default fallback key if not set in environment
        expected_pass = os.environ.get('MASTER_CLAIM_KEY', 'marketplace2026')

        if passphrase == expected_pass or admin_count == 0:
            current_user.is_admin = True
            db.session.commit()
            flash('Master Command access granted. Welcome, Overseer.', 'success')
            return redirect(url_for('admin.overview'))
        else:
            flash('Invalid claim passphrase.', 'danger')

    return render_template('admin/claim_master.html')
