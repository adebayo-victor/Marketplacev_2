import os
import json
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Store, Product, StoreAd, Order
from app.utils.whatsapp import clean_phone_number

dashboard_bp = Blueprint('dashboard', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_image(file, subfolder):
    if not file or file.filename == '':
        return None
    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        dest_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        os.makedirs(dest_folder, exist_ok=True)
        # Unique prefix using timestamp
        import time
        unique_name = f"{int(time.time())}_{filename}"
        file.save(os.path.join(dest_folder, unique_name))
        return unique_name
    return None


@dashboard_bp.route('/')
@login_required
def overview():
    store = current_user.store
    if not store:
        flash('Please create a storefront first.', 'warning')
        return redirect(url_for('auth.register'))

    products_count = store.products.count()
    leads_count = store.orders.count()
    recent_orders = store.orders.order_by(Order.created_at.desc()).limit(10).all()

    # Calculate visit-to-lead conversion rate
    conversion_rate = 0.0
    if store.views_count > 0:
        conversion_rate = round((leads_count / store.views_count) * 100, 1)

    return render_template(
        'dashboard/overview.html',
        store=store,
        products_count=products_count,
        leads_count=leads_count,
        conversion_rate=conversion_rate,
        recent_orders=recent_orders
    )


@dashboard_bp.route('/products')
@login_required
def products():
    store = current_user.store
    all_products = store.products.order_by(Product.created_at.desc()).all()
    return render_template('dashboard/products.html', store=store, products=all_products)


@dashboard_bp.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    store = current_user.store

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        original_price = float(request.form.get('original_price', 0) or 0)
        discount_price = request.form.get('discount_price', '').strip()
        stock = int(request.form.get('stock', 1) or 1)
        is_flash_sale = True if request.form.get('is_flash_sale') else False

        # Parse Custom Dynamic Attributes (e.g. Screen Size: 45, 60)
        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_values[]')
        attributes_dict = {}

        for a_name, a_vals in zip(attr_names, attr_values):
            clean_name = a_name.strip()
            if clean_name and a_vals.strip():
                # Split comma-separated options into clean array
                options = [v.strip() for v in a_vals.split(',') if v.strip()]
                if options:
                    attributes_dict[clean_name] = options

        # Handle Image Upload
        image_file = request.files.get('image')
        image_name = save_uploaded_image(image_file, 'products') or 'default_product.png'

        product = Product(
            store_id=store.id,
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

        flash('Product added to inventory successfully!', 'success')
        return redirect(url_for('dashboard.products'))

    return render_template('dashboard/product_form.html', store=store, product=None)


@dashboard_bp.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    store = current_user.store
    product = Product.query.filter_by(id=id, store_id=store.id).first_or_404()

    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.description = request.form.get('description', '').strip()
        product.original_price = float(request.form.get('original_price', 0) or 0)
        
        discount_price = request.form.get('discount_price', '').strip()
        product.discount_price = float(discount_price) if discount_price else None
        
        product.stock = int(request.form.get('stock', 1) or 1)
        product.is_flash_sale = True if request.form.get('is_flash_sale') else False

        # Parse Custom Attributes
        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_values[]')
        attributes_dict = {}

        for a_name, a_vals in zip(attr_names, attr_values):
            clean_name = a_name.strip()
            if clean_name and a_vals.strip():
                options = [v.strip() for v in a_vals.split(',') if v.strip()]
                if options:
                    attributes_dict[clean_name] = options

        product.attributes_json = json.dumps(attributes_dict)

        # Handle Image Replacement
        image_file = request.files.get('image')
        new_image = save_uploaded_image(image_file, 'products')
        if new_image:
            product.image = new_image

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('dashboard.products'))

    return render_template('dashboard/product_form.html', store=store, product=product)


@dashboard_bp.route('/products/<int:id>/delete', methods=['POST'])
@login_required
def delete_product(id):
    store = current_user.store
    product = Product.query.filter_by(id=id, store_id=store.id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    flash('Product removed from inventory.', 'info')
    return redirect(url_for('dashboard.products'))


@dashboard_bp.route('/ads', methods=['GET', 'POST'])
@login_required
def manage_ads():
    store = current_user.store
    ads = StoreAd.query.filter_by(store_id=store.id).order_by(StoreAd.slot_number.asc()).all()

    if request.method == 'POST':
        slot_num = int(request.form.get('slot_number'))
        ad = StoreAd.query.filter_by(store_id=store.id, slot_number=slot_num).first()
        
        if ad:
            ad.target_link = request.form.get('target_link', '').strip()
            ad.is_active = True if request.form.get('is_active') else False
            
            banner_file = request.files.get('banner_image')
            new_banner = save_uploaded_image(banner_file, 'ads')
            if new_banner:
                ad.banner_image = new_banner
            
            db.session.commit()
            flash(f'Ad Slot #{slot_num} updated successfully!', 'success')
            return redirect(url_for('dashboard.manage_ads'))

    return render_template('dashboard/ads.html', store=store, ads=ads)


@dashboard_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    store = current_user.store

    if request.method == 'POST':
        store.name = request.form.get('name', '').strip()
        store.bio = request.form.get('bio', '').strip()
        store.currency = request.form.get('currency', '₦').strip()
        
        # Public Stats Toggle (The Social Proof Feature!)
        store.show_public_stats = True if request.form.get('show_public_stats') else False
        
        raw_whatsapp = request.form.get('whatsapp_number', '').strip()
        if raw_whatsapp:
            store.whatsapp_number = clean_phone_number(raw_whatsapp)

        # Store Logo Upload
        logo_file = request.files.get('logo')
        new_logo = save_uploaded_image(logo_file, 'logos')
        if new_logo:
            store.logo = new_logo

        db.session.commit()
        flash('Storefront settings updated successfully!', 'success')
        return redirect(url_for('dashboard.settings'))

    return render_template('dashboard/settings.html', store=store)
