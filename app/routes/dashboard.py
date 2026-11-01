
import random
import time
import os
import json
import re
import urllib.request
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_wtf.csrf import generate_csrf
from flask_login import login_required, current_user
from app import db
from app.models import Store, Product, StoreAd, Order, OrderItem, User, Wallet, Transaction, Task
from app.utils.media import upload_image, delete_image
from app.utils.whatsapp import clean_phone_number
from app.utils.ai_builder import generate_kiosk_template
import requests

dashboard_bp = Blueprint('dashboard', __name__)

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '-', text)


# -------------------------------------------------------------
# LEVEL 1: THE MERCHANT HUB (/dashboard)
# -------------------------------------------------------------
@dashboard_bp.route('/dashboard')
@login_required
def overview():
    kiosks = current_user.stores.order_by(Store.created_at.desc()).all()
    return render_template('dashboard/overview.html', kiosks=kiosks)

# -------------------------------------------------------------
# Checks kisok for expiry, motherfucker, a human wrote some of this code, too, are u shocked, muahahahahaahahaha, [tears of joy] [devil], maybe i sold the code to u or ya my employee, who knows, anyways, i hope i am not making life hard for u and if i am i hope i am paying u enough.
# -------------------------------------------------------------
def check_kiosk_expiry(kiosk):
    """Checks if a kiosk has expired and disables it if so."""
    if kiosk.is_active and kiosk.expires_at:
        if kiosk.expires_at < datetime.utcnow():
            kiosk.is_active = False
            db.session.commit()
            return False
    return kiosk.is_active

# -------------------------------------------------------------
# OPEN A NEW KIOSK (INSTANT ARRIVAL IN HUB)
# -------------------------------------------------------------
# =============================================================
# 🛍️ KIOSK CREATION & WORKER DISPATCH
# =============================================================
@dashboard_bp.route('/kiosk/new', methods=['GET', 'POST'])
@login_required
def new_kiosk():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        custom_slug = request.form.get('slug', '').strip()
        whatsapp = request.form.get('whatsapp_number', '').strip()
        bio = request.form.get('bio', 'Welcome to our official store!').strip()
        category = request.form.get('category', 'General Retail').strip()
        ai_prompt = request.form.get('ai_prompt', '').strip()

        section_hero = True if request.form.get('section_hero') else False
        section_flash = True if request.form.get('section_flash') else False
        section_ads = True if request.form.get('section_ads') else False
        sections_dict = {
            "hero": section_hero,
            "flash_sales": section_flash,
            "ads": section_ads
        }

        if not name or not whatsapp:
            flash('Store name and WhatsApp number are required.', 'danger')
            return render_template('dashboard/kiosk_new.html')

        slug = slugify(custom_slug) if custom_slug else slugify(name)
        if Store.query.filter_by(slug=slug).first():
            flash(f'The link "/{slug}" is already taken. Please choose another.', 'warning')
            return render_template('dashboard/kiosk_new.html')

        logo_file = request.files.get('logo')
        hero_file = request.files.get('hero_image')
        bg_file = request.files.get('background_image')

        logo_url = upload_image(logo_file, 'logos') or ''
        hero_url = upload_image(hero_file, 'heroes') or ''
        bg_url = upload_image(bg_file, 'backgrounds') or ''

        clean_phone = clean_phone_number(whatsapp)

        # 1. Create the store row in database (locked as 'building')
        store = Store(
            user_id=current_user.id,
            name=name,
            slug=slug,
            whatsapp_number=clean_phone,
            bio=bio,
            logo=logo_url or 'default_logo.png',
            hero_image=hero_url,
            background_image=bg_url,
            receipt_theme='classic',
            sections_config=json.dumps(sections_dict),
            is_active=False,
            has_ever_activated=False,
            build_status='building',  # ⏳ Locked until Render worker finishes!
            custom_html=''
        )
        db.session.add(store)
        db.session.flush()

        for slot_num in [1, 2, 3]:
            ad = StoreAd(store_id=store.id, slot_number=slot_num, is_active=False)
            db.session.add(ad)

        db.session.commit()

        # 2. ⚡ Intercept & Dispatch to Render Worker (Zero Vercel timeout!)
        worker_url = os.environ.get('RENDER_WORKER_URL', 'https://marketplace-ai-worker.onrender.com/build')
        builder_secret = os.environ.get('BUILDER_SECRET_KEY', '')

        job_payload = {
            "kiosk_id": store.id,
            "kiosk_slug": store.slug,
            "kiosk_name": store.name,
            "bio": store.bio,
            "prompt": f"Category: {category}. Client Style Notes: {ai_prompt or 'Bespoke modern storefront'}",
            "logo_url": logo_url or 'default_logo.png',
            "hero_url": hero_url,
            "bg_url": bg_url,
            "currency": store.currency or '₦',
            "callback_url": "https://marketplace-beryl-delta.vercel.app/api/internal/kiosk-ready",
            "secret": builder_secret
        }

        try:
            # 1-second timeout: Fire-and-forget handoff to Render
            requests.post(worker_url, json=job_payload, timeout=1.0)
            print(f"⚡ Handed off job for store #{store.id} to Render worker")
        except Exception as e:
            print(f"Notice during worker dispatch (expected async): {e}")

        flash(f'⏳ Kiosk "{name}" is being assembled by AI in the background!', 'info')
        return redirect(url_for('dashboard.overview'))

    return render_template('dashboard/kiosk_new.html')

