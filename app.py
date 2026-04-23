from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os, secrets, string, json, stripe, smtplib, random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vivah-royal-2026-xK9m')

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'sqlite:///vivah.db')
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'images', 'products')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

app.config['STRIPE_PUBLIC_KEY'] = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_test_51TKf9O3823lz1qaCjtpVDVPzVFjAsv22vYPdekXyovYvB5ulh3U11Ds9YOtctrFIaMa6wr5C0Ykejn3heIu2MMq000O3D7m806')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_51TKf9O3823lz1qaCmV55JbvzC8DFVfzrmIdLYeW9TpPakolvh9T5nRZHjMyV386CiHkgeIeba8hsw2a6Njc3a7Ko00cspAiTco')
stripe.api_key = app.config['STRIPE_SECRET_KEY']
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ─── Email Config for OTP ─────────────────────────────────────────────────────
MAIL_SENDER_EMAIL = os.environ.get('MAIL_SENDER_EMAIL', 'panerinandha2324@gmail.com')  # Replace with your Gmail
MAIL_SENDER_PASSWORD = os.environ.get('MAIL_SENDER_PASSWORD', 'uzpd wbak uwdg yiha')  # Use Gmail App Password

def send_otp_email(to_email, otp_code):
    """Send OTP to user's email using Gmail SMTP."""
    msg = MIMEMultipart('alternative')
    msg['From'] = MAIL_SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = 'Vivah Sarees – Password Reset OTP'
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:30px;background:#faf8f5;border:1px solid #e8e0d5;">
        <div style="text-align:center;padding:20px 0;border-bottom:2px solid #c9a84c;">
            <h1 style="color:#8B1A1A;font-size:28px;letter-spacing:5px;margin:0;">VIVAH</h1>
            <p style="color:#999;font-size:12px;margin-top:4px;">Luxury Saree House</p>
        </div>
        <div style="padding:30px 0;text-align:center;">
            <p style="color:#333;font-size:15px;margin-bottom:20px;">Your One-Time Password for resetting your account password is:</p>
            <div style="background:#8B1A1A;color:white;font-size:32px;letter-spacing:12px;padding:18px 30px;display:inline-block;font-weight:700;border-radius:4px;">{otp_code}</div>
            <p style="color:#999;font-size:13px;margin-top:20px;">This OTP is valid for <strong>10 minutes</strong>. Do not share it with anyone.</p>
        </div>
        <div style="text-align:center;padding-top:16px;border-top:1px solid #e8e0d5;font-size:11px;color:#bbb;">
            If you didn't request this, please ignore this email.
        </div>
    </div>
    """
    msg.attach(MIMEText(html, 'html'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MAIL_SENDER_EMAIL, MAIL_SENDER_PASSWORD)
        server.sendmail(MAIL_SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f'[EMAIL ERROR] {e}')
        return False

def send_status_email(to_email, subject, title, message):
    """Send generic status update email to user."""
    msg = MIMEMultipart('alternative')
    msg['From'] = MAIL_SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:30px;background:#faf8f5;border:1px solid #e8e0d5;">
        <div style="text-align:center;padding:20px 0;border-bottom:2px solid #c9a84c;">
            <h1 style="color:#8B1A1A;font-size:28px;letter-spacing:5px;margin:0;">VIVAH</h1>
            <p style="color:#999;font-size:12px;margin-top:4px;">Luxury Saree House</p>
        </div>
        <div style="padding:30px 0;text-align:center;">
            <h2 style="color:#333;font-size:20px;margin-bottom:20px;font-weight:600;">{title}</h2>
            <div style="color:#555;font-size:14px;line-height:1.6;">
                {message}
            </div>
        </div>
        <div style="text-align:center;padding-top:16px;border-top:1px solid #e8e0d5;font-size:11px;color:#bbb;">
            Thank you for shopping with Vivah Sarees.
        </div>
    </div>
    """
    msg.attach(MIMEText(html, 'html'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MAIL_SENDER_EMAIL, MAIL_SENDER_PASSWORD)
        server.sendmail(MAIL_SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f'[EMAIL ERROR] {e}')
        return False

db = SQLAlchemy(app)

ADMIN_USERNAME = "vivah_admin"
ADMIN_PASSWORD = "Vivah@2026"

# ─── Helpers ──────────────────────────────────────────────────────────────────
def allowed_file(f): return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None
def is_admin(): return session.get('is_admin', False)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin():
            flash('Please log in as admin.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def gen_order_number(): return 'VIV' + ''.join(secrets.choice(string.digits) for _ in range(8))

app.jinja_env.globals['enumerate'] = enumerate

@app.template_filter('from_json')
def from_json_filter(s):
    try: return json.loads(s)
    except: return []

@app.context_processor
def inject_globals():
    user = current_user()
    cart_count = len(session.get('cart', []))
    wishlist_count = len(session.get('wishlist', []))
    return {'current_user': user, 'cart_count': cart_count,
            'wishlist_count': wishlist_count, 'is_admin': is_admin()}

# ─── Models ───────────────────────────────────────────────────────────────────
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(256), nullable=False)
    reset_token = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)
    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(300))
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)
    image = db.Column(db.String(300))
    fabric = db.Column(db.String(100))
    color = db.Column(db.String(100))
    occasion = db.Column(db.String(100))
    is_wedding = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    is_new_arrival = db.Column(db.Boolean, default=False)
    is_vault_exclusive = db.Column(db.Boolean, default=False)
    stock = db.Column(db.Integer, default=1)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProductColor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    color_name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(300), nullable=False)
    product = db.relationship('Product', backref=db.backref('product_colors', lazy=True, cascade="all, delete-orphan"))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total = db.Column(db.Float, nullable=False)
    discount_amount = db.Column(db.Float, default=0)
    coupon_code = db.Column(db.String(50))
    status = db.Column(db.String(50), default='Confirmed')
    address = db.Column(db.Text)
    payment_method = db.Column(db.String(50), default='COD')
    items_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustomOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    fabric = db.Column(db.String(100))
    color = db.Column(db.String(100))
    embroidery = db.Column(db.String(100))
    border_style = db.Column(db.String(100))
    blouse_design = db.Column(db.String(100))
    occasion = db.Column(db.String(100))
    special_notes = db.Column(db.Text)
    budget = db.Column(db.String(100))
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NewsletterSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_type = db.Column(db.String(20), default='percent')  # percent or flat
    discount_value = db.Column(db.Float, nullable=False)
    min_order = db.Column(db.Float, default=0)
    max_uses = db.Column(db.Integer, default=100)
    uses = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ReplacementRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='Pending')  # Pending, Approved, Rejected, Completed
    admin_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship('Order', backref='replacement_requests')
    user = db.relationship('User', backref='replacement_requests')

