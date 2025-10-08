import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# --- Basic App Setup ---
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# --- Session Configuration ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# --- Environment Variable Loading ---
ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv('ADMIN_PASSWORD'))
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# --- Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "data", "inventory.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Models ---
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    room_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed, deleted
    admin_comment = db.Column(db.Text, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)

# --- Helper Functions ---
def login_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('⚠️ გთხოვთ შეხვიდეთ სისტემაში.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Main Page Route ---
@app.route('/', methods=['GET', 'POST'])
def index():
    form_data = session.get('form_data', {})
    items_from_db = Item.query.order_by(Item.name).all()
    all_items_for_json = [{'id': item.id, 'name': item.name} for item in items_from_db]

    if request.method == 'POST':
        try:
            customer_name = request.form.get('customer_name', '').strip()
            customer_phone = request.form.get('customer_phone', '').strip()
            room_number = request.form.get('room_number', '').strip()

            order_details = {}
            has_items = False
            for item in items_from_db:
                try:
                    qty = int(request.form.get(f'qty_{item.id}', '0'))
                    if qty > 0:
                        order_details[item.name] = qty
                        has_items = True
                except (ValueError, TypeError):
                    continue
            
            if not (customer_name and customer_phone and room_number and has_items):
                flash('⚠️ გთხოვთ შეავსოთ ყველა სავალდებულო ველი და აირჩიოთ მინიმუმ ერთი ნივთი.', 'warning')
                return redirect(url_for('index'))

            new_order = Order(
                customer_name=customer_name, 
                customer_phone=customer_phone, 
                room_number=room_number,
                status='pending'
            )
            for item_name, quantity in order_details.items():
                new_order.order_items.append(OrderItem(item_name=item_name, quantity=quantity))
            
            db.session.add(new_order)
            db.session.commit()

            # Send email notification for new order
            send_new_order_notification(
                customer_name=customer_name,
                customer_phone=customer_phone,
                room_number=room_number,
                order=order_details
            )

            flash(f'✅ შეკვეთა წარმატებით გაიგზავნა, {customer_name}!', 'success')
            session.pop('form_data', None)
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating order: {e}")
            flash('❌ შეკვეთის შექმნისას მოხდა შეცდომა. გთხოვთ სცადოთ თავიდან.', 'error')
            return redirect(url_for('index'))

    return render_template('index.html', items=items_from_db, all_items=all_items_for_json, form_data=form_data)

# --- Admin Authentication Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            session.permanent = True
            flash('✅ წარმატებით შეხვედით სისტემაში!', 'success')
            return redirect(url_for('admin_panel'))
        else:
            flash('❌ არასწორი პაროლი.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('✅ თქვენ გამოხვედით სისტემიდან.', 'success')
    return redirect(url_for('index'))

# --- Admin Panel Main Route ---
@app.route('/admin/', methods=['GET'])
@login_required
def admin_panel():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    items_query = Item.query.order_by(Item.name)
    if search_query:
        items_query = items_query.filter(Item.name.ilike(f'%{search_query}%'))
    
    pagination = items_query.paginate(page=page, per_page=20, error_out=False)
    items_on_page = pagination.items
    
    # Get pending orders count for badge
    pending_count = Order.query.filter_by(status='pending').count()

    return render_template('admin_panel.html', items=items_on_page, pagination=pagination, 
                         search_query=search_query, pending_count=pending_count)

# --- Order Management Routes ---
@app.route('/admin/orders/pending')
@login_required
def admin_orders_pending():
    orders = Order.query.filter_by(status='pending').order_by(Order.timestamp.desc()).all()
    return render_template('admin_orders_pending.html', orders=orders)

@app.route('/admin/orders/confirmed')
@login_required
def admin_orders_confirmed():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    # Date range filters
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')
    
    start_date = None
    end_date = None
    
    try:
        if start_date_param:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
        if end_date_param:
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        flash('⚠️ არასწორი თარიღის ფორმატი.', 'warning')
    
    # Base query
    query = Order.query.filter_by(status='confirmed')
    
    # Apply date range filter
    if start_date:
        query = query.filter(Order.confirmed_at >= start_date)
    if end_date:
        query = query.filter(Order.confirmed_at <= end_date)
    
    # Apply search filter
    if search_query:
        query = query.filter(
            db.or_(
                Order.customer_name.ilike(f'%{search_query}%'),
                Order.customer_phone.ilike(f'%{search_query}%'),
                Order.room_number.ilike(f'%{search_query}%')
            )
        )
    
    # Default sorting by date descending
    query = query.order_by(Order.confirmed_at.desc())
    
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_orders_confirmed.html', 
                         orders=pagination.items, 
                         pagination=pagination, 
                         search_query=search_query,
                         start_date=start_date_param or '',
                         end_date=end_date_param or '')

@app.route('/admin/orders/deleted')
@login_required
def admin_orders_deleted():
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.filter_by(status='deleted')\
                     .order_by(Order.deleted_at.desc())\
                     .paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_orders_deleted.html', orders=pagination.items, pagination=pagination)

@app.route('/admin/reports/weekly')
@login_required
def admin_reports_weekly():
    # Get date range for the report (default: last 7 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    # Allow custom date range
    start_param = request.args.get('start_date')
    end_param = request.args.get('end_date')
    
    try:
        if start_param:
            start_date = datetime.strptime(start_param, '%Y-%m-%d')
        if end_param:
            end_date = datetime.strptime(end_param, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        flash('⚠️ არასწორი თარიღის ფორმატი.', 'warning')
    
    # Get confirmed orders in date range
    orders = Order.query.filter(
        Order.status == 'confirmed',
        Order.confirmed_at >= start_date,
        Order.confirmed_at <= end_date
    ).all()
    
    # Aggregate item quantities
    item_totals = {}
    for order in orders:
        for item in order.order_items:
            if item.item_name in item_totals:
                item_totals[item.item_name] += item.quantity
            else:
                item_totals[item.item_name] = item.quantity
    
    # Sort by quantity
    sorted_items = sorted(item_totals.items(), key=lambda x: x[1], reverse=True)
    
    return render_template('admin_reports_weekly.html', 
                         items=sorted_items, 
                         start_date=start_date, 
                         end_date=end_date,
                         total_orders=len(orders))

# --- Order Management API ---
@app.route('/api/order/confirm/<int:order_id>', methods=['POST'])
@login_required
def api_confirm_order(order_id):
    try:
        data = request.get_json() or {}
        comment = data.get('comment', '').strip()
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'status': 'error', 'message': 'შეკვეთა ვერ მოიძებნა'}), 404
            
        if order.status != 'pending':
            return jsonify({'status': 'error', 'message': 'შეკვეთა უკვე დამუშავებულია'}), 400
        
        order.status = 'confirmed'
        order.confirmed_at = datetime.utcnow()
        order.admin_comment = comment
        db.session.commit()
        
        # NO EMAIL SENT HERE - Email was already sent when order was placed
        
        return jsonify({'status': 'success', 'message': 'შეკვეთა დადასტურდა წარმატებით'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error confirming order: {e}")
        return jsonify({'status': 'error', 'message': 'შეცდომა მოხდა'}), 500

@app.route('/api/order/delete/<int:order_id>', methods=['POST'])
@login_required
def api_delete_order(order_id):
    try:
        data = request.get_json() or {}
        comment = data.get('comment', '').strip()
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'status': 'error', 'message': 'შეკვეთა ვერ მოიძებნა'}), 404
            
        if order.status != 'pending':
            return jsonify({'status': 'error', 'message': 'შეკვეთა უკვე დამუშავებულია'}), 400
        
        order.status = 'deleted'
        order.deleted_at = datetime.utcnow()
        order.admin_comment = comment
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'შეკვეთა წაიშალა'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting order: {e}")
        return jsonify({'status': 'error', 'message': 'შეცდომა მოხდა'}), 500