# -------------------------------------------------------------
#  🔗 A referral route
# -------------------------------------------------------------

@dashboard_bp.route('/referrals')
@login_required
def referrals():
    # Get everyone who signed up using this user's code
    referred_users = User.query.filter_by(referred_by_id=current_user.id).order_by(User.created_at.desc()).all()
    
    # Generate their unique, full referral link
    host_url = request.host_url.rstrip('/')
    referral_link = f"{host_url}/register?ref={current_user.referral_code}"
    
    return render_template('dashboard/referrals.html', 
                           referred_users=referred_users, 
                           referral_link=referral_link,
                           total_invites=len(referred_users))


# -------------------------------------------------------------
# 💰 FINANCE DASHBOARD (Balance, Ledger, Rewards Shop)
# -------------------------------------------------------------
@dashboard_bp.route('/finance')
@login_required
def finance():
    wallet = Wallet.query.filter_by(user_id=current_user.id).first()
    if not wallet:
        wallet = Wallet(user_id=current_user.id, balance=0)
        db.session.add(wallet)
        db.session.commit()

    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).all()
    tasks = Task.query.filter_by(is_active=True).all()
    inactive_kiosks_raw = Store.query.filter_by(user_id=current_user.id, is_active=False, build_status='ready').all()
    inactive_kiosks = [{"id": k.id, "name": k.name} for k in inactive_kiosks_raw]

    return render_template('dashboard/finance.html', 
                           wallet=wallet, 
                           transactions=transactions, 
                           tasks=tasks,
                           inactive_kiosks=inactive_kiosks,
                           csrf_token=generate_csrf()) # 👈 ADD THIS LINE


# -------------------------------------------------------------
# 💸 REDEEM REWARD LOGIC (Debits coins and logs transaction)
# -------------------------------------------------------------
@dashboard_bp.route('/finance/redeem', methods=['POST'])
@login_required
def redeem_task():
    data = request.get_json()
    task_id = data.get('task_id')
    kiosk_id = data.get('kiosk_id') # NEW: We use ID instead of slug
    
    if not task_id:
        return jsonify({'status': 'error', 'message': 'Invalid task ID.'}), 400
        
    task = Task.query.get(task_id)
    if not task or not task.is_active:
        return jsonify({'status': 'error', 'message': 'Reward not found or inactive.'}), 404
        
    wallet = Wallet.query.filter_by(user_id=current_user.id).first()
    if not wallet:
        return jsonify({'status': 'error', 'message': 'Wallet not found.'}), 404
        
    if wallet.balance < task.price:
        return jsonify({'status': 'error', 'message': 'Insufficient coin balance.'}), 400
        
    # SPECIAL LOGIC: If redeeming a Kiosk, unlock it!
    if task.name == 'Kiosk Creation':
        if not kiosk_id:
            return jsonify({'status': 'error', 'message': 'Please select a kiosk to unlock.'}), 400
            
        # Securely find the kiosk and ensure it belongs to this user
        kiosk = Store.query.filter_by(id=kiosk_id, user_id=current_user.id).first()
        if not kiosk:
            return jsonify({'status': 'error', 'message': 'Kiosk not found or not yours.'}), 404
            
        if kiosk.is_active:
            return jsonify({'status': 'error', 'message': 'This kiosk is already active!'}), 400
            
        kiosk.is_active = True
        kiosk.has_ever_activated = True

    # Perform the debit
    wallet.balance -= task.price
    
    tx = Transaction(
        wallet_id=wallet.id,
        user_id=current_user.id,
        type='debit',
        amount=task.price,
        task_id=task.id,
        description=f"Redeemed: {task.name}" + (f" for {kiosk.name}" if task.name == 'Kiosk Creation' and kiosk else "")
    )
    
    db.session.add(tx)
    db.session.commit()
    
    return jsonify({
        'status': 'success', 
        'message': f'Successfully redeemed "{task.name}"! Kiosk unlocked.',
        'new_balance': wallet.balance
    }), 200

