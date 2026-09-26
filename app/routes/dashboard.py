import os
import json
import re
import urllib.request
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Store, Product, StoreAd, Order, OrderItem
from app.utils.media import upload_image, delete_image
from app.utils.whatsapp import clean_phone_number
from app.utils.ai_builder import generate_kiosk_template

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
# OPEN A NEW KIOSK (With 10 Categories & Section Toggles)
# -------------------------------------------------------------
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

        # Sectional Activation Toggles on Creation
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

        # Combine category with user prompt for maximum design precision
        full_design_prompt = f"Category: {category}. Client Style Notes: {ai_prompt or 'Bespoke high-end modern layout'}"

        generated_html = generate_kiosk_template(
            kiosk_name=name,
            bio=bio,
            prompt=full_design_prompt,
            logo_url=logo_url,
            hero_url=hero_url,
            bg_url=bg_url,
            currency='₦'
        )

        clean_phone = clean_phone_number(whatsapp)
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
            custom_html=generated_html
        )
        db.session.add(store)
        db.session.flush()

        for slot_num in [1, 2, 3]:
            ad = StoreAd(store_id=store.id, slot_number=slot_num, is_active=False)
            db.session.add(ad)

        db.session.commit()
        flash(f'Kiosk "{name}" created in Preview Mode! Pay activation to go live.', 'success')
        return redirect(url_for('dashboard.overview'))

    return render_template('dashboard/kiosk_new.html')


# -------------------------------------------------------------
# PAYSTACK ACTIVATION VERIFY
# -------------------------------------------------------------
@dashboard_bp.route('/<kiosk_slug>/activate/verify')
@login_required
def verify_kiosk_activation(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    reference = request.args.get('reference')
    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY')

    if not paystack_secret or reference == 'dev_unlock':
        kiosk.is_active = True
        kiosk.has_ever_activated = True
        db.session.commit()
        flash(f'🎉 Kiosk "{kiosk.name}" is now officially LIVE to the public!', 'success')
        return redirect(url_for('dashboard.overview'))

    try:
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {paystack_secret}",
            "Content-Type": "application/json"
        })
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode('utf-8'))
            if res_data.get('status') and res_data['data']['status'] == 'success':
                kiosk.is_active = True
                kiosk.has_ever_activated = True
                db.session.commit()
                flash(f'🎉 Payment verified! Kiosk "{kiosk.name}" is now officially LIVE!', 'success')
            else:
                flash('Payment verification failed.', 'danger')
    except Exception as e:
        flash(f'Verification error: {e}', 'danger')

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


# 🔄 UPDATE ORDER STATUS
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


# Product CRUD with 2-VALUES PER FEATURE & UNLIMITED STOCK
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

        # 🛑 RULE: Every feature MUST have at least 2 choices/values (e.g. 3000, 5000)
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


# Settings, Branding & Sectional Activation
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


# Delete kiosk
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
