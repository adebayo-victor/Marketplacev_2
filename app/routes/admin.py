import os
import random
import string
from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, session
from flask_login import login_required, current_user, login_user
from app import db
from sqlalchemy import func, or_
from app.models import User, Store, Order, PasswordResetTicket, Wallet, Transaction, Task, Reward
admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin and not session.get('is_master_admin'):
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count == 0:
                flash('No Master Admin exists yet. You can claim Master access below.', 'warning')
                return redirect(url_for('admin.claim_master'))
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/', strict_slashes=False)
@admin_required
def overview():
    total_merchants = User.query.count()
    total_kiosks = Store.query.count()
    from app.models import Order
    total_orders = Order.query.count()
    
    avg_kiosks = round(total_kiosks / total_merchants, 2) if total_merchants > 0 else 0.0
    total_views = db.session.query(db.func.sum(Store.views_count)).scalar() or 0
    kiosks = Store.query.order_by(Store.created_at.desc()).all()
    merchants = User.query.order_by(User.created_at.desc()).all()

    pending_resets_count = PasswordResetTicket.query.filter_by(status='pending').count()

    return render_template(
        'admin/overview.html',
        total_merchants=total_merchants,
        total_kiosks=total_kiosks,
        avg_kiosks=avg_kiosks,
        total_views=total_views,
        total_orders=total_orders,
        kiosks=kiosks,
        merchants=merchants,
        pending_resets_count=pending_resets_count
    )


# -------------------------------------------------------------
# 🔓 MASTER UNLOCK (RESCUES STUCK KIOSKS INSTANTLY)
# -------------------------------------------------------------
@admin_bp.route('/kiosk/<int:store_id>/unlock', methods=['POST'])
@admin_required
def manual_unlock_kiosk(store_id):
    """Rescues any kiosk: sets build_status='ready' and is_active=True."""
    kiosk = Store.query.get_or_404(store_id)
    kiosk.is_active = True
    kiosk.has_ever_activated = True
    kiosk.build_status = 'ready'  # ✅ Rescues stuck background builds!
    db.session.commit()
    flash(f'🎉 Kiosk "{kiosk.name}" has been manually UNLOCKED and set to READY!', 'success')
    return redirect(url_for('admin.overview'))


# Impersonation
@admin_bp.route('/impersonate/<int:user_id>')
@admin_required
def impersonate(user_id):
    target_user = User.query.get_or_404(user_id)
    session['admin_override_id'] = current_user.id
    session['is_master_admin'] = True

    login_user(target_user)
    flash(f'👤 Impersonating Merchant "{target_user.username}". You have full access to their kiosks and settings.', 'info')
    return redirect(url_for('dashboard.overview'))


# Password Reset Tickets
@admin_bp.route('/resets')
@admin_required
def reset_tickets():
    tickets = PasswordResetTicket.query.order_by(PasswordResetTicket.created_at.desc()).all()
    ticket_cards = []
    for t in tickets:
        user = User.query.filter_by(email=t.email).first()
        stores = user.stores.all() if user else []
        ticket_cards.append({
            "ticket": t,
            "user": user,
            "stores": stores
        })
    return render_template('admin/resets.html', ticket_cards=ticket_cards)


@admin_bp.route('/resets/<int:ticket_id>/approve', methods=['POST'])
@admin_required
def approve_reset(ticket_id):
    ticket = PasswordResetTicket.query.get_or_404(ticket_id)
    user = User.query.filter_by(email=ticket.email).first()

    if not user:
        flash(f'Cannot approve: No user found with email {ticket.email}.', 'danger')
        return redirect(url_for('admin.reset_tickets'))

    temp_pass = 'Market_' + ''.join(random.choices(string.digits, k=4)) + '!'
    user.set_password(temp_pass)

    ticket.status = 'approved'
    ticket.temp_password = temp_pass
    ticket.resolved_at = datetime.utcnow()

    db.session.commit()
    flash(f'Approved ticket #{ticket.ticket_ref}! Temporary password: {temp_pass}', 'success')
    return redirect(url_for('admin.reset_tickets'))


@admin_bp.route('/resets/<int:ticket_id>/reject', methods=['POST'])
@admin_required
def reject_reset(ticket_id):
    ticket = PasswordResetTicket.query.get_or_404(ticket_id)
    ticket.status = 'rejected'
    ticket.resolved_at = datetime.utcnow()
    db.session.commit()
    flash(f'Rejected ticket #{ticket.ticket_ref}.', 'info')
    return redirect(url_for('admin.reset_tickets'))


# Template Editor
@admin_bp.route('/kiosk/<int:store_id>/template', methods=['GET', 'POST'])
@admin_required
def edit_template(store_id):
    store = Store.query.get_or_404(store_id)
    if request.method == 'POST':
        store.custom_html = request.form.get('custom_html', '')
        store.build_status = 'ready'
        db.session.commit()
        flash(f'HTML template for "{store.name}" updated successfully!', 'success')
        return redirect(url_for('admin.edit_template', store_id=store.id))
    return render_template('admin/template_editor.html', store=store)