# -------------------------------------------------------------
# ⚡ STATUS CHECKER (Fast non-blocking response for frontend polling)
# -------------------------------------------------------------
@dashboard_bp.route('/<kiosk_slug>/build-worker', methods=['GET', 'POST'])
@login_required
def execute_build_worker(kiosk_slug):
    """Fast status reporter so the dashboard JS doesn't trigger heavy AI on Vercel."""
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    return jsonify({
        "status": "ready" if kiosk.build_status == 'ready' else "building",
        "build_status": kiosk.build_status,
        "slug": kiosk.slug
    })


# -------------------------------------------------------------
# 💳 REAL PAYSTACK ACTIVATION / RENEWAL (₦5,000 / 500,000 KOBO)
# -------------------------------------------------------------
@dashboard_bp.route('/<kiosk_slug>/activate/verify')
@login_required
def verify_kiosk_activation(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    reference = request.args.get('reference')
    paystack_secret = (os.environ.get('PAYSTACK_SECRET_KEY') or '').strip()

    if not reference:
        flash('Payment verification failed: No transaction reference received.', 'danger')
        return redirect(url_for('dashboard.overview'))

    if not paystack_secret:
        flash('Paystack is not configured. Please add PAYSTACK_SECRET_KEY in Master Command (/admin/system/env).', 'danger')
        return redirect(url_for('dashboard.overview'))

    try:
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {paystack_secret}",
            "Content-Type": "application/json",
            "User-Agent": "Marketplace/2.0 (Mozilla/5.0)"
        })

        with urllib.request.urlopen(req, timeout=20) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            
            if res_data.get('status') and res_data.get('data', {}).get('status') == 'success':
                paid_amount = res_data['data']['amount']
                
                if paid_amount >= 500000:
                    kiosk.is_active = True
                    kiosk.has_ever_activated = True
                    
                    # 🗓️ MONTHLY SUBSCRIPTION LOGIC
                    now = datetime.utcnow()
                    if kiosk.expires_at and kiosk.expires_at > now:
                        # If they renew early, add 30 days to their CURRENT expiry
                        kiosk.expires_at = kiosk.expires_at + timedelta(days=30)
                    else:
                        # If it's expired or new, start 30 days from NOW
                        kiosk.expires_at = now + timedelta(days=30)
                        
                    db.session.commit()
                    
                    expiry_date = kiosk.expires_at.strftime('%b %d, %Y')
                    flash(f'🎉 Payment verified! Kiosk "{kiosk.name}" is active until {expiry_date}.', 'success')
                else:
                    flash(f'Payment rejected: Underpaid amount ({paid_amount/100} NGN). Required ₦5,000.', 'danger')
            else:
                gateway_msg = res_data.get('data', {}).get('gateway_response', 'Transaction was declined.')
                flash(f'Paystack Payment Failed: {gateway_msg}', 'danger')
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        flash(f'Paystack Verification Error: HTTP {e.code} - {error_body}', 'danger')
    except Exception as e:
        flash(f'Paystack Verification Error: {e}', 'danger')

    return redirect(url_for('dashboard.overview'))


