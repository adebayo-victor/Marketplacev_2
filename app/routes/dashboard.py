import json
import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Store, Product, StoreAd, Order
from app.utils.media import upload_image
from app.utils.whatsapp import clean_phone_number
from app.utils.ai_builder import generate_kiosk_template
from app.utils.media import upload_image, delete_image

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
    """Merchant Hub: Shows all storefronts owned by this merchant."""
    kiosks = current_user.stores.order_by(Store.created_at.desc()).all()
    return render_template('dashboard/overview.html', kiosks=kiosks)


# -------------------------------------------------------------
# OPEN A NEW KIOSK (/kiosk/new)
# -------------------------------------------------------------
@dashboard_bp.route('/kiosk/new', methods=['GET', 'POST'])
@login_required
def new_kiosk():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        custom_slug = request.form.get('slug', '').strip()
        whatsapp = request.form.get('whatsapp_number', '').strip()
        bio = request.form.get('bio', 'Welcome to our official store!').strip()
        ai_prompt = request.form.get('ai_prompt', '').strip()

        if not name or not whatsapp:
            flash('Store name and WhatsApp number are required.', 'danger')
            return render_template('dashboard/kiosk_new.html')

        slug = slugify(custom_slug) if custom_slug else slugify(name)
        if Store.query.filter_by(slug=slug).first():
            flash(f'The link "/{slug}" is already taken. Please choose another.', 'warning')
            return render_template('dashboard/kiosk_new.html')

        # 1. Visual Media (Cloudinary / Local)
        logo_file = request.files.get('logo')
        hero_file = request.files.get('hero_image')
        bg_file = request.files.get('background_image')

        logo_url = upload_image(logo_file, 'logos') or ''
        hero_url = upload_image(hero_file, 'heroes') or ''
        bg_url = upload_image(bg_file, 'backgrounds') or ''

        # 2. Generate Custom HTML Template via AI using user prompt & Cloudinary URLs
        generated_html = generate_kiosk_template(
            kiosk_name=name,
            bio=bio,
            prompt=ai_prompt or f"A clean, modern storefront for {name}",
            logo_url=logo_url,
            hero_url=hero_url,
            bg_url=bg_url,
            currency='₦'
        )

        # 3. Create Store Record with custom HTML
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
            custom_html=generated_html
        )
        db.session.add(store)
        db.session.flush()

        # Initialize the 3 default Ad Slots for this kiosk
        for slot_num in [1, 2, 3]:
            ad = StoreAd(store_id=store.id, slot_number=slot_num, is_active=False)
            db.session.add(ad)

        db.session.commit()
        flash(f'Kiosk "{name}" launched successfully!', 'success')
        return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=store.slug))

    return render_template('dashboard/kiosk_new.html')


# -------------------------------------------------------------
# LEVEL 2: SPECIFIC KIOSK CONTROL ROOM (/<kiosk_slug>/manage)
# -------------------------------------------------------------
@dashboard_bp.route('/<kiosk_slug>/manage')
@login_required
def manage_kiosk(kiosk_slug):
    """Control room for ONE specific kiosk."""
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


# Product CRUD for specific kiosk
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
        stock = int(request.form.get('stock', 1) or 1)
        is_flash_sale = True if request.form.get('is_flash_sale') else False

        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_values[]')
        attributes_dict = {}
        for a_name, a_vals in zip(attr_names, attr_values):
            if a_name.strip() and a_vals.strip():
                opts = [v.strip() for v in a_vals.split(',') if v.strip()]
                if opts:
                    attributes_dict[a_name.strip()] = opts

        image_file = request.files.get('image')
        image_name = upload_image(image_file, 'products') or 'default_product.png'

        product = Product(
            store_id=kiosk.id,
            name=name,
            description=description,
            original_price=original_price,
            discount_price=float(discount_price) if discount_price else None,
            is_flash_sale=is_flash_sale,
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
        
        product.stock = int(request.form.get('stock', 1) or 1)
        product.is_flash_sale = True if request.form.get('is_flash_sale') else False

        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_values[]')
        attributes_dict = {}
        for a_name, a_vals in zip(attr_names, attr_values):
            if a_name.strip() and a_vals.strip():
                opts = [v.strip() for v in a_vals.split(',') if v.strip()]
                if opts:
                    attributes_dict[a_name.strip()] = opts

        product.attributes_json = json.dumps(attributes_dict)

        image_file = request.files.get('image')
        new_img = upload_image(image_file, 'products')
        if new_img:
            product.image = new_img

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))

    return render_template('dashboard/product_form.html', kiosk=kiosk, product=product)


# Settings & Branding
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
    
    phone = request.form.get('whatsapp_number', '').strip()
    if phone:
        kiosk.whatsapp_number = clean_phone_number(phone)

    logo_file = request.files.get('logo')
    hero_file = request.files.get('hero_image')
    bg_file = request.files.get('background_image')

    new_logo = upload_image(logo_file, 'logos')
    new_hero = upload_image(hero_file, 'heroes')
    new_bg = upload_image(bg_file, 'backgrounds')

    if new_logo: kiosk.logo = new_logo
    if new_hero: kiosk.hero_image = new_hero
    if new_bg: kiosk.background_image = new_bg

    db.session.commit()
    flash(f'Settings for "{kiosk.name}" updated successfully!', 'success')
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
            ad.banner_image = new_banner

        db.session.commit()
        flash(f'Ad Slot #{slot_num} updated!', 'success')

    return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))





# 2. Update delete_product to clean up image:
@dashboard_bp.route('/<kiosk_slug>/product/<int:id>/delete', methods=['POST'])
@login_required
def delete_product(kiosk_slug, id):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    product = Product.query.filter_by(id=id, store_id=kiosk.id).first_or_404()
    
    # 🧹 Auto-delete image from Cloudinary/Local storage
    delete_image(product.image, 'products')

    db.session.delete(product)
    db.session.commit()
    flash('Product removed and storage cleaned up.', 'info')
    return redirect(url_for('dashboard.manage_kiosk', kiosk_slug=kiosk.slug))


# 3. Update delete_kiosk to clean up all kiosk assets:
@dashboard_bp.route('/<kiosk_slug>/delete', methods=['POST'])
@login_required
def delete_kiosk(kiosk_slug):
    kiosk = Store.query.filter_by(slug=kiosk_slug).first_or_404()
    if kiosk.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    name = kiosk.name

    # 🧹 Auto-delete kiosk media (Logo, Hero, Background, and all product pictures)
    delete_image(kiosk.logo, 'logos')
    delete_image(kiosk.hero_image, 'heroes')
    delete_image(kiosk.background_image, 'backgrounds')
    for p in kiosk.products.all():
        delete_image(p.image, 'products')

    db.session.delete(kiosk)
    db.session.commit()
    flash(f'Kiosk "{name}" and all associated media deleted permanently.', 'info')
    return redirect(url_for('dashboard.overview'))