# Secrets Manager
@admin_bp.route('/system/env', methods=['GET', 'POST'])
@admin_required
def env_manager():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    target_keys = [
        'SECRET_KEY', 'CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET',
        'AI_API_KEY', 'OPENROUTER_API_KEY', 'OPENROUTER_MODEL', 'PAYSTACK_PUBLIC_KEY', 
        'PAYSTACK_SECRET_KEY', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'
    ]

    if request.method == 'POST':
        new_env_data = {}
        for key in target_keys:
            val = request.form.get(key, '').strip()
            if val:
                new_env_data[key] = val
                os.environ[key] = val

        try:
            with open(env_path, 'w') as f:
                for k, v in new_env_data.items():
                    f.write(f"{k}={v}\n")
            flash('Environment secrets updated safely on server disk!', 'success')
        except Exception as e:
            flash(f'Notice: On serverless/read-only hosts, update keys in provider dashboard: {e}', 'info')

        return redirect(url_for('admin.env_manager'))

    current_values = {key: os.environ.get(key, '') for key in target_keys}
    return render_template('admin/env_manager.html', env_values=current_values)


@admin_bp.route('/claim-master', methods=['GET', 'POST'])
@login_required
def claim_master():
    admin_count = User.query.filter_by(is_admin=True).count()
    if admin_count > 0 and not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        passphrase = request.form.get('passphrase', '').strip()
        expected_pass = os.environ.get('MASTER_CLAIM_KEY', 'marketplace2026')

        if passphrase == expected_pass or admin_count == 0:
            current_user.is_admin = True
            db.session.commit()
            flash('Master Command access granted. Welcome, Overseer.', 'success')
            return redirect(url_for('admin.overview'))
        else:
            flash('Invalid claim passphrase.', 'danger')

    return render_template('admin/claim_master.html')





# -------------------------------------------------------------
# 💰 ADMIN ECONOMY COMMAND CENTER (Summaries, Pricing, & Ledger Search)
# -------------------------------------------------------------
@admin_bp.route('/economy', methods=['GET', 'POST'])
@admin_required
def economy():
    # 1. Economic Summaries
    total_referrals = User.query.filter(User.referred_by_id.isnot(None)).count()
    total_earned = db.session.query(func.sum(Transaction.amount)).filter(Transaction.type == 'credit').scalar() or 0
    total_spent = db.session.query(func.sum(Transaction.amount)).filter(Transaction.type == 'debit').scalar() or 0
    coins_in_circulation = total_earned - total_spent
    active_wallets = Wallet.query.filter(Wallet.balance > 0).count()

    # 2. Handle Form Submission (Update BOTH Rewards and Tasks)
    if request.method == 'POST':
        # Update Earning Rules (Rewards)
        reward_ids = request.form.getlist('reward_id')
        for r_id in reward_ids:
            reward = Reward.query.get(r_id)
            if reward:
                new_value = request.form.get(f'reward_value_{r_id}')
                if new_value and new_value.isdigit():
                    reward.value = int(new_value)
                reward.is_active = request.form.get(f'reward_active_{r_id}') == 'on'
        
        # Update Redemption Shop (Tasks)
        task_ids = request.form.getlist('task_id')
        for t_id in task_ids:
            task = Task.query.get(t_id)
            if task:
                new_price = request.form.get(f'task_price_{t_id}')
                if new_price and new_price.isdigit():
                    task.price = int(new_price)
                task.is_active = request.form.get(f'task_active_{t_id}') == 'on'
        
        db.session.commit()
        flash('Economy settings updated successfully!', 'success')
        return redirect(url_for('admin.economy'))

    # 3. Fetch Pricing Tables
    rewards = Reward.query.all()
    tasks = Task.query.order_by(Task.price.asc()).all()

    # 4. Transaction Ledger Search & Filter ("Detailed searching typeshiii")
    search_query = request.args.get('search', '').strip()
    filter_type = request.args.get('type', 'all') # 'all', 'credit', 'debit'

    # Join Transaction with User to allow searching by merchant username
    ledger_query = db.session.query(Transaction, User.username).join(User, Transaction.user_id == User.id)

    if filter_type != 'all':
        ledger_query = ledger_query.filter(Transaction.type == filter_type)
    
    if search_query:
        # Search by merchant username OR transaction description (e.g., "Kiosk Creation")
        ledger_query = ledger_query.filter(
            or_(
                User.username.ilike(f'%{search_query}%'),
                Transaction.description.ilike(f'%{search_query}%')
            )
        )

    # Get the latest 100 transactions matching the filter
    ledger_results = ledger_query.order_by(Transaction.created_at.desc()).limit(100).all()
    
    # Format for the template
    transactions = [{
        'id': tx.id,
        'username': username,
        'type': tx.type,
        'amount': tx.amount,
        'description': tx.description,
        'created_at': tx.created_at
    } for tx, username in ledger_results]

    return render_template(
        'admin/economy.html',
        total_referrals=total_referrals,
        total_earned=total_earned,
        total_spent=total_spent,
        coins_in_circulation=coins_in_circulation,
        active_wallets=active_wallets,
        rewards=rewards,
        tasks=tasks,
        transactions=transactions,
        search_query=search_query,
        filter_type=filter_type
    )
