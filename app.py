# app.py - Final, unified version
import os
import json
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash 
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import argparse
import re
from datetime import datetime
import time
import csv # <--- ADDED IMPORT
import pandas as pd # <--- ADDED IMPORT FOR ANALYSIS
 # Use a non-interactive backend for matplotlib


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

# Command line argument parsing
#parser = argparse.ArgumentParser(description='Order Form Website')
#parser.add_argument('--port', type=int, default=5001, help='Port to run the server on (default: 5001)')
#parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
#parser.add_argument("--bind", type=str, default=False)

#if len(sys.argv) > 1:
#    args = parser.parse_args()
#else:
    # Default values when no command line args are given
#    class Args:
 #       host = '0.0.0.0'
  #      port = 5001
   # args = Args()

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
ITEMS_FILE = 'items.json'

def load_items():
    try:
        if os.path.exists(ITEMS_FILE):
            with open(ITEMS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading items: {e}")
        return []

def save_items(items):
    try:
        with open(ITEMS_FILE, 'w') as f:
            json.dump(items, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving items: {e}")
        return False

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
    
    if request.method == 'GET':
        # ... (Your existing GET logic remains the same) ...
        pass
    
    items = [item for item in all_items if search_query in item['name'].lower()] if search_query else all_items

    if request.method == 'POST':
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

            # --- START: New code for saving order to orders.csv ---
            try:
                csv_file = 'orders.csv'
                order_timestamp = datetime.now().isoformat()
                
                # Check if the file exists to decide on writing headers
                file_exists = os.path.isfile(csv_file)

                with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    if not file_exists:
                        writer.writerow(['timestamp', 'customer_name', 'item_name', 'quantity'])
                    
                    # Write each item from the order as a separate row
                    for item_name, quantity in order.items():
                        writer.writerow([order_timestamp, customer_name, item_name, quantity])

            except Exception as e:
                print(f"Error writing to CSV: {e}")
            # --- END: New code for saving order to orders.csv ---

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

# Replace your existing admin_panel function with this one
# app.py

# (Keep all your other code like imports, load_items, save_items, etc.)

@app.route('/admin/', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    items = load_items()

    if request.method == 'POST':
        action = request.form.get('action')
        

        # === HANDLE ADDING A SINGLE ITEM ===
        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                new_item = {
                    'id': str(int(time.time() * 1000)), # Simple unique ID
                    'name': name
                }
                items.append(new_item)
                if save_items(items):
                    flash(f'✅ ნივთი "{name}" წარმატებით დაემატა.', 'success')
                else:
                    flash('❌ ნივთის შენახვა ვერ მოხერხდა.', 'error')
            else:
                flash('⚠️ გთხოვთ, შეიყვანოთ ნივთის დასახელება.', 'warning')

        # === HANDLE ADDING ITEMS IN BULK ===
        elif action == 'bulk_add':
            bulk_items_str = request.form.get('bulk_items', '').strip()
            if bulk_items_str:
                added_count = 0
                new_items = [item.strip() for item in bulk_items_str.splitlines() if item.strip()]
                for name in new_items:
                    new_item = {
                        'id': str(int(time.time() * 1000)) + str(added_count), # Ensure unique ID in loop
                        'name': name
                    }
                    items.append(new_item)
                    added_count += 1
                
                if added_count > 0 and save_items(items):
                    flash(f'✅ წარმატებით დაემატა {added_count} ნივთი.', 'success')
                else:
                    flash('❌ ნივთების შენახვა ვერ მოხერხდა.', 'error')
            else:
                flash('⚠️ გთხოვთ, შეიყვანოთ ნივთები ჯგუფურად დასამატებლად.', 'warning')


        # === HANDLE EDITING AN ITEM ===
        elif action == 'edit':
            item_id = request.form.get('id')
            new_name = request.form.get('name', '').strip()
            item_found = False
            if item_id and new_name:
                for item in items:
                    if item['id'] == item_id:
                        original_name = item['name']
                        item['name'] = new_name
                        item_found = True
                        break
                if item_found and save_items(items):
                    flash(f'✅ ნივთი "{original_name}" განახლდა на "{new_name}".', 'success')
                else:
                    flash('❌ ნივთის განახლება ვერ მოხერხდა.', 'error')
            else:
                flash('⚠️ რედაქტირებისთვის საჭიროა ID და ახალი სახელი.', 'warning')
        
        # === HANDLE DELETING AN ITEM ===
        elif action == 'delete':
            item_id = request.form.get('id')
            item_to_delete = None
            if item_id:
                for item in items:
                    if item['id'] == item_id:
                        item_to_delete = item
                        break
                if item_to_delete:
                    items.remove(item_to_delete)
                    if save_items(items):
                        flash(f'✅ ნივთი "{item_to_delete["name"]}" წაიშალა.', 'success')
                    else:
                        flash('❌ ნივთის წაშლა ვერ მოხერხდა.', 'error')
                else:
                    flash('⚠️ წასაშლელი ნივთი ვერ მოიძებნა.', 'warning')

        return redirect(url_for('admin_panel'))

    # --- Report generation logic (remains the same) ---
    report_data = None
    try:
        df = pd.read_csv('orders.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['quantity'] = pd.to_numeric(df['quantity'])
        weekly_item_summary = df.groupby([pd.Grouper(key='timestamp', freq='W-SUN'), 'item_name'])['quantity'].sum().unstack(fill_value=0)
        if not weekly_item_summary.empty:
            report_data = weekly_item_summary.reset_index()
            report_data['timestamp'] = report_data['timestamp'].dt.strftime('%Y-%m-%d')
            report_data = report_data.to_dict(orient='records')
    except FileNotFoundError:
        print("orders.csv not found. No report to generate.")
    except Exception as e:
        print(f"An error occurred during report generation: {e}")

    return render_template('admin_panel.html', items=items, report_data=report_data)

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

#if __name__ == '__main__':
    print(f"🚀 Starting server on {args.host}:{args.port}")
    app.run(debug=True, host=args.host, port=args.port)