# -------------------------------------------------------------
# LEVEL 2: SPECIFIC KIOSK CONTROL ROOM (/<kiosk_slug>/manage)
# -------------------------------------------------------------
@dashboard_bp.route('/<kiosk_slug>/manage')
@login_required
def manage_kiosk(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    if kiosk.build_status == 'building':
        flash(f'⏳ Hold on! Kiosk "{kiosk.name}" is still being assembled by the AI engine. You cannot open it until creation is finished.', 'warning')
        return redirect(url_for('dashboard.overview'))

    products = kiosk.products.order_by(Product.created_at.desc()).all()
    leads = kiosk.orders.order_by(Order.created_at.desc()).all()
    ads = kiosk.ads.order_by(StoreAd.slot_number.asc()).all()

    return render_template(
        'dashboard/kiosk_manage.html',
        kiosk=kiosk,
        products=products,
        leads=leads,
        ads=ads
    )


# Update Order Status
@dashboard_bp.route('/<kiosk_slug>/order/<int:order_id>/status', methods=['GET', 'POST'])
@login_required
def update_order_status(kiosk_slug, order_id):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        order = Order.query.filter_by(id=order_id, store_id=kiosk.id).first_or_404()
        new_status = request.form.get('status', 'pending').strip().lower()

        if new_status in ['pending', 'paid', 'shipped', 'completed', 'cancelled']:
            order.status = new_status
            db.session.commit()
            flash(f"Order #{order.order_ref} updated to '{new_status.upper()}'. Receipt updated.", "success")

    return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug) + '#leads')


# Product CRUD
@dashboard_bp.route('/<kiosk_slug>/product/new', methods=['GET', 'POST'])
@login_required
def new_product(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        original_price = float(request.form.get('original_price', 0) or 0)
        discount_price = request.form.get('discount_price', '').strip()
        is_flash_sale = True if request.form.get('is_flash_sale') else False

        is_unlimited = True if request.form.get('is_unlimited_stock') else False
        stock = 999999 if is_unlimited else int(request.form.get('stock', 1) or 1)

        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_values[]')
        attributes_dict = {}

        for a_name, a_vals in zip(attr_names, attr_values):
            clean_name = a_name.strip()
            if clean_name and a_vals.strip():
                opts = [v.strip() for v in a_vals.split(',') if v.strip()]
                if len(opts) < 2:
                    flash(f'Validation Error: Feature "{clean_name}" must have at least 2 choices separated by comma (e.g. 3000, 5000).', 'danger')
                    return render_template('dashboard/product_form.html', kiosk=kiosk, product=None)
                attributes_dict[clean_name] = opts

        image_file = request.files.get('image')
        image_name = upload_image(image_file, 'products') or 'default_product.png'

        product = Product(
            store_id=kiosk.id,
            name=name,
            description=description,
            original_price=original_price,
            discount_price=float(discount_price) if discount_price else None,
            is_flash_sale=is_flash_sale,
            is_unlimited_stock=is_unlimited,
            stock=stock,
            image=image_name,
            attributes_json=json.dumps(attributes_dict)
        )
        db.session.add(product)
        db.session.commit()

        flash(f'Product "{name}" added to {kiosk.name}!', 'success')
        return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))

    return render_template('dashboard/product_form.html', kiosk=kiosk, product=None)


@dashboard_bp.route('/<kiosk_slug>/product/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(kiosk_slug, id):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    product = Product.query.filter_by(id=id, store_id=kiosk.id).first_or_404()

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.description = request.form.get('description', '').strip()
        product.original_price = float(request.form.get('original_price', 0) or 0)
        
        disc = request.form.get('discount_price', '').strip()
        product.discount_price = float(disc) if disc else None
        
        is_unlimited = True if request.form.get('is_unlimited_stock') else False
        product.is_unlimited_stock = is_unlimited
        product.stock = 999999 if is_unlimited else int(request.form.get('stock', 1) or 1)
        
        product.is_flash_sale = True if request.form.get('is_flash_sale') else False

        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_values[]')
        attributes_dict = {}

        for a_name, a_vals in zip(attr_names, attr_values):
            clean_name = a_name.strip()
            if clean_name and a_vals.strip():
                opts = [v.strip() for v in a_vals.split(',') if v.strip()]
                if len(opts) < 2:
                    flash(f'Validation Error: Feature "{clean_name}" must have at least 2 choices separated by comma (e.g. 3000, 5000).', 'danger')
                    return render_template('dashboard/product_form.html', kiosk=kiosk, product=product)
                attributes_dict[clean_name] = opts

        product.attributes_json = json.dumps(attributes_dict)

        image_file = request.files.get('image')
        new_img = upload_image(image_file, 'products')
        if new_img:
            delete_image(product.image, 'products')
            product.image = new_img

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))

    return render_template('dashboard/product_form.html', kiosk=kiosk, product=product)


