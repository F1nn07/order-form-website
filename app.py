# app.py - Caching Version
import os
import json
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import csv
import pandas as pd

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

# --- START: Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "data", "inventory.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# --- END: Database Configuration ---

# --- START: Database Models ---
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    room_number = db.Column(db.String(50), nullable=False)
    # This 'relationship' links an Order to its items
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
# --- END: Database Models ---


# --- START: Caching Implementation ---
# Cache will hold our data in memory
_cache = {
    "items": None,
    "items_timestamp": None,
    "report_data": None,
    "report_timestamp": None,
}
CACHE_TIMEOUT = timedelta(seconds=10) # Reload data from disk every 10 seconds
# --- END: Caching Implementation ---


# Environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'default_admin_password')
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER', 'your_receiver_email@example.com')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

if not all([SECRET_KEY, ADMIN_PASSWORD, EMAIL_SENDER, EMAIL_PASSWORD]):
    print("❌ CRITICAL: Missing required environment variables in .env file!")
    sys.exit(1)

ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)
ITEMS_FILE = 'data/items.json'
ORDERS_FILE = 'data/orders.csv'

def load_items(force_reload=False):
    """Loads items from file or returns from cache."""
    now = datetime.now()
    if not force_reload and _cache["items"] is not None and _cache["items_timestamp"] and (now - _cache["items_timestamp"]) < CACHE_TIMEOUT:
        return _cache["items"]
    
    try:
        if os.path.exists(ITEMS_FILE):
            with open(ITEMS_FILE, 'r') as f:
                items = json.load(f)
                _cache["items"] = items
                _cache["items_timestamp"] = now
                return items
        return []
    except Exception as e:
        print(f"Error loading items: {e}")
        return []

def save_items(items):
    """Saves items to file and clears the cache."""
    try:
        with open(ITEMS_FILE, 'w') as f:
            json.dump(items, f, indent=4)
        _cache["items"] = None # Invalidate cache
        return True
    except Exception as e:
        print(f"Error saving items: {e}")
        return False

def generate_report_data(force_reload=False):
    """Generates report from file or returns from cache."""
    now = datetime.now()
    if not force_reload and _cache["report_data"] is not None and _cache["report_timestamp"] and (now - _cache["report_timestamp"]) < CACHE_TIMEOUT:
        return _cache["report_data"]

    try:
        df = pd.read_csv(ORDERS_FILE)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['quantity'] = pd.to_numeric(df['quantity'])
        weekly_item_summary = df.groupby([pd.Grouper(key='timestamp', freq='W-SUN'), 'item_name'])['quantity'].sum().unstack(fill_value=0)
        if not weekly_item_summary.empty:
            report_data = weekly_item_summary.reset_index()
            report_data['timestamp'] = report_data['timestamp'].dt.strftime('%Y-%m-%d')
            report_data_dict = report_data.to_dict(orient='records')
            _cache["report_data"] = report_data_dict
            _cache["report_timestamp"] = now
            return report_data_dict
        return None
    except FileNotFoundError:
        # print("orders.csv not found for report. This is normal if no orders exist.")
        return None
    except Exception as e:
        print(f"An error occurred during report generation: {e}")
        return None

