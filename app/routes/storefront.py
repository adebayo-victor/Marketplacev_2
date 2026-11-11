import os
import uuid
import json
import secrets
import markdown
 from app.utils.obfuscate import encode_product_id, decode_product_id
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort, flash, Response, current_app
from flask_login import current_user
from app import db
from app.models import Store, Product, StoreAd, Order, OrderItem
from app.utils.whatsapp import clean_phone_number, build_whatsapp_order_link
from flask_login import login_required, current_user  # 👈 THIS WAS MISSING
from app import db                                    # 👈 MAKE SURE THIS IS HERE
from app.models import Product, Store, User           # 👈 MAKE SURE THESE ARE HERE

storefront_bp = Blueprint('storefront', __name__)

# ... (your existing routes) ...


storefront_bp = Blueprint('storefront', __name__)

@storefront_bp.route('/')
def landing():
    stores = Store.query.filter_by(is_active=True).order_by(Store.views_count.desc()).all()
    return render_template('store/landing.html', stores=stores)

# -------------------------------------------------------------
# 📦 STUDENT ORDER HISTORY
# -------------------------------------------------------------
@storefront_bp.route('/my-orders')
@login_required
def my_orders():
    # Gate: Only students can access this
    if not current_user.is_student:
        flash('This page is exclusive to verified students.', 'warning')
        return redirect(url_for('dashboard.overview'))

    # Fetch orders placed by this student via the Central Hub
    # (We filter by customer_name matching their username, and checkout_method)
    orders = Order.query.filter_by(
        customer_name=current_user.username,
        checkout_method='central_hub'
    ).order_by(Order.created_at.desc()).all()

    return render_template('store/my_orders.html', orders=orders)

# -------------------------------------------------------------
# 📤 PUBLIC PRODUCT SHARE LINK
# -------------------------------------------------------------


@storefront_bp.route('/p/<token>')
def public_product(token):
    # 1. Decode the token back to the real ID
    product_id = decode_product_id(token)
    
    # 2. If the token was fake or tampered with, return 404
    if not product_id:
        abort(404)
        
    product = Product.query.get_or_404(product_id)
    store = product.store
    
    # Security checks
    if not product.is_active or not store.is_active or store.build_status != 'ready':
        abort(404)
        
    return render_template('store/product_share.html', product=product, store=store))

# -------------------------------------------------------------
# 🎓 CENTRAL CAMPUS HUB
# -------------------------------------------------------------
@storefront_bp.route('/central')
@login_required
def central_hub():
    if not current_user.is_student:
        flash(' The Central Campus Hub is exclusive to verified students.', 'warning')
        return redirect(url_for('dashboard.account_settings'))

    if not current_user.phone_number or not current_user.phone_number.strip():
        flash(' Please add your WhatsApp phone number in Settings before accessing the Hub.', 'warning')
        return redirect(url_for('dashboard.account_settings'))

    universities = db.session.query(User.university_name)\
        .join(Store, User.id == Store.user_id)\
        .filter(User.is_student == True, Store.is_active == True, User.university_name.isnot(None))\
        .distinct().all()
    universities = sorted([u[0] for u in universities if u[0]])

    default_uni = current_user.university_name if current_user.university_name else 'All'
    filter_uni = request.args.get('university', default_uni)
    search_query = request.args.get('search', '').strip()
    
    query = Product.query.join(Store).join(User, Store.user_id == User.id)\
        .filter(Store.is_active == True, User.is_student == True, Product.show_in_hub == True)
    
    if filter_uni and filter_uni != 'All':
        query = query.filter(User.university_name == filter_uni)
    
    if search_query:
        query = query.filter(Product.name.ilike(f'%{search_query}%'))

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    products = pagination.items

    return render_template(
        'store/central_hub.html', 
        products=products, 
        universities=universities, 
        current_uni=filter_uni,
        current_search=search_query,
        pagination=pagination
    )




