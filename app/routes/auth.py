import os
import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, oauth
from app.models import User

auth_bp = Blueprint('auth', __name__)

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.overview'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not username or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('That username is already taken. Please choose another.', 'warning')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('That email address is already registered. Please log in.', 'warning')
            return render_template('auth/register.html')

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f'Welcome, {username}! Your merchant account is ready.', 'success')
        return redirect(url_for('dashboard.overview'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.overview'))

    if request.method == 'POST':
        login_input = request.form.get('login_input', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = True if request.form.get('remember') else False

        user = User.query.filter((User.email == login_input) | (User.username == login_input)).first()

        if not user or not user.check_password(password):
            flash('Invalid username/email or password.', 'danger')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.overview'))

    return render_template('auth/login.html')


# -------------------------------------------------------------
# GOOGLE OAUTH 2.0 SIGN-IN
# -------------------------------------------------------------
@auth_bp.route('/login/google')
def google_login():
    """Initiates Google OAuth flow."""
    google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
    if not google_client_id:
        flash('Google Sign-In is not configured yet. Please configure it in Master Command.', 'warning')
        return redirect(url_for('auth.login'))

    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/login/google/callback')
def google_callback():
    """Handles callback response from Google."""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            user_info = oauth.google.userinfo()

        email = user_info['email'].lower()

        user = User.query.filter_by(email=email).first()
        if not user:
            # Auto-create merchant account with unique username from email
            base_username = slugify(email.split('@')[0])
            username = base_username
            count = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{count}"
                count += 1

            user = User(username=username, email=email)
            # Random strong password for OAuth account
            user.set_password(os.urandom(16).hex())
            db.session.add(user)
            db.session.commit()
            flash(f'Account created via Google! Welcome, {user.username}.', 'success')
        else:
            flash(f'Signed in with Google as {user.username}.', 'success')

        login_user(user)
        return redirect(url_for('dashboard.overview'))

    except Exception as e:
        flash(f'Google Sign-In failed: {e}', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
