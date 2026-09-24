import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Store, StoreAd
from app.utils.whatsapp import clean_phone_number

auth_bp = Blueprint('auth', __name__)

def slugify(text: str) -> str:
    """Converts a store name into a clean URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.overview'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        store_name = request.form.get('store_name', '').strip()
        custom_slug = request.form.get('slug', '').strip()
        whatsapp = request.form.get('whatsapp_number', '').strip()

        if not email or not password or not store_name or not whatsapp:
            flash('Please fill in all required fields.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('That email address is already registered. Please log in.', 'warning')
            return render_template('auth/register.html')

        slug = slugify(custom_slug) if custom_slug else slugify(store_name)
        if Store.query.filter_by(slug=slug).first():
            flash(f'The store link "/{slug}" is already taken. Please choose another.', 'warning')
            return render_template('auth/register.html')

        # 1. Create User
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # 2. Create Store
        clean_phone = clean_phone_number(whatsapp)
        store = Store(
            user_id=user.id,
            name=store_name,
            slug=slug,
            whatsapp_number=clean_phone
        )
        db.session.add(store)
        db.session.flush()

        # 3. Initialize the 3 default Ad Slots
        for slot_num in [1, 2, 3]:
            ad = StoreAd(store_id=store.id, slot_number=slot_num, is_active=False)
            db.session.add(ad)

        db.session.commit()

        login_user(user)
        flash('Storefront launched successfully! Welcome to your dashboard.', 'success')
        return redirect(url_for('dashboard.overview'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.overview'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password. Please try again.', 'danger')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.overview'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