@dashboard_bp.route('/<kiosk_slug>/product/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_product(kiosk_slug, id):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    product = Product.query.filter_by(id=id, store_id=kiosk.id).first_or_404()
    OrderItem.query.filter_by(product_id=product.id).update({'product_id': None})
    delete_image(product.image, 'products')

    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{product.name}" deleted and past receipts preserved.', 'info')
    return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug) + '#inventory')


# The Social Flyer Studio
@dashboard_bp.route('/<kiosk_slug>/product/<int:id>/flyer')
@login_required
def product_flyer(kiosk_slug, id):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    product = Product.query.filter_by(id=id, store_id=kiosk.id).first_or_404()
    return render_template('dashboard/product_flyer.html', kiosk=kiosk, product=product)


# Settings & Sectional Activation
@dashboard_bp.route('/<kiosk_slug>/settings', methods=['POST'])
@login_required
def update_kiosk_settings(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    kiosk.name = request.form.get('name', kiosk.name).strip()
    kiosk.bio = request.form.get('bio', kiosk.bio).strip()
    kiosk.currency = request.form.get('currency', '₦').strip()
    kiosk.show_public_stats = True if request.form.get('show_public_stats') else False
    kiosk.receipt_theme = request.form.get('receipt_theme', 'classic').strip()

    section_hero = True if request.form.get('section_hero') else False
    section_flash = True if request.form.get('section_flash') else False
    section_ads = True if request.form.get('section_ads') else False
    kiosk.sections_config = json.dumps({
        "hero": section_hero,
        "flash_sales": section_flash,
        "ads": section_ads
    })
    
    phone = request.form.get('whatsapp_number', '').strip()
    if phone:
        kiosk.whatsapp_number = clean_phone_number(phone)

    logo_file = request.files.get('logo')
    hero_file = request.files.get('hero_image')
    bg_file = request.files.get('background_image')

    new_logo = upload_image(logo_file, 'logos')
    new_hero = upload_image(hero_file, 'heroes')
    new_bg = upload_image(bg_file, 'backgrounds')

    if new_logo:
        delete_image(kiosk.logo, 'logos')
        kiosk.logo = new_logo
    if new_hero:
        delete_image(kiosk.hero_image, 'heroes')
        kiosk.hero_image = new_hero
    if new_bg:
        delete_image(kiosk.background_image, 'backgrounds')
        kiosk.background_image = new_bg

    db.session.commit()
    flash(f'Settings & Layout for "{kiosk.name}" updated successfully!', 'success')
    return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))


# Manage 3 Ad Slots
@dashboard_bp.route('/<kiosk_slug>/ads', methods=['POST'])
@login_required
def update_kiosk_ads(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    slot_num = int(request.form.get('slot_number'))
    ad = StoreAd.query.filter_by(store_id=kiosk.id, slot_number=slot_num).first()
    if ad:
        ad.target_link = request.form.get('target_link', '').strip()
        ad.is_active = True if request.form.get('is_active') else False
        
        banner_file = request.files.get('banner_image')
        new_banner = upload_image(banner_file, 'ads')
        if new_banner:
            delete_image(ad.banner_image, 'ads')
            ad.banner_image = new_banner

        db.session.commit()
        flash(f'Ad Slot #{slot_num} updated!', 'success')

    return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))


