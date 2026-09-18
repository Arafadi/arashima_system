import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)

# ক্লাউড ডাটাবেজ URL সেটআপ
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# অনলাইনে PostgreSQL এবং লোকাল কম্পিউটারে SQLite ব্যবহার করার কনফিগারেশন
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)



UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

database = {
    "company": {
        "name": "Arashima Co., Ltd.",
        "address": "Chibaken, Inzaishi, Kosaishinden 4-6",
        "phone": "+81 47-636-4742",
        "fax": "+81 47-636-4842"
    },
    "users": [
        {"username": "admin", "password": "6869", "role": "admin", "name": "Admin Boss"}
    ],
    "customers": [],
    "staff": [],
    "cars": [],
    "expenses": []
}

@app.route('/')
def home():
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'customer':
            return redirect(url_for('customer_dashboard'))
        elif session['role'] == 'staff':
            return redirect(url_for('staff_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin_user = next((u for u in database["users"] if u['username'] == username and u['password'] == password), None)
        if admin_user:
            session['username'] = admin_user['username']
            session['role'] = 'admin'
            session['name'] = admin_user['name']
            return redirect(url_for('admin_dashboard'))
        
        cust_user = next((c for c in database["customers"] if c['username'] == username and c['password'] == password), None)
        if cust_user:
            session['username'] = cust_user['username']
            session['role'] = 'customer'
            session['name'] = cust_user['company_name']
            return redirect(url_for('customer_dashboard'))
            
        staff_user = next((s for s in database["staff"] if s['username'] == username and s['password'] == password), None)
        if staff_user:
            session['username'] = staff_user['username']
            session['role'] = 'staff'
            session['name'] = staff_user['name']
            return redirect(url_for('staff_dashboard'))
            
        error = "Invalid Username or Password!"
    return render_template('login.html', error=error, comp=database["company"])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN DASHBOARD ---
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    total_contract = sum(c['contract'] for c in database["cars"])
    total_received = sum(c['received'] for c in database["cars"])
    total_due = total_contract - total_received
    
    current_year_month = datetime.now().strftime('%Y-%m')
    total_exp = sum(e['amount'] for e in database["expenses"] if e['date'].startswith(current_year_month))

    current_month_str = datetime.now().strftime('%B %Y')

    return render_template('admin_dashboard.html', comp=database["company"],
                           cars=database["cars"], customers=database["customers"],
                           staff_list=database["staff"], total_contract=total_contract,
                           total_received=total_received, total_due=total_due, total_exp=total_exp,
                           current_month_str=current_month_str)

# --- VIEW ALL CUSTOMER PROFILES ---
@app.route('/admin/customers')
def view_customers():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    customer_profiles = []
    for cust in database["customers"]:
        c_cars = [c for c in database["cars"] if c['client_company'] == cust['company_name']]
        total_work = sum(c['contract'] for c in c_cars)
        total_paid = sum(c['received'] for c in c_cars)
        total_due = total_work - total_paid
        delivered_count = len([c for c in c_cars if c['status'] == 'Delivered'])
        
        customer_profiles.append({
            "info": cust,
            "cars": c_cars,
            "total_cars": len(c_cars),
            "delivered_cars": delivered_count,
            "total_due": total_due
        })
        
    return render_template('view_customers.html', comp=database["company"], customer_profiles=customer_profiles, staff_list=database["staff"])

# --- EDIT CUSTOMER PROFILE ---
@app.route('/admin/edit-customer/<int:cust_id>', methods=['GET', 'POST'])
def edit_customer(cust_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    cust = next((c for c in database["customers"] if c['id'] == cust_id), None)
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
                if car['client_company'] == old_company_name:
                    car['client_company'] = new_company_name
                    
        return redirect(url_for('view_customers'))
        
    return render_template('edit_customer.html', comp=database["company"], cust=cust)

# --- EDIT CAR DETAILS ---
@app.route('/admin/edit-car/<int:car_id>', methods=['GET', 'POST'])
def edit_car(car_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    car = next((c for c in database["cars"] if c['id'] == car_id), None)
    if not car:
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        car['contract'] = float(request.form.get('contract', car['contract']))
        
        new_received_payment = float(request.form.get('received', 0))
        payment_mode = request.form.get('payment_mode', 'increment')
        
        if payment_mode == 'increment':
            car['received'] = float(car.get('received', 0)) + new_received_payment
        else:
            car['received'] = new_received_payment

        car['status'] = request.form.get('status', car['status'])
        car['assigned_staff'] = request.form.get('assigned_staff', car.get('assigned_staff', ''))
        car['details'] = request.form.get('details', car['details'])
        car['receiving_date'] = request.form.get('receiving_date', car.get('receiving_date', ''))
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_dashboard.html', comp=database["company"], cars=database["cars"], staff_list=database["staff"])



# --- UPDATE CAR FROM DASHBOARD (Updated with Payment History & Date) ---
@app.route('/admin/update-car-dashboard/<int:car_id>', methods=['POST'])
def update_car_dashboard(car_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    car = next((c for c in database["cars"] if c['id'] == car_id), None)
    if car:
        car['contract'] = float(request.form.get('contract', car['contract']))
        
        additional_received = float(request.form.get('received', 0))
        payment_date = request.form.get('payment_date', datetime.now().strftime('%Y-%m-%d'))
        
        # যদি নতুন কোনো রিসিভ অ্যামাউন্ট দেওয়া হয় (যা ০ এর বেশি)
        if additional_received > 0:
            car['received'] = float(car.get('received', 0)) + additional_received
            
            # পেমেন্ট হিস্টোরিতে ডেটসহ সেভ করা হলো
            if 'payment_history' not in car:
                car['payment_history'] = []
            
            pay_id = len(car['payment_history']) + 1
            car['payment_history'].append({
                "id": pay_id,
                "amount": additional_received,
                "date": payment_date
            })

        car['status'] = request.form.get('status', car['status'])
        car['assigned_staff'] = request.form.get('assigned_staff', car.get('assigned_staff', ''))
        car['details'] = request.form.get('details', car['details'])
        
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
        
    return redirect(url_for('admin_dashboard'))

# --- DELETE/CORRECT SPECIFIC PAYMENT RECORD (New Route) ---
@app.route('/admin/delete-payment/<int:car_id>/<int:pay_id>', methods=['POST'])
def delete_payment_record(car_id, pay_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    car = next((c for c in database["cars"] if c['id'] == car_id), None)
    if car and 'payment_history' in car:
        # নির্দিষ্ট পেমেন্টটি খুঁজে বের করা
        target_payment = next((p for p in car['payment_history'] if p['id'] == pay_id), None)
        if target_payment:
            # মোট রিসিভ থেকে ভুল অ্যামাউন্টটি বিয়োগ করে দেওয়া
            car['received'] = max(0.0, float(car.get('received', 0)) - float(target_payment['amount']))
            # হিস্টোরি থেকে এটি রিমুভ করা
            car['payment_history'] = [p for p in car['payment_history'] if p['id'] != pay_id]
            
    return redirect(url_for('admin_dashboard'))




# --- DELETE CAR ROUTES ---
@app.route('/admin/delete-car/<int:car_id>', methods=['POST'])
def delete_car(car_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    database["cars"] = [c for c in database["cars"] if c['id'] != car_id]
    return redirect(url_for('view_customers'))

@app.route('/admin/delete-car-dashboard/<int:car_id>', methods=['POST'])
def delete_car_dashboard(car_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    database["cars"] = [c for c in database["cars"] if c['id'] != car_id]
    return redirect(url_for('admin_dashboard'))

# --- DELETE CUSTOMER ROUTE ---
@app.route('/admin/delete-customer/<int:cust_id>', methods=['POST'])
def delete_customer(cust_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    database["customers"] = [c for c in database["customers"] if c['id'] != cust_id]
    return redirect(url_for('view_customers'))

# --- VIEW ALL STAFF PROFILES ---
@app.route('/admin/staff')
def view_staff():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    staff_profiles = []
    for st in database["staff"]:
        s_cars = [c for c in database["cars"] if c.get('assigned_staff') == st['name']]
        in_progress = len([c for c in s_cars if c['status'] == 'In Progress'])
        completed = len([c for c in s_cars if c['status'] in ['Completed', 'Delivered']])
        
        staff_profiles.append({
            "info": st,
            "cars": s_cars,
            "in_progress": in_progress,
            "completed": completed,
            "total_assigned": len(s_cars)
        })
        
    return render_template('view_staff.html', comp=database["company"], staff_profiles=staff_profiles)

# --- EDIT STAFF PROFILE ---
@app.route('/admin/edit-staff/<int:staff_id>', methods=['GET', 'POST'])
def edit_staff(staff_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    st = next((s for s in database["staff"] if s['id'] == staff_id), None)
    if not st:
        return redirect(url_for('view_staff'))
        
    if request.method == 'POST':
        old_staff_name = st['name']
        new_staff_name = request.form.get('name')
        
        st['name'] = new_staff_name
        st['mobile'] = request.form.get('mobile')
        st['base_salary'] = float(request.form.get('base_salary', 0))
        st['leave_days'] = float(request.form.get('leave_days', 0))
        st['advance_balance'] = float(request.form.get('advance_balance', 0))
        st['joining_date'] = request.form.get('joining_date', st.get('joining_date', ''))
        
        if 'holiday_work_days' in request.form:
            st['holiday_work_days'] = float(request.form.get('holiday_work_days', 0))

        st['username'] = request.form.get('username')
        if request.form.get('password'):
            st['password'] = request.form.get('password')
            
        if old_staff_name != new_staff_name:
            for car in database["cars"]:
                if car.get('assigned_staff') == old_staff_name:
                    car['assigned_staff'] = new_staff_name
                    
        return redirect(url_for('view_staff'))
        
    return render_template('edit_staff.html', comp=database["company"], st=st)

# --- DELETE STAFF ROUTE ---
@app.route('/admin/delete-staff/<int:staff_id>', methods=['POST'])
def delete_staff(staff_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    database["staff"] = [s for s in database["staff"] if s['id'] != staff_id]
    return redirect(url_for('view_staff'))

# --- ADD CUSTOMER & STAFF ---
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
        new_id = max([c['id'] for c in database["customers"]], default=0) + 1
        database["customers"].append({"id": new_id, "company_name": comp_name, "owner_name": owner, "mobile": mobile, "address": address, "username": uname, "password": pwd})
        return redirect(url_for('view_customers'))
    return render_template('add_customer.html', comp=database["company"])

@app.route('/admin/add-staff', methods=['GET', 'POST'])
def add_staff():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        s_name = request.form.get('name')
        s_mobile = request.form.get('mobile')
        s_sal = float(request.form.get('base_salary', 0))
        joining_date = request.form.get('joining_date', datetime.now().strftime('%Y-%m-%d'))
        uname = request.form.get('username')
        pwd = request.form.get('password')
        new_id = max([s['id'] for s in database["staff"]], default=0) + 1
        database["staff"].append({
            "id": new_id, 
            "name": s_name, 
            "mobile": s_mobile, 
            "base_salary": s_sal, 
            "joining_date": joining_date, 
            "leave_days": 0, 
            "holiday_work_days": 0, 
            "advance_balance": 0.0,
            "leave_history": [], 
            "salary_history": [], 
            "username": uname, 
            "password": pwd
        })
        return redirect(url_for('view_staff'))
    return render_template('add_staff.html', comp=database["company"])

# --- DAILY EXPENSES MANAGEMENT ---
@app.route('/admin/expenses', methods=['GET', 'POST'])
def manage_expenses():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        date = request.form.get('date')
        item = request.form.get('item')
        amount = float(request.form.get('amount', 0))
        
        new_id = max([e['id'] for e in database["expenses"]], default=0) + 1
        database["expenses"].append({"id": new_id, "date": date, "item": item, "amount": amount})
        return redirect(url_for('manage_expenses'))
        
    current_year_month = datetime.now().strftime('%Y-%m')
    monthly_expenses = [e for e in database["expenses"] if e['date'].startswith(current_year_month)]
    total_monthly_exp = sum(e['amount'] for e in monthly_expenses)
    
    return render_template('expenses.html', comp=database["company"], expenses=database["expenses"], total_monthly_exp=total_monthly_exp, current_month=datetime.now().strftime('%B, %Y'), edit_exp=None)

# --- EDIT EXPENSE ROUTE ---
@app.route('/admin/edit-expense/<int:exp_id>', methods=['GET', 'POST'])
def edit_expense(exp_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    exp = next((e for e in database["expenses"] if e['id'] == exp_id), None)
    if not exp:
        return redirect(url_for('manage_expenses'))
        
    if request.method == 'POST':
        exp['date'] = request.form.get('date', exp['date'])
        exp['item'] = request.form.get('item', exp['item'])
        exp['amount'] = float(request.form.get('amount', exp['amount']))
        return redirect(url_for('manage_expenses'))
        
    current_year_month = datetime.now().strftime('%Y-%m')
    monthly_expenses = [e for e in database["expenses"] if e['date'].startswith(current_year_month)]
    total_monthly_exp = sum(e['amount'] for e in monthly_expenses)
    
    return render_template('expenses.html', comp=database["company"], expenses=database["expenses"], 
                           total_monthly_exp=total_monthly_exp, current_month=datetime.now().strftime('%B, %Y'), edit_exp=exp)

@app.route('/admin/delete-expense/<int:exp_id>', methods=['POST'])
def delete_expense(exp_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    database["expenses"] = [e for e in database["expenses"] if e['id'] != exp_id]
    return redirect(url_for('manage_expenses'))

# --- RECEIVE CAR ---
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
        contract = float(request.form.get('contract', 0))
        received = float(request.form.get('received', 0))
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
                
        new_id = max([c['id'] for c in database["cars"]], default=0) + 1
        database["cars"].append({
            "id": new_id, "car_name": car_name, "chassis": chassis, 
            "color_name": color_name, "color_code": color_code, 
            "client_company": client_company, "contract": contract, 
            "received": received, "details": details, 
            "receiving_date": receiving_date, 
            "before_images": saved_before, "after_images": saved_after, 
            "status": status, "assigned_staff": assigned_staff
        })
        return redirect(url_for('admin_dashboard'))
    return render_template('receive_car.html', comp=database["company"], customers=database["customers"], staff_list=database["staff"])

# --- CUSTOMER INVOICE ROUTE ---
@app.route('/customer/invoice/<int:car_id>')
def customer_invoice(car_id):
    if 'role' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
    
    car = next((c for c in database["cars"] if c['id'] == car_id), None)
    if not car:
        return "Car not found", 404
        
    if car['client_company'] != session['name']:
        return "Unauthorized Access", 403
        
    comp = database["company"]
    cust = next((cust for cust in database["customers"] if cust['company_name'] == car['client_company']), None)
    
    return render_template('invoice.html', car=car, comp=comp, cust=cust)

# --- CUSTOMER PORTAL ---
@app.route('/customer/dashboard', methods=['GET', 'POST'])
def customer_dashboard():
    if 'role' not in session or session['role'] != 'customer':
        return redirect(url_for('login'))
        
    cust = next((c for c in database["customers"] if c['username'] == session['username']), None)
    client_company = cust['company_name'] if cust else session['name']
    customer_cars = [c for c in database["cars"] if c['client_company'] == client_company]
    
    total_contract = sum(c['contract'] for c in customer_cars)
    total_paid = sum(c['received'] for c in customer_cars)
    total_due = total_contract - total_paid
    
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    
    monthly_cars = []
    monthly_paid = 0
    monthly_due = 0
    
    for c in customer_cars:
        d_date = c.get('delivery_date', '')
        if d_date and d_date.startswith(selected_month):
            monthly_cars.append(c)
            monthly_paid += c.get('received', 0)
            
    monthly_contract = sum(c['contract'] for c in monthly_cars)
    monthly_due_calc = monthly_contract - monthly_paid
    
    return render_template('customer_dashboard.html', 
                           comp=database["company"], 
                           cars=customer_cars, 
                           monthly_cars=monthly_cars,
                           total_contract=total_contract, 
                           total_paid=total_paid, 
                           total_due=total_due, 
                           cust=cust,
                           selected_month=selected_month,
                           monthly_contract=monthly_contract,
                           monthly_paid=monthly_paid,
                           monthly_due=monthly_due_calc)

# --- STAFF DASHBOARD ---
@app.route('/staff/dashboard')
def staff_dashboard():
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('login'))
    
    staff_name = session['name']
    
    current_staff = next((s for s in database["staff"] if s['name'].strip().lower() == staff_name.strip().lower()), {
        "base_salary": 0, "leave_days": 0, "holiday_work_days": 0, "advance_balance": 0.0, "name": staff_name, "salary_history": []
    })
    
    actual_staff_name = current_staff.get('name', staff_name)
    assigned_cars = [c for c in database["cars"] if str(c.get('assigned_staff', '')).strip().lower() == actual_staff_name.strip().lower()]
    
    in_progress_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() in ['in progress', 'processing']]
    completed_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() in ['completed', 'delivered']]
    queue_cars = [c for c in assigned_cars if str(c.get('status', '')).strip().lower() in ['pending', 'waiting', 'in queue', 'queue']]
    
    base_salary = float(current_staff.get('base_salary', 0))
    leave_days = float(current_staff.get('leave_days', 0))
    holiday_work_days = float(current_staff.get('holiday_work_days', 0))
    advance_balance = float(current_staff.get('advance_balance', 0.0))
    
    per_day_salary = base_salary / 26 if base_salary > 0 else 0
    deduction_amount = leave_days * per_day_salary
    holiday_bonus = holiday_work_days * per_day_salary
    
    net_salary = base_salary - deduction_amount + holiday_bonus - advance_balance
    
    return render_template('staff_dashboard.html', 
                           comp=database["company"], 
                           staff=current_staff,
                           cars=assigned_cars,
                           in_progress_cars=in_progress_cars,
                           completed_cars=completed_cars,
                           queue_cars=queue_cars,
                           completed_count=len(completed_cars),
                           in_progress_count=len(in_progress_cars),
                           per_day_salary=round(per_day_salary, 2),
                           holiday_bonus=round(holiday_bonus, 2),
                           net_salary=round(net_salary, 2),
                           staff_name=actual_staff_name)

# --- ADMIN ATTENDANCE ---
@app.route('/admin/attendance', methods=['GET', 'POST'])
def admin_attendance():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        absent_staff_ids = request.form.getlist('absent_staff')
        absent_staff_ids = [int(sid) for sid in absent_staff_ids]
        leave_date = request.form.get('leave_date', datetime.now().strftime('%Y-%m-%d'))
        reason = request.form.get('reason', 'Casual Leave / Absent')
        
        for st in database["staff"]:
            if 'leave_history' not in st:
                st['leave_history'] = []
                
            h_work = request.form.get(f'holiday_work_{st["id"]}')
            if h_work is not None:
                try:
                    st['holiday_work_days'] = float(h_work)
                except ValueError:
                    pass
                
            if st['id'] in absent_staff_ids:
                st['leave_days'] = float(st.get('leave_days', 0)) + 1.0
                st['leave_history'].append({
                    "date": leave_date,
                    "reason": reason
                })
                
        return redirect(url_for('admin_attendance'))
        
    return render_template('attendance.html', comp=database["company"], staff_list=database["staff"], today_date=datetime.now().strftime('%Y-%m-%d'))

# --- MONTHLY SALARY ARCHIVE ---
@app.route('/admin/close-monthly-salary', methods=['POST'])
def close_monthly_salary():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    target_month = request.form.get('target_month')
    if not target_month:
        target_month = datetime.now().strftime('%B %Y')
    
    for st in database["staff"]:
        if 'salary_history' not in st:
            st['salary_history'] = []
            
        base_sal = float(st.get('base_salary', 0))
        l_days = float(st.get('leave_days', 0))
        h_work = float(st.get('holiday_work_days', 0))
        adv_bal = float(st.get('advance_balance', 0.0))
        
        per_day = base_sal / 26 if base_sal > 0 else 0
        net_sal = base_sal - (l_days * per_day) + (h_work * per_day) - adv_bal
        
        record_id = len(st['salary_history']) + 1

        st['salary_history'].append({
            "id": record_id,
            "month": target_month,
            "base_salary": base_sal,
            "leave_days": l_days,
            "holiday_work_days": h_work,
            "advance_balance": adv_bal,
            "net_salary": round(net_sal, 2),
            "status": "Unpaid"
        })
        
        st['leave_days'] = 0.0
        st['holiday_work_days'] = 0.0
        st['advance_balance'] = 0.0
        st['leave_history'] = [] 
        
    return redirect(url_for('admin_dashboard'))

# --- TOGGLE SALARY STATUS ---
@app.route('/admin/toggle-salary-status/<string:staff_name>/<int:record_id>', methods=['POST'])
def toggle_salary_status(staff_name, record_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    st = next((s for s in database["staff"] if s['name'].strip().lower() == staff_name.strip().lower()), None)
    if st and 'salary_history' in st:
        for record in st['salary_history']:
            if record.get('id') == record_id:
                current_status = record.get('status', 'Unpaid')
                record['status'] = 'Paid' if current_status == 'Unpaid' else 'Unpaid'
                break
                
    return redirect(request.referrer or url_for('admin_dashboard'))

# --- STAFF LEAVE HISTORY ---
@app.route('/staff/leave-history')
def staff_leave_history():
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('login'))
    
    staff_name = session['name']
    current_staff = next((s for s in database["staff"] if s['name'].strip().lower() == staff_name.strip().lower()), None)
    
    if not current_staff:
        return "Staff not found", 404
        
    if 'leave_history' not in current_staff:
        current_staff['leave_history'] = []
        
    return render_template('staff_leave_history.html', comp=database["company"], staff=current_staff)

# --- STAFF PAST SALARY HISTORY ---
@app.route('/staff/salary-history')
def staff_salary_history():
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('login'))
    
    staff_name = session['name']
    current_staff = next((s for s in database["staff"] if s['name'].strip().lower() == staff_name.strip().lower()), None)
    
    if not current_staff:
        return "Staff not found", 404
        
    if 'salary_history' not in current_staff:
        current_staff['salary_history'] = []
        
    return render_template('staff_salary_history.html', comp=database["company"], staff=current_staff)

# --- STAFF CAR WORK HISTORY ---
@app.route('/staff/work-history')
def staff_work_history():
    if 'role' not in session or session['role'] != 'staff':
        return redirect(url_for('login'))
    
    staff_name = session['name']
    current_staff = next((s for s in database["staff"] if s['name'].strip().lower() == staff_name.strip().lower()), {
        "name": staff_name
    })
    
    actual_staff_name = current_staff.get('name', staff_name)
    assigned_cars = [c for c in database["cars"] if str(c.get('assigned_staff', '')).strip().lower() == actual_staff_name.strip().lower()]
    
    return render_template('staff_work_history.html', 
                           comp=database["company"], 
                           staff=current_staff,
                           cars=assigned_cars)

if __name__ == '__main__':
    app.run(debug=True, port=5000)