# ─── ADMIN AUTH ───────────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if is_admin(): return redirect(url_for('admin'))
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('admin'))
        flash('Invalid credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))

# ─── ADMIN ────────────────────────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = Category.query.all()
    custom_orders = CustomOrder.query.order_by(CustomOrder.created_at.desc()).all()
    contacts = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    users = User.query.order_by(User.created_at.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    coupons = Coupon.query.order_by(Coupon.created_at.desc()).all()
    replacement_requests = ReplacementRequest.query.order_by(ReplacementRequest.created_at.desc()).all()
    return render_template('admin.html', products=products, categories=categories,
        custom_orders=custom_orders, contacts=contacts, users=users,
        orders=orders, coupons=coupons, replacement_requests=replacement_requests)

@app.route('/admin/product/add', methods=['POST'])
@admin_required
def admin_add_product():
    image_filename = ''
    if 'image_file' in request.files:
        file = request.files['image_file']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            name_part, ext = os.path.splitext(filename)
            filename = f"{name_part}_{secrets.token_hex(6)}{ext}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename
    if not image_filename:
        image_filename = request.form.get('image', '').strip()
    try:
        price = float(request.form.get('price', 0))
        orig = request.form.get('original_price', '').strip()
        original_price = float(orig) if orig else None
        stock = int(request.form.get('stock', 1))
        cat_id = request.form.get('category_id', '')
        category_id = int(cat_id) if cat_id else None
    except (ValueError, TypeError):
        flash('Invalid price or stock.', 'error')
        return redirect(url_for('admin'))
    p = Product(name=request.form.get('name','').strip(),
        description=request.form.get('description','').strip(),
        price=price, original_price=original_price, image=image_filename,
        fabric=request.form.get('fabric',''), color=request.form.get('color',''),
        occasion=', '.join(request.form.getlist('occasion_multi')) or request.form.get('occasion',''),
        is_wedding=bool(request.form.get('is_wedding')),
        is_featured=bool(request.form.get('is_featured')),
        is_new_arrival=bool(request.form.get('is_new_arrival')),
        is_vault_exclusive=bool(request.form.get('is_vault_exclusive')),
        stock=stock, category_id=category_id)
    db.session.add(p); db.session.commit()
    flash(f'Product "{p.name}" added!', 'success')
    return redirect(url_for('admin') + '#tab-products')

@app.route('/admin/product/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_product(id):
    p = Product.query.get_or_404(id)
    name = p.name; db.session.delete(p); db.session.commit()
    flash(f'"{name}" deleted.', 'info')
    return redirect(url_for('admin') + '#tab-products')

@app.route('/admin/product/<int:id>/colors', methods=['GET', 'POST'])
@admin_required
def admin_product_colors(id):
    p = Product.query.get_or_404(id)
    if request.method == 'POST':
        image_filename = ''
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                name_part, ext = os.path.splitext(filename)
                filename = f"{name_part}_{secrets.token_hex(6)}{ext}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
        if not image_filename:
            image_filename = request.form.get('image', '').strip()
            
        color_name = request.form.get('color_name', '').strip()
        if not color_name or not image_filename:
            flash('Color name and image are required.', 'error')
        else:
            pc = ProductColor(product_id=p.id, color_name=color_name, image=image_filename)
            db.session.add(pc)
            db.session.commit()
            flash(f'Color "{color_name}" added!', 'success')
        return redirect(url_for('admin_product_colors', id=p.id))
        
    return render_template('admin_product_colors.html', product=p)

@app.route('/admin/product/color/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_product_color(id):
    pc = ProductColor.query.get_or_404(id)
    product_id = pc.product_id
    color_name = pc.color_name
    db.session.delete(pc)
    db.session.commit()
    flash(f'Color "{color_name}" deleted.', 'info')
    return redirect(url_for('admin_product_colors', id=product_id))

@app.route('/admin/order/update-status', methods=['POST'])
@admin_required
def admin_update_order_status():
    order = Order.query.get_or_404(request.form.get('order_id'))
    old_status = order.status
    new_status = request.form.get('status')
    order.status = new_status
    order.updated_at = datetime.utcnow(); db.session.commit()
    
    if old_status != new_status and order.user:
        subject = f"Order Status Update - #{order.order_number}"
        title = "Your Order Status Has Been Updated"
        message = f"""
            <p>Your order <strong>#{order.order_number}</strong> is now marked as: <strong style="color:#8B1A1A;">{new_status}</strong>.</p>
            <p style="margin-top:20px;">You can track your order anytime by visiting your <a href="http://127.0.0.1:5000/profile" style="color:#C9A84C;text-decoration:none;">profile page</a>.</p>
        """
        send_status_email(order.user.email, subject, title, message)

    flash(f'Order {order.order_number} → {order.status}', 'success')
    return redirect(url_for('admin') + '#tab-orders')

@app.route('/admin/custom-order/update', methods=['POST'])
@admin_required
def admin_update_custom_order():
    order = CustomOrder.query.get_or_404(request.form.get('order_id'))
    old_status = order.status
    new_status = request.form.get('status')
    order.status = new_status; db.session.commit()
    
    if old_status != new_status and order.email:
        subject = f"Custom Order Update - Vivah Sarees"
        title = "Your Custom Saree Request"
        message = f"""
            <p>The status of your custom saree request has been updated to: <strong style="color:#8B1A1A;">{new_status.replace('-', ' ').title()}</strong>.</p>
            <p style="margin-top:20px;">Our artisans are paying close attention to your details. We will reach out to you if we need any more information.</p>
        """
        send_status_email(order.email, subject, title, message)

    flash(f'Custom order #{order.id} updated.', 'success')
    return redirect(url_for('admin') + '#tab-custom')

@app.route('/admin/category/add', methods=['POST'])
@admin_required
def admin_add_category():
    name = request.form.get('name','').strip()
    slug = name.lower().replace(' ', '-').replace("'", '')
    if Category.query.filter_by(slug=slug).first():
        flash('Category already exists.', 'error')
        return redirect(url_for('admin') + '#tab-categories')
    db.session.add(Category(name=name, slug=slug, description=request.form.get('description','')))
    db.session.commit(); flash(f'Category "{name}" added!', 'success')
    return redirect(url_for('admin') + '#tab-categories')

@app.route('/admin/coupon/add', methods=['POST'])
@admin_required
def admin_add_coupon():
    code = request.form.get('code','').strip().upper()
    if Coupon.query.filter_by(code=code).first():
        flash('Coupon code already exists.', 'error')
        return redirect(url_for('admin') + '#tab-coupons')
    try:
        c = Coupon(
            code=code,
            discount_type=request.form.get('discount_type','percent'),
            discount_value=float(request.form.get('discount_value',0)),
            min_order=float(request.form.get('min_order',0)),
            max_uses=int(request.form.get('max_uses',100)),
        )
        db.session.add(c); db.session.commit()
        flash(f'Coupon "{code}" created!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')
    return redirect(url_for('admin') + '#tab-coupons')

@app.route('/admin/coupon/toggle/<int:id>', methods=['POST'])
@admin_required
def admin_toggle_coupon(id):
    c = Coupon.query.get_or_404(id)
    c.is_active = not c.is_active; db.session.commit()
    flash(f'Coupon "{c.code}" {"activated" if c.is_active else "deactivated"}.', 'success')
    return redirect(url_for('admin') + '#tab-coupons')

@app.route('/admin/coupon/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_coupon(id):
    c = Coupon.query.get_or_404(id)
    code = c.code; db.session.delete(c); db.session.commit()
    flash(f'Coupon "{code}" deleted.', 'info')
    return redirect(url_for('admin') + '#tab-coupons')

# ─── REPLACEMENT REQUESTS ────────────────────────────────────────────────────
@app.route('/order/<order_number>/request-replacement', methods=['GET', 'POST'])
def request_replacement(order_number):
    user = current_user()
    if not user: return redirect(url_for('login'))
    order = Order.query.filter_by(order_number=order_number, user_id=user.id).first_or_404()
    if order.status != 'Delivered':
        flash('Replacement can only be requested for delivered orders.', 'error')
        return redirect(url_for('order_detail', order_number=order_number))
    existing = ReplacementRequest.query.filter_by(order_id=order.id, user_id=user.id).filter(
        ReplacementRequest.status.in_(['Pending', 'Approved'])).first()
    if existing:
        flash('A replacement request already exists for this order.', 'info')
        return redirect(url_for('order_detail', order_number=order_number))
    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()
        description = request.form.get('description', '').strip()
        if not reason:
            flash('Please select a reason.', 'error')
            return redirect(url_for('request_replacement', order_number=order_number))
        rr = ReplacementRequest(order_id=order.id, user_id=user.id, reason=reason, description=description)
        db.session.add(rr); db.session.commit()
        flash('Replacement request submitted successfully! We will review it shortly.', 'success')
        return redirect(url_for('order_detail', order_number=order_number))
    return render_template('replacement_request.html', order=order)

@app.route('/admin/replacement/update', methods=['POST'])
@admin_required
def admin_update_replacement():
    rr = ReplacementRequest.query.get_or_404(request.form.get('replacement_id'))
    old_status = rr.status
    new_status = request.form.get('status', rr.status)
    rr.status = new_status
    rr.admin_note = request.form.get('admin_note', '')
    rr.updated_at = datetime.utcnow()
    db.session.commit()

    if old_status != new_status and rr.user:
        subject = f"Replacement Request Update - Order #{rr.order.order_number}"
        title = "Replacement Request Status"
        note_html = f'<p style="margin-top:15px;padding:10px;background:#fff;border:1px solid #e8e0d5;font-size:13px;"><strong>Note from Vivah:</strong> {rr.admin_note}</p>' if rr.admin_note else ''
        message = f"""
            <p>Your replacement request for order <strong>#{rr.order.order_number}</strong> has been marked as: <strong style="color:#8B1A1A;">{new_status}</strong>.</p>
            {note_html}
        """
        send_status_email(rr.user.email, subject, title, message)

    flash(f'Replacement #{rr.id} updated to {rr.status}.', 'success')
    return redirect(url_for('admin') + '#tab-replacements')


# ─── COUPON API ───────────────────────────────────────────────────────────────
@app.route('/coupon/apply', methods=['POST'])
def apply_coupon():
    code = request.json.get('code','').strip().upper()
    total = float(request.json.get('total', 0))
    c = Coupon.query.filter_by(code=code, is_active=True).first()
    if not c:
        return jsonify({'success': False, 'message': 'Invalid or expired coupon code.'})
    if c.max_uses and c.uses >= c.max_uses:
        return jsonify({'success': False, 'message': 'This coupon has reached its usage limit.'})
    if total < c.min_order:
        return jsonify({'success': False, 'message': f'Minimum order ₹{c.min_order:.0f} required for this coupon.'})
    if c.discount_type == 'percent':
        discount = round(total * c.discount_value / 100, 2)
        label = f'{c.discount_value:.0f}% OFF'
    else:
        discount = min(c.discount_value, total)
        label = f'Flat ₹{c.discount_value:.0f} OFF'
    session['applied_coupon'] = {'code': code, 'discount': discount, 'label': label}
    return jsonify({'success': True, 'discount': discount, 'label': label,
                    'message': f'Coupon applied! You save ₹{discount:.0f}'})

@app.route('/coupon/remove', methods=['POST'])
def remove_coupon():
    session.pop('applied_coupon', None)
    return jsonify({'success': True})

# ─── USER AUTH ────────────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name=request.form.get('name','').strip()
        email=request.form.get('email','').strip().lower()
        pw=request.form.get('password','')
        pw2=request.form.get('password2','')
        if not name or not email or not pw:
            flash('Fill in all required fields.', 'error'); return redirect(url_for('register'))
        if pw != pw2:
            flash('Passwords do not match.', 'error'); return redirect(url_for('register'))
        if len(pw) < 6:
            flash('Password must be 6+ characters.', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error'); return redirect(url_for('register'))
        user = User(name=name, email=email, phone=request.form.get('phone',''))
        user.set_password(pw); db.session.add(user); db.session.commit()
        session['user_id'] = user.id
        flash(f'Welcome to Vivah, {name}!', 'success')
        return redirect(request.form.get('next') or url_for('index'))
    return render_template('register.html', next=request.args.get('next',''))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
        if user and user.check_password(request.form.get('password','')):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(request.form.get('next') or url_for('index'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', next=request.args.get('next',''))

@app.route('/logout')
def logout():
    session.pop('user_id', None); flash('Logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            otp = ''.join([str(random.randint(0,9)) for _ in range(6)])
            session['reset_otp'] = otp
            session['reset_email'] = email
            import time; session['reset_otp_time'] = time.time()
            if send_otp_email(email, otp):
                flash('OTP sent to your email! Check your inbox.', 'success')
                return redirect(url_for('verify_otp'))
            else:
                flash('Failed to send OTP. Please try again.', 'error')
        else:
            flash('No account found with that email.', 'error')
        return redirect(url_for('forgot_password'))
    return render_template('forgot_password.html')

@app.route('/verify-otp', methods=['GET','POST'])
def verify_otp():
    if 'reset_email' not in session:
        flash('Please enter your email first.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        entered_otp = request.form.get('otp','').strip()
        import time
        elapsed = time.time() - session.get('reset_otp_time', 0)
        if elapsed > 600:  # 10 minutes
            session.pop('reset_otp', None); session.pop('reset_email', None); session.pop('reset_otp_time', None)
            flash('OTP expired. Please request a new one.', 'error')
            return redirect(url_for('forgot_password'))
        if entered_otp == session.get('reset_otp'):
            session['otp_verified'] = True
            return redirect(url_for('reset_password_otp'))
        else:
            flash('Invalid OTP. Please try again.', 'error')
    return render_template('verify_otp.html', email=session.get('reset_email',''))

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = session.get('reset_email')
    if not email:
        flash('Please enter your email first.', 'error')
        return redirect(url_for('forgot_password'))
    otp = ''.join([str(random.randint(0,9)) for _ in range(6)])
    session['reset_otp'] = otp
    import time; session['reset_otp_time'] = time.time()
    if send_otp_email(email, otp):
        flash('New OTP sent to your email!', 'success')
    else:
        flash('Failed to send OTP. Please try again.', 'error')
    return redirect(url_for('verify_otp'))

@app.route('/reset-password', methods=['GET','POST'])
def reset_password_otp():
    if not session.get('otp_verified'):
        flash('Please verify OTP first.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        pw = request.form.get('password','')
        if len(pw) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('reset_password_otp'))
        if pw != request.form.get('password2',''):
            flash('Passwords do not match.', 'error')
            return redirect(url_for('reset_password_otp'))
        user = User.query.filter_by(email=session.get('reset_email')).first()
        if user:
            user.set_password(pw); db.session.commit()
            # Clean up session
            session.pop('reset_otp', None); session.pop('reset_email', None)
            session.pop('reset_otp_time', None); session.pop('otp_verified', None)
            flash('Password reset successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        flash('Something went wrong.', 'error')
        return redirect(url_for('forgot_password'))
    return render_template('reset_password.html')

@app.route('/profile')
def profile():
    user = current_user()
    if not user: return redirect(url_for('login', next=url_for('profile')))
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    # Load wishlist products
    wl_ids = session.get('wishlist', [])
    wishlist_products = Product.query.filter(Product.id.in_(wl_ids)).all() if wl_ids else []
    return render_template('profile.html', user=user, orders=orders, wishlist_products=wishlist_products)

@app.route('/profile/change-password', methods=['POST'])
def change_password():
    user = current_user()
    if not user: return redirect(url_for('login'))
    if not user.check_password(request.form.get('old_password','')): flash('Current password incorrect.', 'error')
    elif request.form.get('new_password') != request.form.get('new_password2'): flash('Passwords do not match.', 'error')
    else: user.set_password(request.form.get('new_password')); db.session.commit(); flash('Password changed!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/update', methods=['POST'])
def update_profile():
    user = current_user()
    if not user: return redirect(url_for('login'))
    user.name = request.form.get('name', user.name); user.phone = request.form.get('phone', user.phone)
    db.session.commit(); flash('Profile updated!', 'success')
    return redirect(url_for('profile'))

# ─── WISHLIST ─────────────────────────────────────────────────────────────────
@app.route('/wishlist/toggle/<int:id>', methods=['POST'])
def toggle_wishlist(id):
    wl = session.get('wishlist', [])
    if id in wl:
        wl.remove(id); msg = 'Removed from wishlist'; in_wl = False
    else:
        wl.append(id); msg = 'Added to wishlist!'; in_wl = True
    session['wishlist'] = wl
    return jsonify({'success': True, 'message': msg, 'in_wishlist': in_wl, 'count': len(wl)})

@app.route('/wishlist')
def wishlist():
    wl_ids = session.get('wishlist', [])
    products = Product.query.filter(Product.id.in_(wl_ids)).all() if wl_ids else []
    return render_template('wishlist.html', products=products)

# ─── MAIN ROUTES ──────────────────────────────────────────────────────────────
@app.route('/')
def index():
    featured = Product.query.filter_by(is_featured=True).limit(8).all()
    new_arrivals_list = Product.query.filter_by(is_new_arrival=True).limit(8).all()
    wedding = Product.query.filter_by(is_wedding=True).limit(6).all()
    categories = Category.query.all()
    active_coupons = Coupon.query.filter_by(is_active=True).all()
    return render_template('index.html', featured=featured, new_arrivals=new_arrivals_list,
                           wedding=wedding, categories=categories, active_coupons=active_coupons)

@app.route('/collections')
def collections():
    categories = Category.query.all()
    return render_template('collections.html', categories=categories)

@app.route('/collection/<slug>')
def collection_detail(slug):
    category = Category.query.filter_by(slug=slug).first_or_404()
    # Filters
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    color = request.args.get('color', '')
    fabric = request.args.get('fabric', '')
    occasion = request.args.get('occasion', '')
    sort = request.args.get('sort', 'newest')
    q = Product.query.filter_by(category_id=category.id)
    if min_price: q = q.filter(Product.price >= min_price)
    if max_price: q = q.filter(Product.price <= max_price)
    if color: q = q.filter(Product.color.ilike(f'%{color}%'))
    if fabric: q = q.filter(Product.fabric.ilike(f'%{fabric}%'))
    if occasion: q = q.filter(Product.occasion.ilike(f'%{occasion}%'))
    if sort == 'price_asc': q = q.order_by(Product.price.asc())
    elif sort == 'price_desc': q = q.order_by(Product.price.desc())
    elif sort == 'name': q = q.order_by(Product.name.asc())
    else: q = q.order_by(Product.created_at.desc())
    products = q.all()
    wishlist = session.get('wishlist', [])
    return render_template('collection_detail.html', category=category, products=products,
                           wishlist=wishlist, filters={'min_price': min_price, 'max_price': max_price,
                           'color': color, 'fabric': fabric, 'occasion': occasion, 'sort': sort})

@app.route('/wedding-collection')
def wedding_collection():
    products = Product.query.filter_by(is_wedding=True).all()
    wishlist = session.get('wishlist', [])
    all_products_qs = Product.query.filter(Product.stock > 0).all()
    all_products_json = [{'id': p.id, 'name': p.name, 'price': p.price,
                          'color': p.color or '', 'fabric': p.fabric or '',
                          'occasion': p.occasion or '',
                          'category_name': p.category.name if p.category else '',
                          'image': p.image or ''} for p in all_products_qs]
    return render_template('wedding_collection.html', products=products,
                           wishlist=wishlist, all_products_json=all_products_json)

@app.route('/new-arrivals')
def new_arrivals():
    products = Product.query.filter_by(is_new_arrival=True).all()
    wishlist = session.get('wishlist', [])
    return render_template('new_arrivals.html', products=products, wishlist=wishlist)

@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    related = Product.query.filter_by(category_id=product.category_id).filter(Product.id != id).limit(4).all()
    wishlist = session.get('wishlist', [])
    in_wishlist = id in wishlist
    return render_template('product_detail.html', product=product, related=related,
                           in_wishlist=in_wishlist, wishlist=wishlist)

@app.route('/all-products')
def all_products():
    # Advanced filter page
    categories = Category.query.all()
    q = Product.query
    cat_slug = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    color = request.args.get('color', '')
    fabric = request.args.get('fabric', '')
    occasion = request.args.get('occasion', '')
    sort = request.args.get('sort', 'newest')
    if cat_slug:
        cat = Category.query.filter_by(slug=cat_slug).first()
        if cat: q = q.filter_by(category_id=cat.id)
    if min_price: q = q.filter(Product.price >= min_price)
    if max_price: q = q.filter(Product.price <= max_price)
    if color: q = q.filter(Product.color.ilike(f'%{color}%'))
    if fabric: q = q.filter(Product.fabric.ilike(f'%{fabric}%'))
    if occasion: q = q.filter(Product.occasion.ilike(f'%{occasion}%'))
    if sort == 'price_asc': q = q.order_by(Product.price.asc())
    elif sort == 'price_desc': q = q.order_by(Product.price.desc())
    elif sort == 'name': q = q.order_by(Product.name.asc())
    else: q = q.order_by(Product.created_at.desc())
    products = q.all()
    wishlist = session.get('wishlist', [])
    fabrics = [r[0] for r in db.session.query(Product.fabric).distinct() if r[0]]
    colors = [r[0] for r in db.session.query(Product.color).distinct() if r[0]]
    occasions = [r[0] for r in db.session.query(Product.occasion).distinct() if r[0]]
    # Serialize all products for JS recommendation engine (fetch all, not just filtered)
    all_products_qs = Product.query.filter(Product.stock > 0).all()
    products_json = [{'id': p.id, 'name': p.name, 'price': p.price,
                      'color': p.color or '', 'fabric': p.fabric or '',
                      'occasion': p.occasion or '',
                      'category_name': p.category.name if p.category else '',
                      'image': p.image or ''} for p in all_products_qs]
    return render_template('all_products.html', products=products, categories=categories,
                           wishlist=wishlist, fabrics=fabrics, colors=colors, occasions=occasions,
                           products_json=products_json,
                           filters={'category': cat_slug, 'min_price': min_price or '',
                           'max_price': max_price or '', 'color': color, 'fabric': fabric,
                           'occasion': occasion, 'sort': sort})

@app.route('/contact', methods=['GET','POST'])
def contact():
    if request.method == 'POST':
        db.session.add(ContactMessage(name=request.form.get('name'), email=request.form.get('email'),
            phone=request.form.get('phone'), message=request.form.get('message')))
        db.session.commit(); flash('Message sent!', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/about')
def about(): return render_template('about.html')

@app.route('/customize', methods=['GET', 'POST'])
def customize():
    if request.method == 'POST':
        order = CustomOrder(
            name=request.form.get('name', '').strip(),
            email=request.form.get('email', '').strip().lower(),
            phone=request.form.get('phone', '').strip(),
            fabric=request.form.get('fabric', ''),
            color=request.form.get('color', ''),
            embroidery=request.form.get('embroidery', ''),
            border_style=request.form.get('border_style', ''),
            blouse_design=request.form.get('blouse_design', ''),
            occasion=request.form.get('occasion', ''),
            special_notes=request.form.get('special_notes', ''),
            budget=request.form.get('budget', ''),
        )
        db.session.add(order)
        db.session.commit()
        flash('Your custom saree request has been submitted! We will contact you within 24 hours.', 'success')
        return redirect(url_for('customize'))
    return render_template('customize.html')

@app.route('/newsletter', methods=['POST'])
def newsletter():
    email = request.form.get('email','')
    if email:
        if not NewsletterSubscriber.query.filter_by(email=email).first():
            db.session.add(NewsletterSubscriber(email=email)); db.session.commit()
            return jsonify({'success': True, 'message': 'Thank you for subscribing!'})
        return jsonify({'success': False, 'message': 'Already subscribed.'})
    return jsonify({'success': False, 'message': 'Enter a valid email.'})

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    products = []
    categories = Category.query.all()
    wishlist = session.get('wishlist', [])
    if q:
        products = Product.query.filter(db.or_(
            Product.name.ilike(f'%{q}%'), Product.description.ilike(f'%{q}%'),
            Product.fabric.ilike(f'%{q}%'), Product.color.ilike(f'%{q}%'))).all()
        seen = {p.id for p in products}
        for cat in Category.query.filter(Category.name.ilike(f'%{q}%')).all():
            for p in Product.query.filter_by(category_id=cat.id).all():
                if p.id not in seen: products.append(p); seen.add(p.id)
    return render_template('search.html', products=products, query=q, categories=categories, wishlist=wishlist)

# ─── CART ─────────────────────────────────────────────────────────────────────
@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    cart_products, subtotal = [], 0
    for item in cart_items:
        p = Product.query.get(item['id'])
        if p: cart_products.append({'product': p, 'qty': item['qty'], 'color': item.get('color')}); subtotal += p.price * item['qty']
    coupon = session.get('applied_coupon', {})
    discount = coupon.get('discount', 0)
    total = subtotal - discount
    return render_template('cart.html', cart_products=cart_products, subtotal=subtotal,
                           discount=discount, total=total, coupon=coupon)

@app.route('/cart/add/<int:id>', methods=['POST'])
def add_to_cart(id):
    color = request.args.get('color')
    cart = session.get('cart', [])
    for item in cart:
        if item['id'] == id and item.get('color') == color: 
            item['qty'] += 1
            session['cart'] = cart
            return jsonify({'success': True, 'message': 'Added to cart!'})
    cart.append({'id': id, 'qty': 1, 'color': color})
    session['cart'] = cart
    return jsonify({'success': True, 'message': 'Added to cart!'})

@app.route('/cart/remove/<int:id>', methods=['POST'])
def remove_from_cart(id):
    color = request.args.get('color')
    new_cart = []
    removed = False
    for i in session.get('cart', []):
        if not removed and i['id'] == id and i.get('color') == color:
            removed = True
            continue
        new_cart.append(i)
    session['cart'] = new_cart
    return jsonify({'success': True}) if request.is_json else redirect(url_for('cart'))

# ─── CHECKOUT ─────────────────────────────────────────────────────────────────
@app.route('/checkout', methods=['GET','POST'])
def checkout():
    user = current_user()
    if not user: flash('Please log in.', 'info'); return redirect(url_for('login', next=url_for('checkout')))
    cart_items = session.get('cart', [])
    if not cart_items: flash('Cart is empty.', 'error'); return redirect(url_for('cart'))
    cart_products, subtotal = [], 0
    for item in cart_items:
        p = Product.query.get(item['id'])
        if p: cart_products.append({'product': p, 'qty': item['qty'], 'color': item.get('color')}); subtotal += p.price * item['qty']
    coupon = session.get('applied_coupon', {})
    discount = coupon.get('discount', 0)
    total = subtotal - discount
    if request.method == 'POST':
        # Validate coupon again
        coupon_code = coupon.get('code','')
        if coupon_code:
            c = Coupon.query.filter_by(code=coupon_code, is_active=True).first()
            if c: c.uses += 1; db.session.commit()
        shipping = 0 if total >= 2999 else 199
        final_total = total + shipping
        items_data = [{'name': i['product'].name, 'price': i['product'].price, 'qty': i['qty'], 'color': i.get('color')} for i in cart_products]
        payment_method = request.form.get('payment_method', 'COD')
        status = 'Pending' if payment_method == 'Stripe' else 'Confirmed'
        order = Order(order_number=gen_order_number(), user_id=user.id, total=final_total,
            discount_amount=discount, coupon_code=coupon_code, status=status,
            address=f"{request.form.get('address')}, {request.form.get('city')}, {request.form.get('state')} - {request.form.get('pincode')}",
            payment_method=payment_method, items_json=json.dumps(items_data))
        db.session.add(order); db.session.commit()
        
        if payment_method == 'Stripe':
            try:
                line_items = [{
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {
                            'name': f"Vivah Order #{order.order_number}",
                            'description': "Payment for your Vivah order",
                        },
                        'unit_amount': int(final_total * 100),
                    },
                    'quantity': 1,
                }]
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=line_items,
                    mode='payment',
                    success_url=url_for('payment_success', order_number=order.order_number, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=url_for('payment_cancel', order_number=order.order_number, _external=True),
                )
                return redirect(checkout_session.url, code=303)
            except Exception as e:
                flash(f"Error creating Stripe session: {str(e)}", "error")
                return redirect(url_for('checkout'))
        
        session['cart'] = []; session.pop('applied_coupon', None)
        return redirect(url_for('order_confirmation', order_number=order.order_number))
    return render_template('checkout.html', user=user, cart_products=cart_products,
                           subtotal=subtotal, discount=discount, total=total, coupon=coupon)

@app.route('/payment/success/<order_number>')
def payment_success(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    session_id = request.args.get('session_id')
    if session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            if checkout_session.payment_status == 'paid':
                order.status = 'Confirmed'
                db.session.commit()
                session['cart'] = []
                session.pop('applied_coupon', None)
                flash('Payment successful! Your order is confirmed.', 'success')
                return redirect(url_for('order_confirmation', order_number=order.order_number))
        except Exception as e:
            flash(f"Error verifying payment: {str(e)}", "error")
    flash('Payment verification failed.', 'error')
    return redirect(url_for('checkout'))

@app.route('/payment/cancel/<order_number>')
def payment_cancel(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    if order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()
    flash('Payment cancelled. Please try again.', 'error')
    return redirect(url_for('checkout'))

@app.route('/order-confirmation/<order_number>')
def order_confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_confirmation.html', order=order, user=current_user())

@app.route('/order/<order_number>')
def order_detail(order_number):
    user = current_user()
    if not user: return redirect(url_for('login', next=url_for('order_detail', order_number=order_number)))
    order = Order.query.filter_by(order_number=order_number, user_id=user.id).first_or_404()
    return render_template('order_detail.html', order=order)

@app.route('/vivah-vault')
def vivah_vault():
    vault_products = Product.query.filter_by(is_vault_exclusive=True).filter(Product.stock > 0).all()
    # Fallback: if no vault products, show featured ones with a note
    if not vault_products:
        vault_products = Product.query.filter_by(is_featured=True).limit(6).all()
    wishlist = session.get('wishlist', [])
    return render_template('vault.html', products=vault_products, wishlist=wishlist)

@app.route('/track-order', methods=['GET','POST'])
def track_order():
    order = None
    num = request.form.get('order_number') or request.args.get('order_number','')
    if num:
        order = Order.query.filter_by(order_number=num.strip()).first()
        if not order: flash('Order not found.', 'error')
    return render_template('track_order.html', order=order)

# ─── INIT DB ──────────────────────────────────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        if Category.query.count() == 0:
            cats = [
                ('Bandhani Sarees','bandhani-sarees','Traditional tie-dye from Gujarat','categories/bandhani_1.jpeg'),
                ('Patola Sarees','patola-sarees','Double-ikat from Patan, Gujarat','categories/patola_1.jpeg'),
                ('Gharchola Sarees','gharchola-sarees','Bridal Gharchola with gold zari','categories/gharchola_1.jpeg'),
                ('Panetar Sarees','panetar-sarees','Traditional white & red for weddings','categories/panetar_1.jpeg'),
                ('Ajrakh Sarees','ajrakh-sarees','Ancient block-print from Kutch','categories/ajarakh_1.jpeg'),
                ('Kanjivaram Sarees','kanjivaram-sarees','Authentic South Indian silk','categories/kanjivaram_2.jpeg'),
                ('Banarasi Sarees','banarasi-sarees','Traditional Banarasi with gold zari','categories/banarasi_1.jpeg'),
                ('Organza Sarees','organza-sarees','Sheer & elegant Organza drapes','categories/organza_1.jpeg'),
                ('Chiffon Sarees','chiffon-sarees','Lightweight flowing Chiffon','categories/chiffon_1.jpeg'),
                ('Net Sarees','net-sarees','Glamorous Net for parties','categories/net_1.jpeg'),
                ('Velvet Sarees','velvet-sarees','Royal plush Velvet sarees','categories/velvet_1.jpeg'),
                ('Bridal Collection','bridal-sarees','Exquisite bridal sarees','categories/bride_1.jpeg'),
                ('Tissue Sarees','tissue-sarees','Shimmering tissue for festivals','categories/tissue_1.jpeg'),
                ('Kalamkari Sarees','kalamkari-sarees','Hand-painted art on silk','categories/kalamkari_1.jpeg'),
                ('Digital Print','digital-print','Modern digital print sarees','categories/digital_1.jpeg'),
                ('Designer Sarees','designer-sarees','Contemporary designer pieces','categories/sangeet_5.jpeg'),
                ('Silk Sarees','silk-sarees','Luxurious pure silk','categories/silk_10.jpeg'),
                ('Leheriya Sarees','leheriya-sarees','Wave-pattern from Rajasthan','categories/leheriya_4.jpeg'),
            ]
            for name, slug, desc, img in cats:
                db.session.add(Category(name=name, slug=slug, description=desc, image=img))
            db.session.commit()
        if Coupon.query.count() == 0:
            sample_coupons = [
                Coupon(code='VIVAH20', discount_type='percent', discount_value=20, min_order=1000, max_uses=500),
                Coupon(code='WELCOME10', discount_type='percent', discount_value=10, min_order=0, max_uses=1000),
                Coupon(code='FLAT500', discount_type='flat', discount_value=500, min_order=3000, max_uses=200),
                Coupon(code='BRIDAL15', discount_type='percent', discount_value=15, min_order=5000, max_uses=100),
            ]
            db.session.bulk_save_objects(sample_coupons); db.session.commit()

# Initialize Database
init_db()

if __name__ == '__main__':
    print("\n" + "="*55)
    print("  VIVAH SAREES — http://127.0.0.1:10000")
    print(f"  Admin: /admin/login  |  {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=True)
