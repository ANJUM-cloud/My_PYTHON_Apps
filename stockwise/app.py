import math
import os
from datetime import date

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

try:  # python-dotenv lets `.env` work locally; it is optional in production
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

APP_TITLE = "StockWise"
APP_SLUG = "stockwise"
DEFAULT_SECRET = "dev-only-change-this-secret"

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


# ---------------------------------------------------------------- models
# Models live at module level so create_app() can be called many times
# (tests, gunicorn factory) without redefining tables on the shared metadata.
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    items = db.relationship("Product", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    quantity = db.Column(db.Integer, default=0)
    unit_price = db.Column(db.Float, default=0.0)
    reorder_level = db.Column(db.Integer, default=5)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- helpers
def parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError("Enter a valid date.") from None


def parse_int(raw, label, default=0, minimum=0, maximum=1_000_000_000):
    raw = (raw or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}.")
    return value


def parse_price(raw, label, maximum=1_000_000_000):
    raw = (raw or "").strip()
    if not raw:
        return 0.0
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{label} must be a number.") from None
    if not math.isfinite(value) or value < 0 or value > maximum:
        raise ValueError(f"{label} must be a valid amount of 0 or more.")
    return round(value, 2)


def clean_title(form, label):
    title = form.get("title", "").strip()
    if not title:
        raise ValueError(f"{label} is required.")
    if len(title) > 160:
        raise ValueError(f"{label} must be 160 characters or fewer.")
    return title


def clean_text(form, name, limit=5000):
    value = form.get(name, "").strip()
    if len(value) > limit:
        raise ValueError(f"{name.capitalize()} is too long.")
    return value


def parse_fields(form):
    """Validate form input and return a dict of model fields. Raises ValueError."""
    return {
        "title": clean_title(form, "Product name"),
        "description": clean_text(form, "description"),
        "quantity": parse_int(form.get("quantity"), "Quantity"),
        "unit_price": parse_price(form.get("unit_price"), "Unit price"),
        "reorder_level": parse_int(form.get("reorder_level"), "Reorder level", default=5),
    }


TEMPLATE_CONTEXT = {}


def normalise_database_url(url):
    # Render hands out postgres:// or postgresql://. Name the driver explicitly (psycopg2,
    # installed from requirements.txt) because newer SQLAlchemy defaults to a different driver.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


# ------------------------------------------------------------ app factory
def create_app(test_config=None):
    app = Flask(__name__)
    secure_cookie = os.environ.get("COOKIE_SECURE", "0") == "1"
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", DEFAULT_SECRET),
        SQLALCHEMY_DATABASE_URI=normalise_database_url(os.environ.get("DATABASE_URL", "sqlite:///app.db")),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=secure_cookie,
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    if secure_cookie and app.config["SECRET_KEY"] == DEFAULT_SECRET:
        raise RuntimeError("Set a strong SECRET_KEY environment variable before running with COOKIE_SECURE=1.")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    csrf.init_app(app)

    @app.context_processor
    def globals_for_templates():
        return {"app_title": APP_TITLE}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if len(password) < 10:
                flash("Password must contain at least 10 characters.", "error")
            elif len(password) > 200:
                flash("Password is too long.", "error")
            elif not email or len(email) > 255 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                flash("Enter a valid, unused email.", "error")
            elif User.query.filter_by(email=email).first():
                flash("Enter a valid, unused email.", "error")
            else:
                user = User(email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for("dashboard"))
        return render_template("auth.html", mode="Create account")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(request.form.get("password", "")):
                login_user(user)
                return redirect(url_for("dashboard"))
            flash("Email or password was not recognised.", "error")
        return render_template("auth.html", mode="Sign in")

    @app.post("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        items = Product.query.filter_by(user_id=current_user.id).order_by(Product.id.desc()).all()
        return render_template("dashboard.html", items=items, total=len(items), **TEMPLATE_CONTEXT)

    @app.post("/items/create")
    @login_required
    def create_item():
        try:
            fields = parse_fields(request.form)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("dashboard"))
        db.session.add(Product(user_id=current_user.id, **fields))
        db.session.commit()
        flash("Record created.", "success")
        return redirect(url_for("dashboard"))

    def owned_item_or_404(item_id):
        item = db.session.get(Product, item_id)
        if item is None or item.user_id != current_user.id:
            abort(404)
        return item

    @app.post("/items/<int:item_id>/update")
    @login_required
    def update_item(item_id):
        item = owned_item_or_404(item_id)
        try:
            fields = parse_fields(request.form)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("dashboard"))
        for name, value in fields.items():
            setattr(item, name, value)
        db.session.commit()
        flash("Record updated.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/items/<int:item_id>/delete")
    @login_required
    def delete_item(item_id):
        item = owned_item_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        flash("Record deleted.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:  # database unreachable
            return {"status": "error", "application": APP_SLUG, "database": "unreachable"}, 503
        return {"status": "ok", "application": APP_SLUG, "database": "ok"}, 200

    with app.app_context():
        db.create_all()
    return app


if __name__ == "__main__":
    create_app().run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
