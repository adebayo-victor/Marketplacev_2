import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)  # <-- The username property
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One merchant owns many kiosks
    stores = db.relationship('Store', backref='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Store(db.Model):
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    bio = db.Column(db.Text, default='Welcome to our official store!')
    
    # Visual Branding Media
    logo = db.Column(db.String(500), default='default_logo.png')
    hero_image = db.Column(db.String(500), default='')
    background_image = db.Column(db.String(500), default='')
    
    whatsapp_number = db.Column(db.String(20), nullable=False)
    currency = db.Column(db.String(10), default='₦')
    
    # Social Proof & Link Previews
    views_count = db.Column(db.Integer, default=0)
    show_public_stats = db.Column(db.Boolean, default=False)
    custom_html = db.Column(db.Text, default='')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    banner_image = db.Column(db.String(500), nullable=True)
    target_link = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=False)
    clicks_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default='')
    image = db.Column(db.String(500), default='default_product.png')
    
    original_price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)
    is_flash_sale = db.Column(db.Boolean, default=False)
    
    stock = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    attributes_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def current_price(self):
        if self.discount_price and self.discount_price > 0:
            return self.discount_price
        return self.original_price

    @property
    def has_discount(self):
        return bool(self.discount_price and self.discount_price < self.original_price)

    def get_attributes(self):
        try:
            return json.loads(self.attributes_json)
        except Exception:
            return {}

    def set_attributes(self, attr_dict):
        self.attributes_json = json.dumps(attr_dict)


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    order_ref = db.Column(db.String(32), unique=True, nullable=False, index=True)
    
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(25), nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)
    
    status = db.Column(db.String(20), default='pending')
    total_amount = db.Column(db.Float, nullable=False)
    items_summary = db.Column(db.Text, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    product_name = db.Column(db.String(150), nullable=False)
    selected_variants = db.Column(db.String(255), default='')
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    subtotal = db.Column(db.Float, nullable=False)


class AbandonedCart(db.Model):
    __tablename__ = 'abandoned_carts'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(25), nullable=False)
    cart_json = db.Column(db.Text, nullable=False)
    total_amount = db.Column(db.Float, default=0.0)
    recovered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    order_ref = db.Column(db.String(32), nullable=True)
    action_type = db.Column(db.String(50), nullable=False)
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
