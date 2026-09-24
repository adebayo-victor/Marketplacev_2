import json
from flask import Blueprint, request, jsonify
from app import db
from app.models import Store, AbandonedCart
from app.utils.whatsapp import clean_phone_number
from app.utils.backup import perform_db_backup

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
