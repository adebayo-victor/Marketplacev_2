import urllib.parse

def clean_phone_number(phone: str) -> str:
    """Cleans phone numbers into international format without '+' or spaces."""
    cleaned = ''.join(filter(str.isdigit, str(phone)))
    if cleaned.startswith('0') and len(cleaned) == 11:
        cleaned = '234' + cleaned[1:]
    return cleaned


def build_whatsapp_order_link(store_phone: str, store_name: str, order) -> str:
    """Generates WhatsApp URL with order breakdown + viral platform watermark."""
    phone = clean_phone_number(store_phone)
    
    message_lines = [
        f"🛍️ *NEW ORDER FOR {store_name.upper()}*",
        f"Order Ref: *#{order.order_ref}*",
        "--------------------------------",
        "*Items Ordered:*",
        order.items_summary,
        "--------------------------------",
        f"💰 *Total Amount:* {order.store.currency}{order.total_amount:,.2f}",
        "",
        "📍 *Customer Details:*",
        f"• Name: {order.customer_name}",
        f"• Phone: {order.customer_phone}",
        f"• Address: {order.delivery_address}",
        "",
        "Please confirm item availability and send payment details. Thank you!",
        "--------------------------------",
        "⚡ _Created with Marketplace_",
        "_Launch your kiosk free at: https://marketplace.app_"
    ]
    
    raw_message = "\n".join(message_lines)
    encoded_message = urllib.parse.quote(raw_message)
    return f"https://wa.me/{phone}?text={encoded_message}"


def build_receipt_share_link(customer_phone: str, store_name: str, order_ref: str, receipt_url: str) -> str:
    phone = clean_phone_number(customer_phone)
    message = (
        f"Hello! Thank you for shopping with *{store_name}*.\n\n"
        f"Your order *#{order_ref}* has been confirmed.\n"
        f"View and download your official receipt here:\n{receipt_url}\n\n"
        f"We appreciate your business!\n\n"
        f"⚡ _Powered by Marketplace_"
    )
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded_message}"


def build_abandoned_cart_nudge_link(customer_phone: str, customer_name: str, store_name: str, total_amount: float, currency: str) -> str:
    phone = clean_phone_number(customer_phone)
    message = (
        f"Hello {customer_name}! 👋\n\n"
        f"We noticed you were checking out items worth *{currency}{total_amount:,.2f}* on *{store_name}*, "
        f"but didn't complete your order.\n\n"
        f"Did you run into any issues, or would you like help completing your order?"
    )
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded_message}"
