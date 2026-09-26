import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
import json

DB_FILE = 'database.json'

def load_database():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    else:
        initial_data = {
            "company": {
                "name": "Arashima Co., Ltd.",
                "address": "Chibaken, Inzaishi, Kosaishinden 4-6",
                "phone": "+81 47-636-4742",
                "fax": "+81 47-636-4842",
                "email": "arashimainzai@gmail.com",
                "tax_invoice_no": "T7040001122584"
            },
            "users": [
                {"username": "admin", "password": "123", "role": "admin", "name": "Admin Boss"}
            ],
            "customers": [],
            "staff": [],
            "cars": [],
            "expenses": []
        }
        save_database(initial_data)
        return initial_data

def save_database(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# গ্লোবাল ডাটাবেজ ইনিশিয়ালাইজেশন
database = load_database()

app = Flask(__name__)
app.secret_key = 'arashima_super_secret_key_12345'

# ক্লাউড ডাটাবেজ URL সেটআপ
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_no = db.Column(db.String(50), nullable=False)
    model_name = db.Column(db.String(50), nullable=False)

    def _repr_(self):
        return f'<Vehicle {self.vehicle_no}>'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- মূল রুট ও হোম পেজ ---
@app.route('/')
def home():
    if 'username' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session.get('role') == 'customer':
            return redirect(url_for('customer_dashboard'))
        elif session.get('role') == 'staff':
            return redirect(url_for('staff_dashboard'))
    return redirect(url_for('login'))


# --- এসকিউএলআলকেমি ভেহিক্যাল পেজ ---
@app.route('/vehicles', methods=['GET', 'POST'])
def vehicles_page():
    if request.method == 'POST':
        v_no = request.form.get('vehicle_no')
        v_model = request.form.get('model_name')
        
        new_vehicle = Vehicle(vehicle_no=v_no, model_name=v_model)
        db.session.add(new_vehicle)
        db.session.commit()
        return redirect(url_for('vehicles_page'))
        
    vehicles = Vehicle.query.all()
    return render_template('vehicles.html', vehicles=vehicles)


# --- লগইন ও অথেন্টিকেশন ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = next((u for u in database.get("users", []) if u.get('username') == username and u.get('password') == password), None)
        if admin_user:
            session['username'] = admin_user['username']
            session['role'] = 'admin'
            session['name'] = admin_user['name']
            return redirect(url_for('admin_dashboard'))
            
        cust_user = next((c for c in database.get("customers", []) if c.get('username') == username and c.get('password') == password), None)
        if cust_user:
            session['username'] = cust_user['username']
            session['role'] = 'customer'
            session['name'] = cust_user.get('company_name', 'Customer')
            return redirect(url_for('customer_dashboard'))
            
        staff_user = next((s for s in database.get("staff", []) if s.get('username') == username and s.get('password') == password), None)
        if staff_user:
            session['username'] = staff_user['username']
            session['role'] = 'staff'
            session['name'] = staff_user['name']
            return redirect(url_for('staff_dashboard'))
            
        error = "Invalid Username or Password!"
        
    return render_template('login.html', error=error, comp=database.get("company", {}))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ADMIN DASHBOARD ---
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    all_cars = database.get("cars", [])
    
    # ইউজার ফিল্টার থেকে কোনো কোম্পানি সিলেক্ট করেছে কি না তা চেক করা
    selected_client = request.args.get('client')
    
    if selected_client and selected_client != 'all' and selected_client != 'All Customers':
        # শুধু সিলেক্ট করা কোম্পানির গাড়িগুলো ফিল্টার করা (এখানে car.get('client_company') ব্যবহার করা হয়েছে)
        cars = [c for c in all_cars if c.get('client_company') == selected_client]
    else:
        cars = all_cars

    staff_list = database.get("staff", [])
    expenses = database.get("expenses", [])
    
    total_contract = sum(float(c.get('contract', 0) or 0) for c in cars)
    total_received = sum(float(c.get('received', 0) or 0) for c in cars)
    total_due = total_contract - total_received
    total_exp = sum(float(ex.get('amount', 0) or 0) for ex in expenses)
    
    return render_template('admin_dashboard.html',
                         comp=database.get("company", {}),
                         cars=cars,
                         staff_list=staff_list,
                         total_contract=total_contract,
                         total_received=total_received,
                         total_due=total_due,
                         total_exp=total_exp,
                         selected_client=selected_client)



@app.route('/admin/receive-payment-dashboard', methods=['POST'])
def receive_payment_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    client_company = request.form.get('client_company')
    car_id = request.form.get('car_id')
    amount_raw = request.form.get('received_amount')
    payment_date = request.form.get('payment_date')
    
    received_amount = float(amount_raw) if amount_raw and amount_raw.strip() != '' else 0.0
    
    if car_id and car_id.strip() != '':
        for car in database.get("cars", []):
            if str(car.get('id')) == str(car_id):
                current_received = float(car.get('received', 0) or 0)
                car['received'] = current_received + received_amount
                
                if 'payment_history' not in car:
                    car['payment_history'] = []
                    
                car['payment_history'].append({
                    "id": str(datetime.now().timestamp()),
                    "client": client_company,
                    "amount": received_amount,
                    "date": payment_date
                })
                break
    else:
        if 'general_payments' not in database:
            database["general_payments"] = []
            
        database["general_payments"].append({
            "client": client_company,
            "amount": received_amount,
            "date": payment_date
        })
            
    save_database(database)
    flash(f"Payment of ¥{received_amount} recorded successfully for {client_company}!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-payment-record/<car_id>/<pay_id>', methods=['POST'])
def delete_payment_record(car_id, pay_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    for car in database.get("cars", []):
        if str(car.get('id')) == str(car_id):
            payments = car.get('payment_history', [])
            for pay in payments:
                if str(pay.get('id')) == str(pay_id):
                    current_received = float(car.get('received', 0) or 0)
                    pay_amount = float(pay.get('amount', 0) or 0)
                    car['received'] = max(0.0, current_received - pay_amount)
                    
                    payments.remove(pay)
                    break
            break
            
    save_database(database)
    flash("Payment record deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/revise-payment/<car_id>/<pay_id>', methods=['POST'])
def revise_payment(car_id, pay_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    new_amount = float(request.form.get('new_amount', 0) or 0)
    new_date = request.form.get('new_date', '')
    
    cars = database.get("cars", [])
    for car in cars:
        if str(car.get('id')) == str(car_id):
            for pay in car.get('payment_history', []):
                if str(pay.get('id')) == str(pay_id):
                    pay['amount'] = new_amount
                    if new_date:
                        pay['date'] = new_date
                    break
            
            total_rec = sum(float(p.get('amount', 0) or 0) for p in car.get('payment_history', []))
            car['received'] = total_rec
            break
            
    save_database(database)
    flash("Payment entry revised successfully!", "success")
    return redirect(url_for('admin_dashboard'))


# --- CUSTOMER MANAGEMENT ---
@app.route('/admin/customers')
def view_customers():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    customers = database.get("customers", [])
    
    for cust in customers:
        cust_cars = [car for car in database.get("cars", []) if car.get('client_company') == cust.get('company_name')]
        
        total_contract = sum(float(car.get('contract', 0) or 0) for car in cust_cars)
        total_received = sum(float(car.get('received', 0) or 0) for car in cust_cars)
        total_due = total_contract - total_received
        
        cust['total_cars'] = len(cust_cars)
        cust['total_contract'] = total_contract
        cust['total_received'] = total_received
        cust['total_due'] = total_due

    return render_template('view_customers.html', customers=customers, comp=database.get("company", {}))


@app.route('/admin/add-customer', methods=['GET', 'POST'])
def add_customer():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        comp_name = request.form.get('company_name')
        owner = request.form.get('owner_name')
        mobile = request.form.get('mobile')
        address = request.form.get('address')
        uname = request.form.get('username')
        pwd = request.form.get('password')
        new_id = max([c.get('id', 0) for c in database["customers"]], default=0) + 1
        database["customers"].append({"id": new_id, "company_name": comp_name, "owner_name": owner, "mobile": mobile, "address": address, "username": uname, "password": pwd})
        save_database(database)
        return redirect(url_for('view_customers'))
    return render_template('add_customer.html', comp=database.get("company", {}))


@app.route('/admin/edit-customer/<int:cust_id>', methods=['GET', 'POST'])
def edit_customer(cust_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    cust = next((c for c in database["customers"] if c.get('id') == cust_id), None)
    if not cust:
        return redirect(url_for('view_customers'))
        
    if request.method == 'POST':
        old_company_name = cust['company_name']
        new_company_name = request.form.get('company_name')
        
        cust['company_name'] = new_company_name
        cust['owner_name'] = request.form.get('owner_name')
        cust['mobile'] = request.form.get('mobile')
        cust['address'] = request.form.get('address')
        cust['username'] = request.form.get('username')
        if request.form.get('password'):
            cust['password'] = request.form.get('password')
            
        if old_company_name != new_company_name:
            for car in database["cars"]:
                if car.get('client_company') == old_company_name:
                    car['client_company'] = new_company_name
                    
        save_database(database)
        flash("Customer updated successfully!", "success")
        return redirect(url_for('view_customers'))
        
    return render_template('edit_customer.html', comp=database.get("company", {}), cust=cust)


@app.route('/admin/customer/delete/<customer_id>', methods=['POST'])
def delete_customer(customer_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    database["customers"] = [
        c for c in database.get("customers", []) 
        if str(c.get('id')) != str(customer_id) and str(c.get('name', '')).strip() != str(customer_id).strip()
    ]
    save_database(database)
    flash("Customer profile deleted successfully!", "success")
    return redirect(url_for('view_customers'))


# --- CAR MANAGEMENT ---
@app.route('/admin/receive-car', methods=['GET', 'POST'])
def receive_car():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        car_name = request.form.get('car_name')
        chassis = request.form.get('chassis')
        color_name = request.form.get('color_name')
        color_code = request.form.get('color_code')
        client_company = request.form.get('client_company')
        contract = float(request.form.get('contract', 0) or 0)
        received = float(request.form.get('received', 0) or 0)
        details = request.form.get('details')
        assigned_staff = request.form.get('assigned_staff')
        status = request.form.get('status', 'In Progress')
        receiving_date = request.form.get('receiving_date', datetime.now().strftime('%Y-%m-%d'))
        
        before_files = request.files.getlist('before_images')
        saved_before = []
        for file in before_files:
            if file and allowed_file(file.filename):
                filename = secure_filename("before_" + datetime.now().strftime('%Y%m%d%H%M%S') + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                saved_before.append(filename)
                
        after_files = request.files.getlist('after_images')
        saved_after = []
        for file in after_files:
            if file and allowed_file(file.filename):
                filename = secure_filename("after_" + datetime.now().strftime('%Y%m%d%H%M%S') + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                saved_after.append(filename)
                
        new_id = max([c.get('id', 0) for c in database["cars"]], default=0) + 1
        database["cars"].append({
            "id": new_id, "car_name": car_name, "chassis": chassis, 
            "color_name": color_name, "color_code": color_code, 
            "client_company": client_company, "contract": contract, 
            "received": received, "details": details, 
            "receiving_date": receiving_date, 
            "before_images": saved_before, "after_images": saved_after, 
            "status": status, "assigned_staff": assigned_staff
        })
        save_database(database)
        return redirect(url_for('admin_dashboard'))
    return render_template('receive_car.html', comp=database.get("company", {}), customers=database.get("customers", []), staff_list=database.get("staff", []))


@app.route('/admin/update-car-dashboard/<int:car_id>', methods=['POST'])
def update_car_dashboard(car_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    car = next((c for c in database["cars"] if c.get('id') == car_id), None)
    if car:
        car['contract'] = float(request.form.get('contract', car.get('contract', 0)) or 0)
        additional_received = float(request.form.get('received', 0) or 0)
        payment_date = request.form.get('payment_date', datetime.now().strftime('%Y-%m-%d'))
        
        if additional_received > 0:
            car['received'] = float(car.get('received', 0) or 0) + additional_received
            if 'payment_history' not in car:
                car['payment_history'] = []
            pay_id = str(datetime.now().timestamp())
            car['payment_history'].append({
                "id": pay_id,
                "amount": additional_received,
                "date": payment_date
            })

        car['status'] = request.form.get('status', car.get('status', ''))
        car['assigned_staff'] = request.form.get('assigned_staff', car.get('assigned_staff', ''))
        car['details'] = request.form.get('details', car.get('details', ''))
        
        if request.form.get('receiving_date'):
            car['receiving_date'] = request.form.get('receiving_date')
            
        if request.form.get('delivery_date'):
            car['delivery_date'] = request.form.get('delivery_date')
        elif car['status'] == 'Delivered' and not car.get('delivery_date'):
            car['delivery_date'] = datetime.now().strftime('%Y-%m-%d')
        elif car['status'] != 'Delivered':
            car['delivery_date'] = ''
        
        after_files = request.files.getlist('after_images')
        for file in after_files:
            if file and allowed_file(file.filename):
                filename = secure_filename("after_" + datetime.now().strftime('%Y%m%d%H%M%S') + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                if 'after_images' not in car or car['after_images'] is None:
                    car['after_images'] = []
                car['after_images'].append(filename)
                
        save_database(database)
        
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-car-dashboard/<int:car_id>', methods=['POST'])
def delete_car_dashboard(car_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    database["cars"] = [c for c in database["cars"] if c.get('id') != car_id]
    save_database(database)
    return redirect(url_for('admin_dashboard'))


# --- STAFF MANAGEMENT & DIRECTORY ---
@app.route('/admin/staff-list')
def view_staff():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    staff_list = database.get("staff", [])
    return render_template('staff_list.html', staff_list=staff_list, comp=database.get("company", {}))


@app.route('/admin/attendance')
@app.route('/admin/attendance/<staff_id>')
def attendance(staff_id=None):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    comp = database.get("company", {})
    staff_list = database.get("staff", [])
    
    staff = None
    if staff_id:
        for st in staff_list:
            if str(st.get('id')) == str(staff_id):
                staff = st
                break
    
    if not staff and staff_list:
        staff = staff_list[0]
    elif not staff:
        staff = {'name': 'Select Staff', 'advance_balance': 0.0}
            
    return render_template('staff_leave_history.html', staff_list=staff_list, staff=staff, comp=comp)


@app.route('/admin/add_staff', methods=['GET', 'POST'])
def add_staff():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        mobile = request.form.get('mobile')
        address = request.form.get('address')
        base_salary = float(request.form.get('base_salary', 0) or 0)
        
        new_id = max([s.get('id', 0) for s in database.get("staff", [])], default=0) + 1
        new_staff = {
            "id": new_id,
            "name": name,
            "username": username,
            "password": password,
            "mobile": mobile,
            "address": address,
            "base_salary": base_salary,
            "advance_balance": 0.0,
            "leave_history": [],
            "advance_history": [],
            "overtime_history": [],
            "holiday_work_history": []
        }
        
        database.setdefault("staff", []).append(new_staff)
        save_database(database)

        flash("Staff added successfully!", "success")
        return redirect(url_for('view_staff'))
        
    return render_template('add_staff.html', comp=database.get("company", {}))


@app.route('/admin/edit-staff/<staff_id>', methods=['POST'])
def edit_staff(staff_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    name = request.form.get('name')
    mobile = request.form.get('mobile')
    username = request.form.get('username')
    password = request.form.get('password')
    base_salary = float(request.form.get('base_salary', 0) or 0)
    
    for st in database.get("staff", []):
        if str(st.get('id')) == str(staff_id) or str(st.get('name')).strip() == str(staff_id).strip():
            st['name'] = name
            st['mobile'] = mobile
            st['username'] = username
            if password and password.strip() != "":
                st['password'] = password
            st['base_salary'] = base_salary
            break
            
    save_database(database)
    flash("Staff profile updated successfully!", "success")
    return redirect(url_for('view_staff'))


@app.route('/admin/delete-staff/<staff_id>', methods=['POST'])
def delete_staff(staff_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    database["staff"] = [st for st in database.get("staff", []) if str(st.get('id')) != str(staff_id) and str(st.get('name')).strip() != str(staff_id).strip()]
    
    save_database(database)
    flash("Staff profile deleted successfully!", "success")
    return redirect(url_for('view_staff'))


@app.route('/admin/add-leave/<staff_id>', methods=['POST'])
def add_leave(staff_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    leave_date = request.form.get('leave_date')
    reason = request.form.get('reason', 'Absent')
    
    for st in database.get("staff", []):
        if str(st.get('id')) == str(staff_id) or str(st.get('name')).strip() == str(staff_id).strip():
            st.setdefault('leave_history', []).append({
                "id": str(datetime.now().timestamp()),
                "date": leave_date,
                "reason": reason
            })
            break
            
    save_database(database)
    flash("Absent record added successfully!", "success")
    return redirect(url_for('view_staff'))


@app.route('/admin/add-advance', methods=['POST'])
def add_staff_advance():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    staff_name = request.form.get('staff_name')
    try:
        amount = float(request.form.get('advance_amount', 0) or 0)
    except ValueError:
        amount = 0.0
        
    adv_date = request.form.get('advance_date')
    
    for st in database.get("staff", []):
        if str(st.get('name')).strip() == str(staff_name).strip():
            st.setdefault('advance_history', []).append({
                "id": str(datetime.now().timestamp()),
                "date": adv_date,
                "amount": amount
            })
            break
            
    save_database(database)
    flash("Advance amount added successfully!", "success")
    return redirect(url_for('admin_dashboard'))


# --- ঠিক করা ওভারটাইম ও হলিডে ওয়ার্ক রুট ---
@app.route('/add_staff_overtime_holiday', methods=['POST'])
def add_staff_overtime_holiday():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    staff_name = request.form.get('staff_name')
    entry_type = request.form.get('entry_type')
    work_date = request.form.get('work_date')
    
    target_staff = None
    for st in database.get("staff", []):
        if str(st.get('name')).strip() == str(staff_name).strip():
            target_staff = st
            break
            
    if target_staff:
        if entry_type == 'overtime':
            try:
                minutes = int(request.form.get('overtime_minutes', 0) or 0)
            except ValueError:
                minutes = 0
                
            target_staff.setdefault('overtime_history', []).append({
                "id": str(datetime.now().timestamp()),
                'date': work_date,
                'minutes': minutes
            })
            
        elif entry_type == 'holiday':
            holiday_note = request.form.get('holiday_note', 'Full Day Holiday Work')
            
            target_staff.setdefault('holiday_work_history', []).append({
                "id": str(datetime.now().timestamp()),
                'date': work_date,
                'note': holiday_note
            })
            
        save_database(database)
        flash("Overtime or Holiday work added successfully!", "success")
        
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-record/<staff_id>/<record_type>/<record_id>', methods=['POST'])
def delete_record(staff_id, record_type, record_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    for st in database.get("staff", []):
        if str(st.get('id')) == str(staff_id) or str(st.get('name')).strip() == str(staff_id).strip():
            if record_type == 'leave':
                st['leave_history'] = [l for l in st.get('leave_history', []) if str(l.get('id')) != str(record_id)]
            elif record_type == 'advance':
                st['advance_history'] = [adv for adv in st.get('advance_history', []) if str(adv.get('id')) != str(record_id)]
            elif record_type == 'overtime':
                st['overtime_history'] = [ot for ot in st.get('overtime_history', []) if str(ot.get('id')) != str(record_id)]
            elif record_type == 'holiday':
                st['holiday_work_history'] = [h for h in st.get('holiday_work_history', []) if str(h.get('id')) != str(record_id)]
            break
            
    save_database(database)
    flash("Record deleted successfully!", "success")
    return redirect(url_for('view_staff'))


# --- DAILY EXPENSES MANAGEMENT ---
@app.route('/admin/expenses', methods=['GET', 'POST'])
def manage_expenses():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        date = request.form.get('date')
        item = request.form.get('item')
        amount = float(request.form.get('amount', 0) or 0)
        new_id = max([e.get('id', 0) for e in database["expenses"]], default=0) + 1
        database["expenses"].append({"id": new_id, "date": date, "item": item, "amount": amount})
        save_database(database)
        return redirect(url_for('manage_expenses'))
        
    current_year_month = datetime.now().strftime('%Y-%m')
    monthly_expenses = [e for e in database["expenses"] if str(e.get('date', '')).startswith(current_year_month)]
    total_monthly_exp = sum(float(e.get('amount', 0) or 0) for e in monthly_expenses)
    return render_template('expenses.html', comp=database.get("company", {}), expenses=database["expenses"], total_monthly_exp=total_monthly_exp, current_month=datetime.now().strftime('%B, %Y'), edit_exp=None)


@app.route('/admin/delete-expense/<int:exp_id>', methods=['POST'])
def delete_expense(exp_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    database["expenses"] = [e for e in database["expenses"] if e.get('id') != exp_id]
    save_database(database)
    return redirect(url_for('manage_expenses'))

@app.route('/admin/edit-expense/<int:exp_id>', methods=['GET', 'POST'])
def edit_expense(exp_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    expense = next((e for e in database["expenses"] if e.get('id') == exp_id), None)
    if not expense:
        return redirect(url_for('manage_expenses'))
        
    if request.method == 'POST':
        expense['date'] = request.form.get('date')
        expense['item'] = request.form.get('item')
        expense['amount'] = float(request.form.get('amount', 0) or 0)
        save_database(database)
        flash("Expense updated successfully!", "success")
        return redirect(url_for('manage_expenses'))
        
    return render_template('expenses.html', comp=database.get("company", {}), expenses=database["expenses"], total_monthly_exp=0, current_month="", edit_exp=expense)




# --- CUSTOMER PORTAL & INVOICE ---
@app.route('/customer/invoice/<int:car_id>')
def customer_invoice(car_id):
    if 'role' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
    car = next((c for c in database["cars"] if c.get('id') == car_id), None)
    if not car:
        return "Car not found", 404
    if car.get('client_company') != session.get('name'):
        return "Unauthorized Access", 403
    comp = database.get("company", {})
    cust = next((cust for cust in database.get("customers", []) if cust.get('company_name') == car.get('client_company')), None)
    return render_template('invoice.html', car=car, comp=comp, cust=cust)


@app.route('/customer/dashboard', methods=['GET', 'POST'])
def customer_dashboard():
    if 'role' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
        
    cust = next((c for c in database.get("customers", []) if c.get('username') == session.get('username')), None)
    client_company = cust.get('company_name') if cust else session.get('name')
    customer_cars = [c for c in database.get("cars", []) if c.get('client_company') == client_company]
    
    total_contract = sum(float(c.get('contract', 0) or 0) for c in customer_cars)
    total_paid = sum(float(c.get('received', 0) or 0) for c in customer_cars)
    total_due = total_contract - total_paid
    
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    monthly_cars = []
    monthly_paid = 0
    monthly_contract = 0
    
    for c in customer_cars:
        d_date = c.get('delivery_date', '')
        if (d_date and str(d_date).startswith(selected_month)) or (str(c.get('receiving_date', '')).startswith(selected_month)):
            monthly_cars.append(c)
            monthly_contract += float(c.get('contract', 0) or 0)
            monthly_paid += float(c.get('received', 0) or 0)
            
    monthly_due_calc = monthly_contract - monthly_paid
    
    return render_template('customer_dashboard.html', 
                           comp=database.get("company", {}), cars=customer_cars, monthly_cars=monthly_cars,
                           total_contract=total_contract, total_paid=total_paid, total_due=total_due, 
                           cust=cust, selected_month=selected_month, monthly_contract=monthly_contract,
                           monthly_paid=monthly_paid, monthly_due=monthly_due_calc)


# --- STAFF PORTAL DASHBOARD (COMPLETELY MONTHLY REFRESHED) ---
@app.route('/staff/dashboard')
def staff_dashboard():
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('login'))
    
    staff_name = session.get('name', '')
    current_staff = next((s for s in database.get("staff", []) if str(s.get('name', '')).strip().lower() == staff_name.strip().lower()), {
        "base_salary": 0, "name": staff_name, "salary_history": [], "advance_history": [], "leave_history": [], "overtime_history": [], "holiday_work_history": []
    })
    
    actual_staff_name = current_staff.get('name', staff_name)
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    assigned_cars = [c for c in database.get("cars", []) if str(c.get('assigned_staff', '')).strip().lower() == actual_staff_name.strip().lower()]
    
    def matches_selected_month(car):
        for field in ['date', 'delivery_date', 'receiving_date', 'created_at', 'completion_date', 'updated_at']:
            val = str(car.get(field, '')).strip()
            if val and val.startswith(selected_month):
                return True
        return False

    in_progress_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() in ['in progress', 'processing', 'in processing'] and matches_selected_month(c)]
    queue_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() in ['pending', 'waiting', 'in queue', 'queue'] and matches_selected_month(c)]
    delivered_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() == 'delivered' and matches_selected_month(c)]
    completed_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() in ['completed', 'complete', 'done'] and matches_selected_month(c)]
    
    month_work_history = [c for c in assigned_cars if matches_selected_month(c)]
    total_car_history = assigned_cars

    all_advances = current_staff.get('advance_history', [])
    monthly_advances = [adv for adv in all_advances if str(adv.get('date', '')).startswith(selected_month)]
    monthly_advance_total = sum(float(adv.get('amount', 0)) for adv in monthly_advances)

    all_leaves = current_staff.get('leave_history', [])
    staff_leaves = [leave for leave in all_leaves if str(leave.get('date', leave.get('leave_date', ''))).startswith(selected_month)]
    monthly_leave_days = len(staff_leaves)

    all_overtime = current_staff.get('overtime_history', [])
    monthly_overtime = [ot for ot in all_overtime if str(ot.get('date', '')).startswith(selected_month)]
    monthly_overtime_minutes = sum(int(ot.get('minutes', ot.get('overtime_minutes', 0))) for ot in monthly_overtime)
    
    all_holidays = current_staff.get('holiday_work_history', [])
    monthly_holidays = [hw for hw in all_holidays if str(hw.get('date', '')).startswith(selected_month)]
    holiday_work_days = float(len(monthly_holidays))

    base_salary = float(current_staff.get('base_salary', 0) or 0)
    per_day_salary = base_salary / 26 if base_salary > 0 else 0
    per_minute_salary = (per_day_salary / 480) if per_day_salary > 0 else 0
    
    deduction_amount = monthly_leave_days * per_day_salary
    holiday_bonus = holiday_work_days * per_day_salary * 1.25
    overtime_bonus = monthly_overtime_minutes * per_minute_salary * 1.25
    
    net_salary = base_salary - deduction_amount + holiday_bonus + overtime_bonus - monthly_advance_total
    
    current_staff_display = dict(current_staff)
    current_staff_display['monthly_advance_total'] = monthly_advance_total
    current_staff_display['advance_balance'] = monthly_advance_total
    current_staff_display['advance_history'] = monthly_advances
    current_staff_display['monthly_overtime_minutes'] = monthly_overtime_minutes
    current_staff_display['monthly_holidays'] = monthly_holidays

    return render_template('staff_dashboard.html', 
                           comp=database.get("company", {}), 
                           staff=current_staff_display, 
                           cars=assigned_cars,
                           in_progress_cars=in_progress_cars, 
                           completed_cars=completed_cars, 
                           queue_cars=queue_cars,
                           delivered_cars=delivered_cars,
                           month_work_history=month_work_history,
                           total_car_history=total_car_history,
                           staff_leaves=staff_leaves,
                           monthly_overtime=monthly_overtime,
                           selected_month=selected_month,
                           completed_count=len(completed_cars), 
                           in_progress_count=len(in_progress_cars),
                           per_day_salary=round(per_day_salary, 2), 
                           holiday_bonus=round(holiday_bonus, 2),
                           overtime_bonus=round(overtime_bonus, 2),
                           net_salary=round(net_salary, 2), 
                           staff_name=actual_staff_name)


if __name__ == '__main__':
    app.run(debug=True, port=5000)