@app.route('/api/orders/clean-deleted', methods=['POST'])
@login_required
def api_clean_deleted_orders():
    try:
        deleted_orders = Order.query.filter_by(status='deleted').all()
        count = len(deleted_orders)
        for order in deleted_orders:
            db.session.delete(order)
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'წარმატებით წაიშალა {count} შეკვეთა სამუდამოდ'})
    except Exception as e:
        db.session.rollback()
        print(f"Error cleaning deleted orders: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/order/edit/<int:order_id>', methods=['PUT'])
@login_required
def api_edit_confirmed_order(order_id):
    try:
        data = request.get_json() or {}
        order_items = data.get('items', [])
        
        order = Order.query.get(order_id)
        if not order:
            return jsonify({'status': 'error', 'message': 'შეკვეთა ვერ მოიძებნა'}), 404
            
        if order.status != 'confirmed':
            return jsonify({'status': 'error', 'message': 'მხოლოდ დადასტურებული შეკვეთების რედაქტირებაა შესაძლებელი'}), 400
        
        # Delete existing order items
        OrderItem.query.filter_by(order_id=order_id).delete()
        
        # Add new order items
        for item_data in order_items:
            if item_data.get('quantity', 0) > 0:
                new_item = OrderItem(
                    item_name=item_data['name'],
                    quantity=item_data['quantity'],
                    order_id=order_id
                )
                db.session.add(new_item)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'შეკვეთა განახლდა წარმატებით'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error editing order: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- API Routes ---
@app.route('/api/public/items/search')
def api_public_search_items():
    query = request.args.get('q', '').strip()
    
    if not query:
        items = Item.query.order_by(Item.name).all()
    else:
        items = Item.query.filter(Item.name.ilike(f'%{query}%')).order_by(Item.name).all()
    
    results = [{'id': item.id, 'name': item.name} for item in items]
    return jsonify(results)

@app.route('/api/item/add', methods=['POST'])
@login_required
def api_add_item():
    try:
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'status': 'error', 'message': 'ნივთის სახელი არ უნდა იყოს ცარიელი'}), 400
        
        # Check if item already exists
        if Item.query.filter_by(name=name).first():
            return jsonify({'status': 'error', 'message': 'ეს ნივთი უკვე არსებობს'}), 400
        
        new_item = Item(name=name)
        db.session.add(new_item)
        db.session.commit()
        
        return jsonify({'status': 'success', 'item': {'id': new_item.id, 'name': new_item.name}})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error adding item: {e}")
        return jsonify({'status': 'error', 'message': 'შეცდომა მოხდა'}), 500