# Delete kiosk safely
@dashboard_bp.route('/<kiosk_slug>/delete', methods=['GET', 'POST'])
@login_required
def delete_kiosk(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    name = kiosk.name
    product_ids = [p.id for p in kiosk.products.all()]
    if product_ids:
        OrderItem.query.filter(OrderItem.product_id.in_(product_ids)).update({'product_id': None}, synchronize_session=False)

    delete_image(kiosk.logo, 'logos')
    delete_image(kiosk.hero_image, 'heroes')
    delete_image(kiosk.background_image, 'backgrounds')
    for p in kiosk.products.all():
        delete_image(p.image, 'products')
    for ad in kiosk.ads.all():
        delete_image(ad.banner_image, 'ads')

    db.session.delete(kiosk)
    db.session.commit()
    flash(f'Kiosk "{name}" and media deleted permanently.', 'info')
    return redirect(url_for('dashboard.overview'))

# -------------------------------------------------------------
# 💳 WALLET TOP-UP: Initialize Paystack
# -------------------------------------------------------------
@dashboard_bp.route('/finance/topup', methods=['POST'])
@login_required
def topup_wallet():
    data = request.get_json()
    amount_naira = data.get('amount')
    
    if not amount_naira:
        return jsonify({'status': 'error', 'message': 'Amount is required.'}), 400
        
    amount_naira = float(amount_naira)
    if amount_naira < 100:
        return jsonify({'status': 'error', 'message': 'Minimum top-up amount is ₦100.'}), 400
        
    ref = f"TOPUP_{current_user.id}_{int(time.time())}_{random.randint(1000, 9999)}"
    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY', '').strip()
    
    if not paystack_secret:
        return jsonify({'status': 'error', 'message': 'Paystack secret key not configured.'}), 500
        
    url = "https://api.paystack.co/transaction/initialize"
    req_data = json.dumps({
        "email": current_user.email,
        "amount": int(amount_naira * 100),
        "reference": ref,
        "callback_url": request.host_url.rstrip('/') + "/finance/topup/verify"
    }).encode('utf-8')
    
    # ✅ MIRRORED HEADERS FROM WORKING KIOSK ROUTE
    req = urllib.request.Request(url, data=req_data, headers={
        "Authorization": f"Bearer {paystack_secret}",
        "Content-Type": "application/json",
        "User-Agent": "Marketplace/2.0 (Mozilla/5.0)"  # 👈 THIS IS THE MISSING KEY!
    })
    
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            if res_data.get('status'):
                return jsonify({
                    'status': 'success',
                    'authorization_url': res_data['data']['authorization_url'],
                    'reference': ref
                })
            else:
                return jsonify({'status': 'error', 'message': res_data.get('message', 'Paystack initialization failed')}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# -------------------------------------------------------------
# 💳 WALLET TOP-UP: Verify and Credit Wallet
# -------------------------------------------------------------
@dashboard_bp.route('/finance/topup/verify')
def verify_topup():
    reference = request.args.get('reference')
    
    if not reference:
        flash('No transaction reference provided.', 'danger')
        return redirect(url_for('auth.login'))

    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY', '').strip()
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {paystack_secret}",
        "Content-Type": "application/json",
        "User-Agent": "Marketplace/2.0 (Mozilla/5.0)" # Mirrored from working route
    })
    
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            
            if res_data.get('status') and res_data.get('data', {}).get('status') == 'success':
                paid_amount_kobo = res_data['data']['amount']
                amount_naira = paid_amount_kobo / 100
                
                # 1. Find the user via the email Paystack gives us (Bypasses session cookie issues!)
                customer_email = res_data['data']['customer']['email']
                user = User.query.filter_by(email=customer_email).first()
                
                if not user:
                    flash('Payment successful, but user account not found.', 'danger')
                    return redirect(url_for('auth.login'))

                # 2. Prevent double-crediting
                desc = f"Wallet Top-up (Ref: {reference})"
                if Transaction.query.filter_by(user_id=user.id, description=desc).first():
                    flash('This transaction has already been processed.', 'info')
                    return redirect(url_for('dashboard.finance'))

                # 3. Get or create wallet
                wallet = Wallet.query.filter_by(user_id=user.id).first()
                if not wallet:
                    wallet = Wallet(user_id=user.id, balance=0)
                    db.session.add(wallet)
                    db.session.flush()
                    
                # 4. Credit the wallet (1 Naira = 1 Coin)
                coins_to_add = int(amount_naira)
                wallet.balance += coins_to_add
                
                # 5. Log the transaction
                tx = Transaction(
                    wallet_id=wallet.id,
                    user_id=user.id,
                    type='credit',
                    amount=coins_to_add,
                    description=desc
                )
                db.session.add(tx)
                db.session.commit()
                
                flash(f'🎉 Successfully topped up your wallet with ₦{amount_naira:,.2f} ({coins_to_add} Coins)!', 'success')
            else:
                gateway_msg = res_data.get('data', {}).get('gateway_response', 'Transaction was declined.')
                flash(f'Payment Failed: {gateway_msg}', 'danger')
                
    except urllib.error.HTTPError as e:
        flash(f'Verification Error: HTTP {e.code}', 'danger')
    except Exception as e:
        flash(f'Verification Error: {str(e)}', 'danger')
        
    # Redirect to finance if logged in, otherwise login
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.finance'))
    return redirect(url_for('auth.login'))