# (Keep your send_order_email function as is)
def send_order_email(customer_name, customer_phone, room_number, order):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER
        msg['Subject'] = f'🛒 ახალი შეკვეთა {customer_name}-სგან (ოთახი {room_number})'
        
        item_rows = ""
        for item, qty in order.items():
            item_rows += f"""
            <tr style="border-bottom: 1px solid #dddddd;">
                <td style="padding: 12px 15px; text-align: left;">{item}</td>
                <td style="padding: 12px 15px; text-align: center;">{qty}</td>
            </tr>
            """

        html_body = f"""
        <!DOCTYPE html>
        <html lang="ka">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ახალი შეკვეთა</title>
        </head>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f6;">
            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                <tr>
                    <td style="padding: 30px; text-align: center; background-color: #004149; color: #ffffff; border-top-left-radius: 8px; border-top-right-radius: 8px;">
                        <h1 style="margin: 0; font-size: 28px;">მიღებულია ახალი შეკვეთა</h1>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 30px;">
                        <h2 style="font-size: 20px; color: #333333; border-bottom: 2px solid #eeeeee; padding-bottom: 10px;">მომხმარებლის მონაცემები</h2>
                        <p style="font-size: 16px; color: #555555; line-height: 1.6;">
                            <strong>სახელი:</strong> {customer_name}<br>
                            <strong>ოთახი:</strong> {room_number}<br>
                            <strong>ტელეფონი:</strong> {customer_phone}
                        </p>
                        
                        <h2 style="font-size: 20px; color: #333333; border-bottom: 2px solid #eeeeee; padding-bottom: 10px; margin-top: 30px;">შეკვეთის დეტალები</h2>
                        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 20px; border-collapse: collapse;">
                            <thead>
                                <tr style="background-color: #f2f2f2;">
                                    <th style="padding: 12px 15px; text-align: left; color: #333;">ნივთის დასახელება</th>
                                    <th style="padding: 12px 15px; text-align: center; color: #333;">რაოდენობა</th>
                                </tr>
                            </thead>
                            <tbody>
                                {item_rows}
                            </tbody>
                        </table>
                    </td>
                </tr>
                <tr>
                    <td style="text-align: center; padding: 20px; font-size: 12px; color: #999999; background-color: #f4f7f6; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;">
                        ეს არის ავტომატური შეტყობინება შეკვეთების სისტემიდან.
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_body, 'html'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        _cache["report_data"] = None # Invalidate report cache after a new order
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        print(traceback.format_exc())
        return False
@app.route('/', methods=['GET', 'POST'])
def index():
    all_items = load_items()
    search_query = request.args.get('search', '').lower()

    form_data = {
        'customer_name': session.get('customer_name', ''),
        'customer_phone': session.get('customer_phone', ''),
        'room_number': session.get('room_number', ''),
        'quantities': session.get('quantities', {})
    }
    
    items = [item for item in all_items if search_query in item['name'].lower()] if search_query else all_items

    if request.method == 'POST':
        # (Your POST logic for index remains the same)
        customer_name = request.form.get('customer_name', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        room_number = request.form.get('room_number', '').strip()
        session['customer_name'] = customer_name
        session['customer_phone'] = customer_phone
        session['room_number'] = room_number
        session['quantities'] = {f'qty_{item["id"]}': request.form.get(f'qty_{item["id"]}', '0') for item in all_items}

        missing_fields = []
        if not customer_name: missing_fields.append("Name")
        if not customer_phone: missing_fields.append("Phone Number")
        if not room_number: missing_fields.append("Room Number")

        if missing_fields:
            flash(f'❌ გთხოვთ შეავსოთ ყველა საჭირო ველი: {", ".join(missing_fields)}.', 'შეცდომა')
            return render_template('index.html', items=items, all_items=all_items, search_query=search_query, form_data=form_data)
        
        order = {}
        has_items = False
        for item in all_items:
            qty_field = f'qty_{item["id"]}'
            qty = request.form.get(qty_field, '0')
            try:
                qty_int = int(qty)
                if qty_int > 0:
                    order[item['name']] = qty_int
                    has_items = True
            except ValueError:
                continue

        if not has_items:
            flash('⚠️ გთხოვთ აირჩიეთ ნივთი', 'გაფრთხილება')
            return render_template('index.html', items=items, all_items=all_items, search_query=search_query, form_data=form_data)

        if send_order_email(customer_name, customer_phone, room_number, order):
            flash(f'✅ შეკვეთა წარმატებით განხორციელდა, {customer_name}!', 'წარმატებულია')

            try:
                order_timestamp = datetime.now().isoformat()
                file_exists = os.path.isfile(ORDERS_FILE)
                with open(ORDERS_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(['timestamp', 'customer_name', 'item_name', 'quantity'])
                    for item_name, quantity in order.items():
                        writer.writerow([order_timestamp, customer_name, item_name, quantity])
            except Exception as e:
                print(f"Error writing to CSV: {e}")

            if 'quantities' in session:
                del session['quantities']
        else:
            flash('❌ შეკვეთა მიღებულია, მაგრამ ელ.ფოსტა ვერ გაიგზავნა. გთხოვთ, დაუკავშირდეთ ჩვენ.', 'შეცდომა')

        return redirect(url_for('index'))

    return render_template('index.html', items=items, all_items=all_items, search_query=search_query, form_data=form_data)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            flash('✅ მოგესალმებით ადმინ პანელში', 'წარმატებულია')
            return redirect(url_for('admin_panel'))
        else:
            flash('❌ პაროლი არასწორია სცადეთ ხელახლა.', 'შეცდომა')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('👋 წარმატებით გამოვიდა.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        action = request.form.get('action')

        # === HANDLE ADDING A SINGLE ITEM ===
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                # Check if item already exists to prevent duplicates
                existing_item = Item.query.filter_by(name=name).first()
                if existing_item:
                    flash(f'⚠️ Item "{name}" already exists.', 'warning')
                else:
                    new_item = Item(name=name)
                    db.session.add(new_item)    # <-- Saves to database
                    db.session.commit()         # <-- Commits the change
                    flash(f'✅ Item "{name}" added successfully.', 'success')
            else:
                flash('⚠️ Please enter an item name.', 'warning')

        # === HANDLE EDITING AN ITEM ===
        elif action == 'edit':
            item_id = request.form.get('id')
            new_name = request.form.get('name', '').strip()
            item_to_edit = Item.query.get(item_id) # <-- Get item from DB
            if item_to_edit and new_name:
                item_to_edit.name = new_name
                db.session.commit()             # <-- Update in DB
                flash(f'✅ Item updated to "{new_name}".', 'success')

        # === HANDLE DELETING AN ITEM ===
        elif action == 'delete':
            item_id = request.form.get('id')
            item_to_delete = Item.query.get(item_id) # <-- Get item from DB by ID
            if item_to_delete:
                db.session.delete(item_to_delete)    # <-- Delete from DB
                db.session.commit()
                flash(f'✅ Item "{item_to_delete.name}" has been deleted.', 'success')
        # You can add the 'bulk_add' logic here later if you need it

        return redirect(url_for('admin_panel'))

    # For GET requests, fetch items from the database
    items = Item.query.order_by(Item.name).all() # <-- Reads from database
    return render_template('admin_panel.html', items=items, report_data=None)
# (Keep your save_progress and clear_session functions as is)
@app.route('/save-progress', methods=['POST'])
def save_progress():
    try:
        data = request.get_json()
        if not data:
            return "No data received", 400

        session['customer_name'] = data.get('customer_name', '')
        session['customer_phone'] = data.get('customer_phone', '')
        session['room_number'] = data.get('room_number', '')
        
        current_quantities = session.get('quantities', {})
        new_quantities = data.get('quantities', {})
        current_quantities.update(new_quantities)
        session['quantities'] = current_quantities

        return "Progress saved successfully", 200
    except Exception as e:
        print(f"Error saving progress: {e}")
        return "Internal server error", 500
    
@app.route('/clear-session', methods=['POST'])
def clear_session():
    session.pop('customer_name', None)
    session.pop('customer_phone', None)
    session.pop('room_number', None)
    session.pop('quantities', None)
    return "Session cleared", 200