# -------------------------------------------------------------
# 🛒 CENTRAL HUB BULK CHECKOUT
# -------------------------------------------------------------
@storefront_bp.route('/central/checkout', methods=['POST'])
@login_required
def central_checkout_bulk():
    if not current_user.is_student:
        return jsonify({'status': 'error', 'message': 'Access denied.'}), 403

    data = request.get_json()
    cart_items = data.get('items', [])
    
    if not cart_items:
        return jsonify({'status': 'error', 'message': 'Cart is empty.'}), 400

    # Group cart items by store_id
    orders_by_store = {}
    for item in cart_items:
        product = Product.query.get(item['id'])
        if not product or not product.is_active or not product.store.is_active:
            continue # Skip invalid products
            
        store_id = product.store.id
        if store_id not in orders_by_store:
            orders_by_store[store_id] = {
                'store': product.store,
                'items': [],
                'total': 0.0,
                'summary_lines': []
            }
        
        subtotal = product.current_price * item['qty']
        orders_by_store[store_id]['items'].append({
            'product': product,
            'qty': item['qty'],
            'subtotal': subtotal
        })
        orders_by_store[store_id]['total'] += subtotal
        orders_by_store[store_id]['summary_lines'].append(f"• {item['qty']}x {product.name} - ₦{subtotal:,.2f}")

    # Create an order for each merchant
    created_orders = []
    for store_id, order_data in orders_by_store.items():
        order_ref = "CH-" + secrets.token_hex(6).upper()
        
        new_order = Order(
            store_id=store_id,
            order_ref=order_ref,
            customer_name=current_user.username, 
            customer_phone=current_user.phone_number or "Student Account",  
            delivery_address="Campus Delivery (Update in profile)",
            status='pending',
            total_amount=order_data['total'],
            items_summary="\n".join(order_data['summary_lines']),
            checkout_method='central_hub' # 👈 TRIGGERS 200 COIN REWARD FOR MERCHANT
        )
        db.session.add(new_order)
        created_orders.append(order_ref)

    db.session.commit()
    
    return jsonify({
        'status': 'success', 
        'message': f'Successfully placed {len(created_orders)} order(s).',
        'order_refs': created_orders
    }), 201


@storefront_bp.route('/agent-instructions')
def agent_instructions():
    """Serves the Marketplace Agent Documentation."""
    doc_path = os.path.join(current_app.static_folder, 'docs', 'marketplace-agent.md')
    
    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(md_content, extensions=['fenced_code', 'tables', 'toc'])
    except FileNotFoundError:
        html_content = "<p>Documentation not found. Please ensure app/static/docs/marketplace-agent.md exists.</p>"

    # If an AI bot requests it with ?format=raw, give them clean plain text
    if request.args.get('format') == 'raw':
        return Response(md_content, mimetype='text/plain')

    # Otherwise, show the nice HTML page for humans
    return render_template('store/agent_instructions.html', doc_content=html_content)

@storefront_bp.route('/<store_slug>')
def store_catalog(store_slug):
    store = Store.query.filter_by(slug=store_slug).first_or_404()

    # ⏳ IF STILL ASSEMBLING IN BACKGROUND: CANNOT BE OPENED
    if store.build_status == 'building':
        flash(f'⏳ Hold on! Kiosk "{store.name}" is still being assembled by the AI engine.', 'warning')
        return redirect(url_for('dashboard.overview'))

    # 🔒 PREVIEW MODE / LOCKED CHECK
    is_preview = False
    if not store.is_active:
        is_owner = current_user.is_authenticated and (current_user.id == store.user_id or current_user.is_admin)
        if not is_owner:
            return render_template('store/locked.html', store=store, is_owing=store.has_ever_activated)
        is_preview = True

    # Only increment views if it's NOT preview mode (real customer traffic)
    if not is_preview:
        store.views_count += 1
        db.session.commit()

    all_products = store.products.filter_by(is_active=True).all()
    flash_sales = [p for p in all_products if p.is_flash_sale and p.is_available]
    regular_products = [p for p in all_products if not p.is_flash_sale]
    
    ad_slots = {
        ad.slot_number: ad for ad in store.ads.filter_by(is_active=True).all() if ad.banner_image
    }

    # ✅ FIXED: Actually return the rendered custom HTML if it exists
    if store.custom_html and store.custom_html.strip():
        try:
            from flask import render_template_string
            rendered = render_template_string(
                store.custom_html,
                store=store,
                flash_sales=flash_sales,
                regular_products=regular_products,
                ad_slots=ad_slots
            )
            if is_preview:
                banner = f'''<div style="background:#b33a3a;color:white;padding:12px;text-align:center;font-family:sans-serif;font-size:12px;font-weight:bold;position:sticky;top:0;z-index:999999;box-shadow:0 4px 15px rgba(0,0,0,0.3);">
                    🔑 PREVIEW MODE: This kiosk is currently HIDDEN from customers. 
                    <a href="/dashboard" style="color:#fef08a;text-decoration:underline;margin-left:10px;">[ACTIVATE NOW TO GO LIVE (₦5,000)]</a>
                </div>'''
                rendered = banner + rendered
            return rendered
        except Exception as e:
            print(f"Template Render Error: {e}")
            flash("Your kiosk had rendering issues. Falling back to default catalog.", 'error')

    # Fallback to default catalog.html if no custom_html
    rendered_default = render_template(
        'store/catalog.html',
        store=store,
        flash_sales=flash_sales,
        regular_products=regular_products,
        ad_slots=ad_slots,
        is_preview=is_preview
    )
    
    if is_preview:
        banner = f'''<div style="background:#b33a3a;color:white;padding:12px;text-align:center;font-family:sans-serif;font-size:12px;font-weight:bold;position:sticky;top:0;z-index:999999;box-shadow:0 4px 15px rgba(0,0,0,0.3);">
            🔑 PREVIEW MODE: This kiosk is currently HIDDEN from customers. 
            <a href="/dashboard" style="color:#fef08a;text-decoration:underline;margin-left:10px;">[ACTIVATE NOW TO GO LIVE (₦5,000)]</a>
        </div>'''
        return banner + rendered_default
        
    return rendered_default


