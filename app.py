import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# --- Basic App Setup ---
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

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

# --- Main Page Route ---
@app.route('/', methods=['GET', 'POST'])
def index():
    form_data = session.get('form_data', {})
    items_from_db = Item.query.order_by(Item.name).all()
    all_items_for_json = [{'id': item.id, 'name': item.name} for item in items_from_db]

    if request.method == 'POST':
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
            flash('⚠️ Please fill all required fields and select at least one item.', 'warning')
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

        # Email will be sent when admin confirms the order
        flash(f'✅ Order placed successfully, {customer_name}!', 'success')
        session.pop('form_data', None)
        return redirect(url_for('index'))

    return render_template('index.html', items=items_from_db, all_items=all_items_for_json, form_data=form_data)

# --- Admin Authentication Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('❌ Invalid password.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

# --- Admin Panel Main Route ---
@app.route('/admin/', methods=['GET'])
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    items_query = Item.query.order_by(Item.name)
    if search_query:
        items_query = items_query.filter(Item.name.ilike(f'%{search_query}%'))
    
    pagination = items_query.paginate(page=page, per_page=20, error_out=False)
    items_on_page = pagination.items
    
    # Get pending orders count for badge
    pending_count = Order.query.filter_by(status='pending').count()

    return render_template('admin_panel.html', items=items_on_page, pagination=pagination, search_query=search_query, pending_count=pending_count)

# --- Order Management Routes ---
@app.route('/admin/orders/pending')
def admin_orders_pending():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    orders = Order.query.filter_by(status='pending').order_by(Order.timestamp.desc()).all()
    return render_template('admin_orders_pending.html', orders=orders)

