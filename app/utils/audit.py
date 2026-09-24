from datetime import datetime
from app import db
from app.models import AuditLog, Order, Product

def log_action(store_id: int, action_type: str, order_ref: str = None, amount: float = 0.0, reason: str = ""):
    """
    Creates an immutable audit log entry in the database.
    """
    entry = AuditLog(
        store_id=store_id,
        action_type=action_type,
        order_ref=order_ref,
        amount=amount,
        reason=reason,
        timestamp=datetime.utcnow()
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def void_order(order: Order, reason: str = "Order cancelled by merchant") -> bool:
    """
    Voids an order, restores inventory stock for each product, and records an audit log.
    """
    if order.status in ['voided', 'refunded']:
        return False  # Already cancelled

    # 1. Restore product stock counts
    for item in order.items.all():
        if item.product_id:
            product = Product.query.get(item.product_id)
            if product:
                product.stock += item.quantity

    # 2. Update order status
    order.status = 'voided'
    
    # 3. Write to audit ledger
    log_action(
        store_id=order.store_id,
        action_type='VOID_ORDER',
        order_ref=order.order_ref,
        amount=order.total_amount,
        reason=reason
    )
    
    db.session.commit()
    return True


def refund_order(order: Order, refund_amount: float, reason: str = "Customer requested refund") -> bool:
    """
    Marks an order as refunded (full or partial) and records the financial audit entry.
    """
    if order.status == 'refunded':
        return False

    order.status = 'refunded'
    
    log_action(
        store_id=order.store_id,
        action_type='REFUND_ORDER',
        order_ref=order.order_ref,
        amount=refund_amount,
        reason=reason
    )
    
    db.session.commit()
    return True
