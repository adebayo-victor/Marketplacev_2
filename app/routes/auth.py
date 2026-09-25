from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

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

        # PLAIN START: Create Merchant User ONLY (Zero kiosks created yet)
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


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
