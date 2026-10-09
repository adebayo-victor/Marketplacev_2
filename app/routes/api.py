import json
from flask import Blueprint, request, jsonify
from app import db
from app.models import Store, AbandonedCart
from app.utils.whatsapp import clean_phone_number
from app.utils.backup import perform_db_backup
import os

api_bp = Blueprint('api', __name__)

@api_bp.route('/cart/capture-lead', methods=['POST'])
def capture_lead():
    """Asynchronously records customer info as soon as they type into the checkout form."""
    data = request.get_json() or {}
    store_slug = data.get('store_slug')
    store = Store.query.filter_by(slug=store_slug).first()

    if not store:
        return jsonify({"status": "error", "message": "Store not found"}), 404

    customer_name = data.get('customer_name', '').strip()
    customer_phone = clean_phone_number(data.get('customer_phone', '').strip())
    cart_items = data.get('cart', [])
    total_amount = float(data.get('total', 0.0))

    if not customer_phone or not customer_name:
        return jsonify({"status": "ignored"}), 200

    # Save to AbandonedCart table
    cart_record = AbandonedCart(
        store_id=store.id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        cart_json=json.dumps(cart_items),
        total_amount=total_amount,
        recovered=False
    )
    db.session.add(cart_record)
    db.session.commit()

    return jsonify({"status": "success", "lead_id": cart_record.id})


@api_bp.route('/backup', methods=['POST', 'GET'])
def trigger_backup():
    """Manual or cron-triggered SQLite database snapshot backup."""
    backup_file = perform_db_backup(max_backups=7)
    return jsonify({
        "status": "success",
        "backup_file": backup_file,
        "message": "SQLite database snapshot created successfully."
    })


@api_bp.route('/health')
def health_check():
    """System health check."""
    return jsonify({"status": "healthy", "service": "Marketplace Engine v2"})


# =============================================================
# 📥 RENDER WORKER CALLBACK RECEPTOR
# =============================================================
@api_bp.route('/internal/kiosk-ready', methods=['POST'])
def internal_kiosk_ready():
    """Secure endpoint that receives generated HTML from Render and unlocks the kiosk."""
    auth_header = request.headers.get('Authorization', '')
    expected_secret = "marketplace_worker_secret_key_882"

    # 🔒 Verify Authorization Token
    if not expected_secret or auth_header != f"Bearer {expected_secret}":
        return jsonify({"status": "unauthorized", "message": "Invalid secret"}), 401

    data = request.get_json() or {}
    kiosk_id = data.get('kiosk_id')
    generated_html = data.get('custom_html')

    if not kiosk_id or not generated_html:
        return jsonify({"status": "error", "message": "Missing kiosk_id or custom_html"}), 400

    store = Store.query.get(kiosk_id)
    if not store:
        return jsonify({"status": "error", "message": "Store not found"}), 404

    # 🔓 Save the bespoke template and flip status to ready
    store.custom_html = generated_html
    store.build_status = 'ready'
    db.session.commit()

    print(f"🎉 Store #{store.id} ({store.name}) successfully saved and set to READY!")
    return jsonify({"status": "success", "message": "Store updated"}), 200
