import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from app import db
from app.models import Order, AuditLog, AbandonedCart
from app.utils.audit import void_order, refund_order
from app.utils.whatsapp import build_abandoned_cart_nudge_link

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/')
@login_required
def audit_ledger():
    """Displays the immutable financial audit log of all voids, refunds, and changes."""
    store = current_user.store
    logs = store.audit_logs.order_by(AuditLog.timestamp.desc()).all()
    return render_template('dashboard/audits.html', store=store, logs=logs)


@audit_bp.route('/export')
@login_required
def export_audit_json():
    """Dynamically exports the store's audit ledger as a downloadable JSON report."""
    store = current_user.store
    logs = store.audit_logs.order_by(AuditLog.timestamp.desc()).all()
    data = [log.to_dict() for log in logs]
    
    json_output = json.dumps(data, indent=4)
    return Response(
        json_output,
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename=audit_report_{store.slug}.json"}
    )


@audit_bp.route('/order/<int:order_id>/void', methods=['POST'])
@login_required
def process_void(order_id):
    """Voids an order, restores inventory stock, and logs to ledger."""
    store = current_user.store
    order = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    reason = request.form.get('reason', 'Cancelled by merchant').strip()

    if void_order(order, reason=reason):
        flash(f'Order #{order.order_ref} voided successfully. Product stock has been restored.', 'info')
    else:
        flash(f'Order #{order.order_ref} is already voided or refunded.', 'warning')

    return redirect(url_for('dashboard.overview'))


@audit_bp.route('/order/<int:order_id>/refund', methods=['POST'])
@login_required
def process_refund(order_id):
    """Records a refund and financial ledger entry."""
    store = current_user.store
    order = Order.query.filter_by(id=order_id, store_id=store.id).first_or_404()
    amount = float(request.form.get('amount', order.total_amount) or order.total_amount)
    reason = request.form.get('reason', 'Customer refund').strip()

    if refund_order(order, refund_amount=amount, reason=reason):
        flash(f'Refund of {store.currency}{amount:,.2f} recorded for Order #{order.order_ref}.', 'success')
    else:
        flash(f'Order #{order.order_ref} has already been processed for refund.', 'warning')

    return redirect(url_for('dashboard.overview'))


@audit_bp.route('/leads')
@login_required
def lost_leads():
    """Lists uncompleted checkouts with direct 1-click WhatsApp nudge links."""
    store = current_user.store
    carts = store.abandoned_carts.filter_by(recovered=False).order_by(AbandonedCart.created_at.desc()).all()
    
    # Pre-generate WhatsApp nudge links
    leads_data = []
    for c in carts:
        nudge_link = build_abandoned_cart_nudge_link(
            customer_phone=c.customer_phone,
            customer_name=c.customer_name,
            store_name=store.name,
            total_amount=c.total_amount,
            currency=store.currency
        )
        leads_data.append({"cart": c, "nudge_link": nudge_link})

    return render_template('dashboard/leads.html', store=store, leads=leads_data)


@audit_bp.route('/leads/<int:lead_id>/recovered', methods=['POST'])
@login_required
def mark_lead_recovered(lead_id):
    """Marks an abandoned cart as recovered."""
    store = current_user.store
    cart = AbandonedCart.query.filter_by(id=lead_id, store_id=store.id).first_or_404()
    cart.recovered = True
    db.session.commit()
    flash(f'Lead for {cart.customer_name} marked as recovered!', 'success')
    return redirect(url_for('audit.lost_leads'))
