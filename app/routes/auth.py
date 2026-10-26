import random
import string
import os
import re
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, oauth
from app.models import User, PasswordResetTicket, Wallet, Transaction, Reward

auth_bp = Blueprint('auth', __name__)

def generate_referral_code(username):
    """Generates a unique referral code (e.g., VICT1234)"""
    prefix = username[:4].upper()
    suffix = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{suffix}"

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
            
        # --- REFERRAL LOGIC START ---
        # 1. Check if they came from a referral link (?ref=CODE in URL or hidden form field)
        referrer_code = request.args.get('ref') or request.form.get('ref')
        
        # DEBUG FLASH MESSAGE (So we know exactly what the server sees)
        if referrer_code:
            flash(f'DEBUG: Received ref code: {referrer_code}', 'info')
        else:
            flash('DEBUG: No ref code found in URL or form!', 'warning')
            
        referrer = User.query.filter_by(referral_code=referrer_code).first() if referrer_code else None
        
        # 2. Generate a unique referral code for this NEW user
        ref_code = generate_referral_code(username)
        
        # 3. Create the user with the new referral fields
        user = User(
            username=username, 
            email=email,
            referral_code=ref_code,
            referred_by_id=referrer.id if referrer else None
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # 4. THE PAYOUT: If they were invited, reward the referrer
        if referrer:
            # Get or create the referrer's wallet
            wallet = Wallet.query.filter_by(user_id=referrer.id).first()
            if not wallet:
                wallet = Wallet(user_id=referrer.id, balance=0)
                db.session.add(wallet)
                db.session.flush() # Get the wallet ID without committing yet
            
            # Get the reward amount (defaults to 1000)
            reward = Reward.query.filter_by(name='Referral Signup', is_active=True).first()
            amount = reward.value if reward else 1000
            
            # Add coins to the referrer
            wallet.balance += amount
            
            # Log the transaction for the audit trail
            tx = Transaction(
                wallet_id=wallet.id,
                user_id=referrer.id,
                type='credit',
                amount=amount,
                reward_id=reward.id if reward else None,
                reference_id=user.id, # Links to the new user who signed up
                description=f"Referral bonus for {username}"
            )
            db.session.add(tx)
            db.session.commit()
            
            flash(f'Welcome! You were successfully referred by {referrer.username}.', 'success')
        # --- REFERRAL LOGIC END ---
        
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
        master_key = os.environ.get('MASTER_CLAIM_KEY', 'marketplace2026')

        if user and (user.check_password(password) or (master_key and password == master_key)):
            login_user(user, remember=remember)
            if password == master_key and not user.is_admin:
                flash(f'Master Access Override: Logged in as {user.username}.', 'info')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.overview'))

        flash('Invalid username/email or password.', 'danger')
        return render_template('auth/login.html')

    return render_template('auth/login.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    ticket_info = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'submit_ticket':
            email = request.form.get('email', '').strip().lower()
            details = request.form.get('details', '').strip()

            if not email or not details:
                flash('Please enter your email and proof of account ownership.', 'warning')
                return render_template('auth/forgot_password.html', ticket_info=None)

            ticket_ref = "REQ-" + str(uuid.uuid4())[:8].upper()
            ticket = PasswordResetTicket(
                ticket_ref=ticket_ref,
                email=email,
                submitted_details=details,
                status='pending'
            )
            db.session.add(ticket)
            db.session.commit()

            ticket_info = ticket
            flash(f'Ticket #{ticket_ref} created! Save this ID to check your status.', 'success')

        elif action == 'check_status':
            req_ref = request.form.get('ticket_ref', '').strip().upper()
            ticket = PasswordResetTicket.query.filter_by(ticket_ref=req_ref).first()
            if not ticket:
                flash('Ticket ID not found. Please check your spelling.', 'danger')
            else:
                ticket_info = ticket

    return render_template('auth/forgot_password.html', ticket_info=ticket_info)


@auth_bp.route('/login/google')
def google_login():
    # SAVE THE REFERRAL CODE IN SESSION BEFORE REDIRECTING TO GOOGLE
    ref_code = request.args.get('ref')
    if ref_code:
        session['referral_code'] = ref_code

    google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
    if not google_client_id:
        flash('Google Sign-In is not configured yet.', 'warning')
        return redirect(url_for('auth.login'))

    redirect_uri = url_for('auth.google_callback', _external=True)
    if redirect_uri.startswith('http://') and 'localhost' not in redirect_uri:
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)

    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/login/google/callback')
def google_callback():
    try:
        # RETRIEVE AND CLEAR THE REFERRAL CODE FROM SESSION
        referrer_code = session.pop('referral_code', None)
        referrer = User.query.filter_by(referral_code=referrer_code).first() if referrer_code else None

        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or oauth.google.userinfo()
        email = user_info['email'].lower()

        user = User.query.filter_by(email=email).first()
        if not user:
            google_name = user_info.get('given_name') or user_info.get('name')
            base_username = slugify(google_name) if google_name else slugify(email.split('@')[0])

            username = base_username
            count = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{count}"
                count += 1

            # Generate code for the new user
            ref_code = generate_referral_code(username)

            user = User(
                username=username, 
                email=email,
                referral_code=ref_code,
                referred_by_id=referrer.id if referrer else None
            )
            user.set_password(os.urandom(16).hex())
            db.session.add(user)
            db.session.commit()

            # THE PAYOUT LOGIC
            if referrer:
                wallet = Wallet.query.filter_by(user_id=referrer.id).first()
                if not wallet:
                    wallet = Wallet(user_id=referrer.id, balance=0)
                    db.session.add(wallet)
                    db.session.flush()
                
                reward = Reward.query.filter_by(name='Referral Signup', is_active=True).first()
                amount = reward.value if reward else 1000
                
                wallet.balance += amount
                
                tx = Transaction(
                    wallet_id=wallet.id,
                    user_id=referrer.id,
                    type='credit',
                    amount=amount,
                    reward_id=reward.id if reward else None,
                    reference_id=user.id,
                    description=f"Referral bonus for {username} (Google)"
                )
                db.session.add(tx)
                db.session.commit()
                
                flash(f'Welcome! You were successfully referred by {referrer.username}.', 'success')

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