@storefront_bp.route('/ad/click/<int:ad_id>')
def click_ad(ad_id):
    ad = StoreAd.query.get_or_404(ad_id)
    ad.clicks_count += 1
    db.session.commit()
    return redirect(ad.target_link or url_for('storefront.store_catalog', store_slug=ad.store.slug))


@storefront_bp.route('/<store_slug>/checkout', methods=['POST'])
def checkout(store_slug):
    store = Store.query.filter_by(slug=store_slug).first_or_404()
    data = request.get_json() or {}

    customer_name = data.get('customer_name', '').strip()
    customer_phone = data.get('customer_phone', '').strip()
    delivery_address = data.get('delivery_address', '').strip()
    cart_items = data.get('cart', [])

    if not customer_name or not customer_phone or not delivery_address or not cart_items:
        return jsonify({"status": "error", "message": "All customer and cart fields are required."}), 400

    order_ref = str(uuid.uuid4())[:8].upper()
    total_amount = 0.0
    summary_lines = []

    order = Order(
        store_id=store.id,
        order_ref=order_ref,
        customer_name=customer_name,
        customer_phone=clean_phone_number(customer_phone),
        delivery_address=delivery_address,
        total_amount=0.0,
        items_summary='',
        status='pending'
    )
    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        product_id = item.get('product_id')
        qty = int(item.get('quantity', 1))
        chosen_variants = item.get('variants', '')

        product = Product.query.filter_by(id=product_id, store_id=store.id).first()
        
        if not product or not product.is_available:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Sorry, '{product.name if product else 'Item'}' is out of stock."}), 400

        unit_price = product.current_price
        subtotal = unit_price * qty
        total_amount += subtotal

        if not product.is_unlimited_stock:
            product.stock -= qty

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            selected_variants=chosen_variants,
            unit_price=unit_price,
            quantity=qty,
            subtotal=subtotal
        )
        db.session.add(order_item)

        variant_text = f" ({chosen_variants})" if chosen_variants else ""
        summary_lines.append(f"• {qty}x {product.name}{variant_text} - {store.currency}{subtotal:,.2f}")

    order.total_amount = total_amount
    order.items_summary = "\n".join(summary_lines)
    db.session.commit()

    whatsapp_url = build_whatsapp_order_link(
        store_phone=store.whatsapp_number,
        store_name=store.name,
        order=order
    )

    return jsonify({
        "status": "success",
        "order_ref": order.order_ref,
        "whatsapp_url": whatsapp_url
    })


@storefront_bp.route('/receipt/<order_ref>')
def public_receipt(order_ref):
    order = Order.query.filter_by(order_ref=order_ref).first_or_404()
    store = order.store
    return render_template('store/receipt.html', order=order, store=store)
