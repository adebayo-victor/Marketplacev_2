import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from authlib.integrations.flask_client import OAuth
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'
oauth = OAuth()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    oauth.init_app(app)

    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID') or os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET') or os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        for sub in ['products', 'ads', 'logos', 'heroes', 'backgrounds']:
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub), exist_ok=True)
    except OSError:
        pass

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.storefront import storefront_bp
    from app.routes.audit import audit_bp
    from app.routes.api import api_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(storefront_bp)
    app.register_blueprint(audit_bp, url_prefix='/dashboard/audit')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    with app.app_context():
        db.create_all()
        # 🛡️ Seamless PostgreSQL Migration (Zero DB wipe required!)
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE products ADD COLUMN IF NOT EXISTS is_unlimited_stock BOOLEAN DEFAULT FALSE"))
                conn.execute(db.text("ALTER TABLE stores ADD COLUMN IF NOT EXISTS build_status VARCHAR(20) DEFAULT 'ready'"))
                conn.commit()
        except Exception as e:
            print(f"Auto-migration notice: {e}")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app