@app.route('/admin/orders/confirmed')
def admin_orders_confirmed():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.filter_by(status='confirmed').order_by(Order.confirmed_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_orders_confirmed.html', orders=pagination.items, pagination=pagination)

@app.route('/admin/orders/deleted')
def admin_orders_deleted():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    page = request.args.get('page', 1, type=int)
    pagination = Order.query.filter_by(status='deleted').order_by(Order.deleted_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin_orders_deleted.html', orders=pagination.items, pagination=pagination)

@app.route('/admin/reports/weekly')
def admin_reports_weekly():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    # Get date range for the report (default: last 7 days)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    # Allow custom date range
    start_param = request.args.get('start_date')
    end_param = request.args.get('end_date')
    
    if start_param:
        start_date = datetime.strptime(start_param, '%Y-%m-%d')
    if end_param:
        end_date = datetime.strptime(end_param, '%Y-%m-%d')
        end_date = end_date.replace(hour=23, minute=59, second=59)
    
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
def api_confirm_order(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    comment = data.get('comment', '').strip() if data else ''
    
    order = Order.query.get(order_id)
    if order and order.status == 'pending':
        order.status = 'confirmed'
        order.confirmed_at = datetime.utcnow()
        order.admin_comment = comment
        db.session.commit()
        
        # Send email after confirmation
        order_details = {item.item_name: item.quantity for item in order.order_items}
        email_sent = send_order_email(order.customer_name, order.customer_phone, order.room_number, order_details)
        
        if email_sent:
            return jsonify({'status': 'success', 'message': 'Order confirmed and email sent'})
        else:
            return jsonify({'status': 'success', 'message': 'Order confirmed but email failed'})
    
    return jsonify({'status': 'error', 'message': 'Order not found or already processed'}), 404

@app.route('/api/order/delete/<int:order_id>', methods=['POST'])
def api_delete_order(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    comment = data.get('comment', '').strip() if data else ''
    
    order = Order.query.get(order_id)
    if order and order.status == 'pending':
        order.status = 'deleted'
        order.deleted_at = datetime.utcnow()
        order.admin_comment = comment
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Order deleted'})
    
    return jsonify({'status': 'error', 'message': 'Order not found or already processed'}), 404

@app.route('/api/orders/clean-deleted', methods=['POST'])
def api_clean_deleted_orders():
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        deleted_orders = Order.query.filter_by(status='deleted').all()
        count = len(deleted_orders)
        for order in deleted_orders:
            db.session.delete(order)
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Successfully deleted {count} orders permanently'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/order/edit/<int:order_id>', methods=['PUT'])
def api_edit_confirmed_order(order_id):
    if not session.get('admin_logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    order_items = data.get('items', [])
    
    order = Order.query.get(order_id)
    if not order or order.status != 'confirmed':
        return jsonify({'status': 'error', 'message': 'Order not found or not confirmed'}), 404
    
    try:
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
        return jsonify({'status': 'success', 'message': 'Order updated successfully'})
    except Exception as e:
        db.session.rollback()
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
def api_add_item():
    if not session.get('admin_logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name: return jsonify({'status': 'error', 'message': 'Item name cannot be empty'}), 400
    new_item = Item(name=name)
    db.session.add(new_item)
    db.session.commit()
    return jsonify({'status': 'success', 'item': {'id': new_item.id, 'name': new_item.name}})

@app.route('/api/item/bulk_add', methods=['POST'])
def api_bulk_add_items():
    if not session.get('admin_logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    data = request.get_json()
    items_text = data.get('items_text', '').strip()
    if not items_text: return jsonify({'status': 'error', 'message': 'No items provided'}), 400
    item_names = [name.strip() for name in items_text.splitlines() if name.strip()]
    added_count = 0
    for name in item_names:
        if not Item.query.filter_by(name=name).first():
            db.session.add(Item(name=name))
            added_count += 1
    db.session.commit()
    return jsonify({'status': 'success', 'message': f'Successfully added {added_count} new items.'})

@app.route('/api/item/delete/<int:item_id>', methods=['DELETE'])
def api_delete_item(item_id):
    if not session.get('admin_logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    item = Item.query.get(item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Item not found'}), 404

@app.route('/api/item/edit/<int:item_id>', methods=['PUT'])
def api_edit_item(item_id):
    if not session.get('admin_logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    data = request.get_json()
    new_name = data.get('name', '').strip()
    item = Item.query.get(item_id)
    if item and new_name:
        item.name = new_name
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Invalid data or item not found'}), 400

@app.route('/api/items/search')
def api_search_items():
    if not session.get('admin_logged_in'): return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    query = request.args.get('q', '')
    items = Item.query.filter(Item.name.ilike(f'%{query}%')).order_by(Item.name).limit(20).all()
    return jsonify([{'id': item.id, 'name': item.name} for item in items])

# --- Session Saving Routes for Main Form ---
@app.route('/save-progress', methods=['POST'])
def save_progress():
    session['form_data'] = request.get_json()
    session.modified = True
    return jsonify(success=True)

@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.pop('form_data', None)
    return jsonify(success=True)

# --- Email Helper Function ---
def send_order_email(customer_name, customer_phone, room_number, order):
    if not all([EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER]):
        print("Email credentials not set. Skipping email.")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = f'🛒 Confirmed Order from {customer_name} (Room {room_number})'
        
        item_rows = "".join(f'<tr><td style="padding: 8px; border: 1px solid #ddd;">{item}</td><td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{qty}</td></tr>' for item, qty in order.items())
        html_body = f"""
        <html><body style="font-family: Arial, sans-serif;">
        <div style="background-color: #f8f9fa; padding: 20px;">
            <div style="background-color: white; border-radius: 10px; padding: 30px; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745; border-bottom: 3px solid #28a745; padding-bottom: 10px;">✅ Confirmed Order</h2>
                <div style="margin: 20px 0;">
                    <p style="margin: 10px 0;"><strong>Customer Name:</strong> {customer_name}</p>
                    <p style="margin: 10px 0;"><strong>Room Number:</strong> {room_number}</p>
                    <p style="margin: 10px 0;"><strong>Phone:</strong> {customer_phone}</p>
                </div>
                <h3 style="color: #333; margin-top: 20px;">Order Items:</h3>
                <table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd; margin-top: 10px;">
                    <thead>
                        <tr style="background-color: #f2f2f2;">
                            <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Item</th>
                            <th style="padding: 12px; border: 1px solid #ddd; text-align: center;">Quantity</th>
                        </tr>
                    </thead>
                    <tbody>{item_rows}</tbody>
                </table>
                <p style="margin-top: 20px; color: #666; font-size: 12px;">This order has been confirmed by the administrator.</p>
            </div>
        </div>
        </body></html>"""
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"✅ Email sent successfully for order: {customer_name}")
        return True
    except Exception as e:
        print(f"❌ Email send failed: {e}")
        return False

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)