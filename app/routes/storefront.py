import uuid
import json
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort
from app import db
from app.models import Store, Product, StoreAd, Order, OrderItem
from app.utils.whatsapp import clean_phone_number, build_whatsapp_order_link

storefront_bp = Blueprint('storefront', __name__)

@storefront_bp.route('/')
def landing():
    """Main marketplace discovery page showing active merchant storefronts."""
    stores = Store.query.order_by(Store.views_count.desc()).all()
    return render_template('store/landing.html', stores=stores)


@storefront_bp.route('/<store_slug>')
def store_catalog(store_slug):
    """Dynamic public storefront for a merchant."""
    store = Store.query.filter_by(slug=store_slug).first_or_404()

    # Track view count (Live analytics)
    store.views_count += 1
    db.session.commit()

    # Fetch active products
    all_products = store.products.filter_by(is_active=True).all()
    flash_sales = [p for p in all_products if p.is_flash_sale and p.stock > 0]
    regular_products = [p for p in all_products if not p.is_flash_sale]

    # Fetch active Ad Slots
    ad_slots = {
        ad.slot_number: ad for ad in store.ads.filter_by(is_active=True).all() if ad.banner_image
    }

    # 🛠️ IF MASTER ADMIN OVERRODE WITH CUSTOM HTML TEMPLATE:
    if store.custom_html and store.custom_html.strip():
        from flask import render_template_string
        return render_template_string(
            store.custom_html,
            store=store,
            flash_sales=flash_sales,
            regular_products=regular_products,
            ad_slots=ad_slots
        )

    # Otherwise, render default theme
    return render_template(
        'store/catalog.html',
        store=store,
        flash_sales=flash_sales,
        regular_products=regular_products,
        ad_slots=ad_slots
    )


@storefront_bp.route('/ad/click/<int:ad_id>')
def click_ad(ad_id):
    """Tracks sponsor ad clicks and redirects to destination URL."""
    ad = StoreAd.query.get_or_404(ad_id)
    ad.clicks_count += 1
    db.session.commit()
    return redirect(ad.target_link or url_for('storefront.store_catalog', store_slug=ad.store.slug))


@storefront_bp.route('/<store_slug>/checkout', methods=['POST'])
def checkout(store_slug):
    """Processes customer checkout, creates order in DB, and returns WhatsApp URL."""
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

    # 1. Create Order Container
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

    # 2. Process Order Items & Deduct Stock
    for item in cart_items:
        product_id = item.get('product_id')
        qty = int(item.get('quantity', 1))
        chosen_variants = item.get('variants', '')  # e.g., "Screen Size: 60 inch"

        product = Product.query.filter_by(id=product_id, store_id=store.id).first()
        if not product or product.stock < qty:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Sorry, '{product.name if product else 'Item'}' is out of stock."}), 400

        unit_price = product.current_price
        subtotal = unit_price * qty
        total_amount += subtotal

        # Deduct stock
        product.stock -= qty

        # Add OrderItem
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

    # 3. Build WhatsApp Redirect Link
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
    """Public customer invoice & digital receipt with client-side PDF download."""
    order = Order.query.filter_by(order_ref=order_ref).first_or_404()
    store = order.store
    return render_template('store/receipt.html', order=order, store=store)
