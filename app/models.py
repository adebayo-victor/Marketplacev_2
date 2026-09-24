import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    store = db.relationship('Store', backref='owner', uselist=False, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Store(db.Model):
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text, default='Welcome to our official store!')
    logo = db.Column(db.String(255), default='default_logo.png')
    whatsapp_number = db.Column(db.String(20), nullable=False)  # e.g., "2348012345678"
    currency = db.Column(db.String(10), default='₦')
    
    # Social Proof & Link Preview feature
    views_count = db.Column(db.Integer, default=0)
    show_public_stats = db.Column(db.Boolean, default=False)  # Toggle to show/hide total views in meta tags & directory
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    products = db.relationship('Product', backref='store', lazy='dynamic', cascade="all, delete-orphan")
    orders = db.relationship('Order', backref='store', lazy='dynamic', cascade="all, delete-orphan")
    ads = db.relationship('StoreAd', backref='store', lazy='dynamic', cascade="all, delete-orphan")
    abandoned_carts = db.relationship('AbandonedCart', backref='store', lazy='dynamic', cascade="all, delete-orphan")
    audit_logs = db.relationship('AuditLog', backref='store', lazy='dynamic', cascade="all, delete-orphan")


class StoreAd(db.Model):
    """3 Monetization Ad Slots per Store"""
    __tablename__ = 'store_ads'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    slot_number = db.Column(db.Integer, nullable=False)  # 1: Header, 2: Mid-catalog, 3: Footer
    banner_image = db.Column(db.String(255), nullable=True)
    target_link = db.Column(db.String(255), nullable=True)  # Sponsor's WhatsApp or website URL
    is_active = db.Column(db.Boolean, default=False)
    clicks_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default='')
    image = db.Column(db.String(255), default='default_product.png')
    
    # Pricing & Promotions
    original_price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)  # If set, slashes original_price
    is_flash_sale = db.Column(db.Boolean, default=False)  # If True, pinned to top carousel
    
    stock = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    
    # Dynamic Custom Variants stored as JSON string
    # e.g., '{"Screen Size": ["45 inch", "60 inch"], "Color": ["Black", "Silver"]}'
    attributes_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def current_price(self):
        """Returns discount price if active, otherwise original price"""
        if self.discount_price and self.discount_price > 0:
            return self.discount_price
        return self.original_price

    @property
    def has_discount(self):
        return bool(self.discount_price and self.discount_price < self.original_price)

    def get_attributes(self):
        """Parses JSON attributes into a Python dictionary"""
        try:
            return json.loads(self.attributes_json)
        except Exception:
            return {}

    def set_attributes(self, attr_dict):
        """Saves a Python dictionary as JSON string"""
        self.attributes_json = json.dumps(attr_dict)


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    order_ref = db.Column(db.String(32), unique=True, nullable=False, index=True)  # e.g. "ORD-94A1B2"
    
    # Customer Details
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(25), nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)
    
    # Order Status Lifecycle: pending, confirmed, paid, shipped, completed, voided, refunded
    status = db.Column(db.String(20), default='pending')
    total_amount = db.Column(db.Float, nullable=False)
    items_summary = db.Column(db.Text, nullable=False)  # Formatted text summary of items purchased
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(150), nullable=False)
    selected_variants = db.Column(db.String(255), default='')  # e.g., "Screen Size: 60 inch | Color: Black"
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    subtotal = db.Column(db.Float, nullable=False)


class AbandonedCart(db.Model):
    """Captures uncompleted checkouts for WhatsApp recovery nudges"""
    __tablename__ = 'abandoned_carts'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(25), nullable=False)
    cart_json = db.Column(db.Text, nullable=False)  # JSON snapshot of products & chosen variants
    total_amount = db.Column(db.Float, default=0.0)
    recovered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    """Replaces loose void.txt and refund_audit_report.json with structured database audits"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    order_ref = db.Column(db.String(32), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)  # e.g., 'VOID_ORDER', 'REFUND_ORDER', 'RESTOCK'
    amount = db.Column(db.Float, default=0.0)
    reason = db.Column(db.Text, default='')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "order_ref": self.order_ref,
            "action": self.action_type,
            "amount": self.amount,
            "reason": self.reason,
            "timestamp": self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