@app.route('/api/item/bulk_add', methods=['POST'])
@login_required
def api_bulk_add_items():
    try:
        data = request.get_json() or {}
        items_text = data.get('items_text', '').strip()
        
        if not items_text:
            return jsonify({'status': 'error', 'message': 'ნივთები არ არის მითითებული'}), 400
        
        item_names = [name.strip() for name in items_text.splitlines() if name.strip()]
        added_count = 0
        skipped_count = 0
        
        for name in item_names:
            if not Item.query.filter_by(name=name).first():
                db.session.add(Item(name=name))
                added_count += 1
            else:
                skipped_count += 1
        
        db.session.commit()
        
        message = f'წარმატებით დაემატა {added_count} ნივთი.'
        if skipped_count > 0:
            message += f' {skipped_count} ნივთი გამოტოვებულია (უკვე არსებობს).'
        
        return jsonify({'status': 'success', 'message': message})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error bulk adding items: {e}")
        return jsonify({'status': 'error', 'message': 'შეცდომა მოხდა'}), 500

@app.route('/api/item/delete/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_item(item_id):
    try:
        item = Item.query.get(item_id)
        if not item:
            return jsonify({'status': 'error', 'message': 'ნივთი ვერ მოიძებნა'}), 404
        
        db.session.delete(item)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'ნივთი წაიშალა'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting item: {e}")
        return jsonify({'status': 'error', 'message': 'შეცდომა მოხდა'}), 500

@app.route('/api/item/edit/<int:item_id>', methods=['PUT'])
@login_required
def api_edit_item(item_id):
    try:
        data = request.get_json() or {}
        new_name = data.get('name', '').strip()
        
        if not new_name:
            return jsonify({'status': 'error', 'message': 'ნივთის სახელი არ უნდა იყოს ცარიელი'}), 400
        
        item = Item.query.get(item_id)
        if not item:
            return jsonify({'status': 'error', 'message': 'ნივთი ვერ მოიძებნა'}), 404
        
        # Check if new name already exists (excluding current item)
        existing_item = Item.query.filter(Item.name == new_name, Item.id != item_id).first()
        if existing_item:
            return jsonify({'status': 'error', 'message': 'ეს სახელი უკვე გამოიყენება'}), 400
        
        item.name = new_name
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'ნივთი განახლდა'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error editing item: {e}")
        return jsonify({'status': 'error', 'message': 'შეცდომა მოხდა'}), 500

@app.route('/api/items/search')
@login_required
def api_search_items():
    query = request.args.get('q', '')
    items = Item.query.filter(Item.name.ilike(f'%{query}%')).order_by(Item.name).limit(20).all()
    return jsonify([{'id': item.id, 'name': item.name} for item in items])

# --- Session Saving Routes for Main Form ---
@app.route('/save-progress', methods=['POST'])
def save_progress():
    try:
        session['form_data'] = request.get_json()
        session.modified = True
        return jsonify(success=True)
    except Exception as e:
        print(f"Error saving progress: {e}")
        return jsonify(success=False), 500

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.pop('form_data', None)
    return jsonify(success=True)

# --- Email Helper Function ---
def send_new_order_notification(customer_name, customer_phone, room_number, order):
    """Send email notification when a NEW order is placed by customer"""
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("⚠️ Email credentials not set. Skipping email notification.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = f'🔔 ახალი შეკვეთა! {customer_name} (ოთახი {room_number})'
        
        item_rows = "".join(
            f'<tr>'
            f'<td style="padding: 8px; border: 1px solid #ddd;">{item}</td>'
            f'<td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{qty}</td>'
            f'</tr>' 
            for item, qty in order.items()
        )
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
        <div style="background-color: #f8f9fa; padding: 20px;">
            <div style="background-color: white; border-radius: 10px; padding: 30px; max-width: 600px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #f97316; border-bottom: 3px solid #f97316; padding-bottom: 10px; margin-top: 0;">
                    🔔 ახალი შეკვეთა
                </h2>
                <div style="margin: 20px 0; background-color: #fff7ed; padding: 15px; border-radius: 8px;">
                    <p style="margin: 10px 0;"><strong>მომხმარებლის სახელი:</strong> {customer_name}</p>
                    <p style="margin: 10px 0;"><strong>ოთახის ნომერი:</strong> {room_number}</p>
                    <p style="margin: 10px 0;"><strong>ტელეფონი:</strong> {customer_phone}</p>
                    <p style="margin: 10px 0;"><strong>თარიღი:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                </div>
                <h3 style="color: #333; margin-top: 20px;">შეკვეთის ნივთები:</h3>
                <table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin-top: 10px;">
                    <thead>
                        <tr style="background-color: #f2f2f2;">
                            <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">ნივთი</th>
                            <th style="padding: 12px; border: 1px solid #ddd; text-align: center;">რაოდენობა</th>
                        </tr>
                    </thead>
                    <tbody>{item_rows}</tbody>
                </table>
                <div style="margin-top: 20px; padding: 15px; background-color: #e0f2fe; border-radius: 8px;">
                    <p style="margin: 0; color: #0369a1; font-size: 14px;">
                        <strong>⚠️ სტატუსი:</strong> ახალი შეკვეთა - საჭიროებს დადასტურებას ადმინ პანელში
                    </p>
                </div>
            </div>
        </div>
        </body>
        </html>"""
        
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        
        print(f"✅ Email notification sent successfully for order from: {customer_name}")
        return True
        
    except Exception as e:
        print(f"❌ Email notification failed: {e}")
        return False

# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return "Internal Server Error", 500

if __name__ == '__main__':
    with app.app_context():
        # Create data directory if it doesn't exist
        os.makedirs(os.path.join(basedir, 'data'), exist_ok=True)
        # Create all database tables
        db.create_all()
        print("✅ Database initialized successfully")
    
    # Run the app
    app.run(host='0.0.0.0', port=5001, debug=True)