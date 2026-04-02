from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import datetime, date
from functools import wraps
import pandas as pd
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sincet-digital-leave-2025-secure')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
DATABASE = os.path.join(os.path.dirname(__file__), 'database.db')

DEFAULT_PRINCIPAL_ACCOUNT = {
    'username': 'principal',
    'password': 'sincet@2025',
    'name': 'SINCET Principal'
}

DEFAULT_ADMIN_ACCOUNTS = [
    {'username': 'admin_cse', 'password': 'cse@2025', 'department': 'CSE', 'name': 'CSE HOD'},
    {'username': 'admin_ece', 'password': 'ece@2025', 'department': 'ECE', 'name': 'ECE HOD'},
    {'username': 'admin_it', 'password': 'it@2025', 'department': 'IT', 'name': 'IT HOD'},
    {'username': 'admin_aids', 'password': 'aids@2025', 'department': 'AIDS', 'name': 'AIDS HOD'},
    {'username': 'admin_aiml', 'password': 'aiml@2025', 'department': 'AIML', 'name': 'AIML HOD'},
    {'username': 'admin_mech', 'password': 'mech@2025', 'department': 'MECH', 'name': 'MECH HOD'},
    {'username': 'admin_agri', 'password': 'agri@2025', 'department': 'AGRI', 'name': 'AGRI HOD'}
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def upsert_user_credential(db, username, password, role, department=None, display_name=None, source_student_id=None):
    db.execute('''INSERT INTO user_credentials
                 (username, password, role, department, display_name, source_student_id, updated_at)
                 VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                 ON CONFLICT(username) DO UPDATE SET
                    password = excluded.password,
                    role = excluded.role,
                    department = excluded.department,
                    display_name = excluded.display_name,
                    source_student_id = excluded.source_student_id,
                    updated_at = CURRENT_TIMESTAMP''',
              (username, password, role, department, display_name, source_student_id))

def sync_core_credentials(db):
    upsert_user_credential(
        db,
        DEFAULT_PRINCIPAL_ACCOUNT['username'],
        DEFAULT_PRINCIPAL_ACCOUNT['password'],
        'principal',
        'ALL',
        DEFAULT_PRINCIPAL_ACCOUNT['name'],
        None
    )

    for account in DEFAULT_ADMIN_ACCOUNTS:
        upsert_user_credential(
            db,
            account['username'],
            account['password'],
            'admin',
            account['department'],
            account['name'],
            None
        )

def sync_student_credentials(db, student_id=None):
    if student_id:
        students = db.execute('''SELECT student_id, password, department, name
                                 FROM students
                                 WHERE LOWER(student_id) = ?''',
                              (student_id.lower(),)).fetchall()
    else:
        students = db.execute('SELECT student_id, password, department, name FROM students').fetchall()

    for student in students:
        upsert_user_credential(
            db,
            student['student_id'],
            student['password'],
            'student',
            student['department'],
            student['name'],
            student['student_id']
        )

def normalize_session_type(raw_session):
    session = (raw_session or '').strip().upper()
    mapping = {
        'FULL': 'BOTH',
        'FULLDAY': 'BOTH',
        'MORNING': 'FN',
        'FORENOON': 'FN',
        'HALF': 'FN',
        'AFTERNOON': 'AN'
    }
    session = mapping.get(session, session)
    return session if session in ['FN', 'AN', 'BOTH'] else 'BOTH'

def is_likely_valid_signature(signature):
    return bool(signature) and len(signature.strip()) >= 300

def passwords_match(input_password, stored_password, role):
    raw_input = (input_password or '').strip()
    raw_stored = (stored_password or '').strip()
    if not raw_input or not raw_stored:
        return False

    if raw_input == raw_stored:
        return True

    # Admin users often type "2" instead of "@" on some keyboard layouts.
    if role in ['admin', 'principal']:
        equivalents = {
            raw_stored,
            raw_stored.replace('@', '2'),
            raw_stored.replace('@', ''),
            raw_stored.replace('@', 'at')
        }
        return raw_input.lower() in {value.lower() for value in equivalents}

    return False

def init_db():
    with app.app_context():
        db = get_db()

        # Principal Table (Super Admin)
        db.execute('''CREATE TABLE IF NOT EXISTS principal (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Admins Table
        db.execute('''CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            department TEXT NOT NULL,
            name TEXT DEFAULT 'Admin',
            created_by TEXT DEFAULT 'system',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Students Table
        db.execute('''CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            register_number TEXT UNIQUE NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            parent_name TEXT NOT NULL,
            parent_phone TEXT NOT NULL,
            address TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Leave Applications Table
        db.execute('''CREATE TABLE IF NOT EXISTS leave_applications (
            id INTEGER PRIMARY KEY,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            register_number TEXT NOT NULL,
            department TEXT NOT NULL,
            year TEXT NOT NULL,
            reason TEXT NOT NULL,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            num_days REAL NOT NULL,
            session_type TEXT NOT NULL,
            days_already_taken INTEGER DEFAULT 0,
            student_signature TEXT,
            parent_signature TEXT,
            status TEXT DEFAULT 'pending',
            admin_remarks TEXT,
            applied_time TEXT DEFAULT CURRENT_TIMESTAMP,
            processed_time TEXT,
            processed_by TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )''')

        # Unified Credentials Table
        db.execute('''CREATE TABLE IF NOT EXISTS user_credentials (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT,
            display_name TEXT,
            source_student_id TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Ensure default principal credentials stay valid even on existing databases.
        db.execute('''INSERT OR IGNORE INTO principal (username, password, name)
                     VALUES (?, ?, ?)''',
                  (DEFAULT_PRINCIPAL_ACCOUNT['username'],
                   DEFAULT_PRINCIPAL_ACCOUNT['password'],
                   DEFAULT_PRINCIPAL_ACCOUNT['name']))
        db.execute('''UPDATE principal
                     SET password = ?, name = ?
                     WHERE LOWER(username) = ?''',
                  (DEFAULT_PRINCIPAL_ACCOUNT['password'],
                   DEFAULT_PRINCIPAL_ACCOUNT['name'],
                   DEFAULT_PRINCIPAL_ACCOUNT['username']))

        # Ensure department admin IDs/passwords are always synchronized.
        for account in DEFAULT_ADMIN_ACCOUNTS:
            db.execute('''INSERT OR IGNORE INTO admins (username, password, department, name, created_by)
                         VALUES (?, ?, ?, ?, ?)''',
                      (account['username'], account['password'], account['department'], account['name'], 'system'))
            db.execute('''UPDATE admins
                         SET password = ?, department = ?, name = ?
                         WHERE LOWER(username) = ?''',
                      (account['password'], account['department'], account['name'], account['username']))

        sync_core_credentials(db)
        sync_student_credentials(db)

        db.commit()

init_db()

# Decorators
def principal_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'principal':
            flash('Principal access required', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') not in ['admin', 'principal']:
            flash('Admin access required', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Student access required', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'role' in session:
        if session['role'] == 'principal':
            return redirect(url_for('principal_dashboard'))
        elif session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    admin_login_ids = [
        {'department': account['department'], 'username': account['username'], 'password': account['password']}
        for account in DEFAULT_ADMIN_ACCOUNTS
    ]

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        login_type = request.form.get('login_type', 'admin')

        if not username or not password:
            flash('Username and password required', 'error')
            return render_template('login.html',
                                   admin_login_ids=admin_login_ids,
                                   principal_login=DEFAULT_PRINCIPAL_ACCOUNT)

        db = get_db()
        sync_core_credentials(db)
        sync_student_credentials(db)
        db.commit()

        if login_type == 'admin':
            username = username.lower()

            admin_credential = db.execute('''SELECT * FROM user_credentials
                                            WHERE LOWER(username) = ?
                                              AND role IN ('principal', 'admin')''',
                                         (username,)).fetchone()

            if admin_credential and passwords_match(password, admin_credential['password'], admin_credential['role']) and admin_credential['role'] == 'principal':
                principal = db.execute('SELECT * FROM principal WHERE LOWER(username) = ?',
                                      (username,)).fetchone()
                session['user_id'] = principal['id']
                session['role'] = 'principal'
                session['username'] = principal['username']
                session['name'] = principal['name']
                session['department'] = 'ALL'
                flash('Welcome, Principal!', 'success')
                return redirect(url_for('principal_dashboard'))

            if admin_credential and passwords_match(password, admin_credential['password'], admin_credential['role']) and admin_credential['role'] == 'admin':
                admin = db.execute('SELECT * FROM admins WHERE LOWER(username) = ?',
                                  (username,)).fetchone()
                session['user_id'] = admin['id']
                session['role'] = 'admin'
                session['department'] = admin['department']
                session['username'] = admin['username']
                session['name'] = admin['name'] if admin['name'] else admin['department'] + ' Admin'
                flash('Welcome, ' + admin['department'] + ' Admin!', 'success')
                return redirect(url_for('admin_dashboard'))

            flash('Invalid admin credentials. Use department admin ID and password.', 'error')

        else:
            # Student login
            student_credential = db.execute('''SELECT * FROM user_credentials
                                              WHERE LOWER(username) = ? AND role = 'student' ''',
                                           (username.lower(),)).fetchone()
            if student_credential and passwords_match(password, student_credential['password'], student_credential['role']):
                student = db.execute('SELECT * FROM students WHERE LOWER(student_id) = ?',
                                    (username.lower(),)).fetchone()
                session['user_id'] = student['id']
                session['role'] = 'student'
                session['student_id'] = student['student_id']
                session['student_name'] = student['name']
                session['department'] = student['department']
                flash('Welcome, ' + student['name'] + '!', 'success')
                return redirect(url_for('student_dashboard'))

            flash('Invalid student credentials', 'error')

        return render_template('login.html',
                               admin_login_ids=admin_login_ids,
                               principal_login=DEFAULT_PRINCIPAL_ACCOUNT)

    return render_template('login.html',
                           admin_login_ids=admin_login_ids,
                           principal_login=DEFAULT_PRINCIPAL_ACCOUNT)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# ==================== PRINCIPAL ROUTES ====================

@app.route('/principal/dashboard')
@principal_required
def principal_dashboard():
    db = get_db()

    # Get all departments stats
    departments = ['CSE', 'ECE', 'IT', 'AIDS', 'AIML', 'MECH', 'AGRI']
    dept_stats = []

    for dept in departments:
        stats = {
            'name': dept,
            'students': db.execute('SELECT COUNT(*) as count FROM students WHERE department = ?', (dept,)).fetchone()['count'],
            'pending': db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "pending"', (dept,)).fetchone()['count'],
            'approved': db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "approved"', (dept,)).fetchone()['count'],
            'rejected': db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "rejected"', (dept,)).fetchone()['count']
        }
        dept_stats.append(stats)

    total_students = db.execute('SELECT COUNT(*) as count FROM students').fetchone()['count']
    total_pending = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE status = "pending"').fetchone()['count']
    total_approved = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE status = "approved"').fetchone()['count']
    total_admins = db.execute('SELECT COUNT(*) as count FROM admins').fetchone()['count']

    admins = db.execute('SELECT * FROM admins ORDER BY department').fetchall()

    recent_leaves = db.execute('''SELECT * FROM leave_applications
                                 ORDER BY applied_time DESC LIMIT 10''').fetchall()

    return render_template('principal_dashboard.html',
                          dept_stats=dept_stats,
                          total_students=total_students,
                          total_pending=total_pending,
                          total_approved=total_approved,
                          total_admins=total_admins,
                          admins=admins,
                          recent_leaves=recent_leaves)

@app.route('/principal/create_admin', methods=['GET', 'POST'])
@principal_required
def create_admin():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        department = request.form.get('department', '').strip().upper()
        name = request.form.get('name', '').strip()

        if not all([username, password, department, name]):
            flash('All fields are required', 'error')
            return render_template('create_admin.html')

        db = get_db()

        # Check if username exists
        existing = db.execute('SELECT id FROM admins WHERE username = ?', (username,)).fetchone()
        if existing:
            flash('Username already exists', 'error')
            return render_template('create_admin.html')

        try:
            db.execute('''INSERT INTO admins (username, password, department, name, created_by)
                         VALUES (?, ?, ?, ?, ?)''',
                      (username, password, department, name, session['username']))
            db.commit()
            flash(f'Admin account created successfully for {department}!', 'success')
            return redirect(url_for('principal_dashboard'))
        except Exception as e:
            flash('Error creating admin account', 'error')

    return render_template('create_admin.html')

@app.route('/principal/delete_admin/<int:admin_id>', methods=['POST'])
@principal_required
def delete_admin(admin_id):
    db = get_db()
    admin = db.execute('SELECT * FROM admins WHERE id = ?', (admin_id,)).fetchone()

    if admin:
        db.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
        db.commit()
        flash(f'Admin {admin["username"]} deleted', 'success')
    else:
        flash('Admin not found', 'error')

    return redirect(url_for('principal_dashboard'))

@app.route('/principal/all_leaves')
@principal_required
def principal_all_leaves():
    db = get_db()
    department = request.args.get('department', 'all')
    status = request.args.get('status', 'all')

    query = 'SELECT * FROM leave_applications WHERE 1=1'
    params = []

    if department != 'all':
        query += ' AND department = ?'
        params.append(department)

    if status != 'all':
        query += ' AND status = ?'
        params.append(status)

    query += ' ORDER BY applied_time DESC'

    leaves = db.execute(query, params).fetchall()

    return render_template('principal_leaves.html', leaves=leaves, department=department, status=status)

@app.route('/principal/all_students')
@principal_required
def principal_all_students():
    db = get_db()
    department = request.args.get('department', 'all')
    year = request.args.get('year', 'all')

    query = 'SELECT * FROM students WHERE 1=1'
    params = []

    if department != 'all':
        query += ' AND department = ?'
        params.append(department)

    if year != 'all':
        query += ' AND year = ?'
        params.append(year)

    query += ' ORDER BY department, year, name'

    students = db.execute(query, params).fetchall()

    return render_template('principal_students.html', students=students, department=department, year=year)

# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()

    if session.get('role') == 'principal':
        dept = request.args.get('department', 'CSE')
    else:
        dept = session['department']

    total_students = db.execute('SELECT COUNT(*) as count FROM students WHERE department = ?',
                               (dept,)).fetchone()['count']
    pending_leaves = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "pending"',
                               (dept,)).fetchone()['count']
    approved_leaves = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "approved"',
                                (dept,)).fetchone()['count']
    rejected_leaves = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "rejected"',
                                (dept,)).fetchone()['count']

    recent_leaves = db.execute('''SELECT * FROM leave_applications
                                 WHERE department = ?
                                 ORDER BY applied_time DESC LIMIT 5''',
                              (dept,)).fetchall()

    return render_template('admin_dashboard.html',
                          total_students=total_students,
                          pending_leaves=pending_leaves,
                          approved_leaves=approved_leaves,
                          rejected_leaves=rejected_leaves,
                          recent_leaves=recent_leaves)

@app.route('/admin/students')
@admin_required
def admin_students():
    dept = session['department']
    year = request.args.get('year', 'all')
    db = get_db()

    if session.get('role') == 'principal':
        dept = request.args.get('department', 'CSE')

    if year == 'all':
        students = db.execute('SELECT * FROM students WHERE department = ? ORDER BY year, name',
                             (dept,)).fetchall()
    else:
        students = db.execute('SELECT * FROM students WHERE department = ? AND year = ? ORDER BY name',
                             (dept, year)).fetchall()

    return render_template('admin_students.html', students=students, year=year)

@app.route('/admin/student/<student_id>')
@admin_required
def admin_student_profile(student_id):
    db = get_db()

    if session.get('role') == 'principal':
        student = db.execute('SELECT * FROM students WHERE student_id = ?',
                            (student_id,)).fetchone()
    else:
        dept = session['department']
        student = db.execute('SELECT * FROM students WHERE student_id = ? AND department = ?',
                            (student_id, dept)).fetchone()

    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('admin_students'))

    leaves = db.execute('SELECT * FROM leave_applications WHERE student_id = ? ORDER BY applied_time DESC',
                       (student_id,)).fetchall()

    total_used = sum(leave['num_days'] for leave in leaves if leave['status'] == 'approved')
    total_approved = len([l for l in leaves if l['status'] == 'approved'])
    total_rejected = len([l for l in leaves if l['status'] == 'rejected'])
    total_pending = len([l for l in leaves if l['status'] == 'pending'])

    return render_template('admin_student_profile.html',
                          student=student,
                          leaves=leaves,
                          total_used=total_used,
                          total_approved=total_approved,
                          total_rejected=total_rejected,
                          total_pending=total_pending)

@app.route('/admin/add_student', methods=['GET', 'POST'])
@admin_required
def add_student():
    dept = session['department']

    if session.get('role') == 'principal':
        dept = request.form.get('department', request.args.get('department', 'CSE'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        register_number = request.form.get('register_number', '').strip()
        year = request.form.get('year', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        parent_phone = request.form.get('parent_phone', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, register_number, year, email, phone, parent_name, parent_phone, address]):
            flash('All fields are required', 'error')
            return render_template('add_student.html')

        db = get_db()

        existing = db.execute('SELECT id FROM students WHERE register_number = ?',
                             (register_number,)).fetchone()
        if existing:
            flash('Register number already exists', 'error')
            return render_template('add_student.html')

        dept_prefix = {'CSE': 'cse', 'ECE': 'ece', 'IT': 'it', 'AIDS': 'aids', 'AIML': 'aiml', 'MECH': 'mech', 'AGRI': 'agri'}.get(dept, 'std')
        count = db.execute('SELECT COUNT(*) as count FROM students WHERE department = ?',
                          (dept,)).fetchone()['count']
        student_id = f'{dept_prefix}{10000 + count + 1}'

        password = register_number[-6:] if len(register_number) >= 6 else register_number

        try:
            db.execute('''INSERT INTO students
                         (student_id, name, register_number, department, year,
                          email, phone, parent_name, parent_phone, address, password)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (student_id, name, register_number, dept, year,
                       email, phone, parent_name, parent_phone, address, password))
            sync_student_credentials(db, student_id)
            db.commit()

            flash(f'Student added successfully! ID: {student_id}', 'success')
            return redirect(url_for('admin_students'))
        except Exception as e:
            flash('Error adding student', 'error')

    return render_template('add_student.html')

@app.route('/admin/bulk_import', methods=['GET', 'POST'])
@admin_required
def bulk_import():
    dept = session['department']

    if session.get('role') == 'principal':
        dept = request.form.get('department', request.args.get('department', 'CSE'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return render_template('bulk_import.html')

        file = request.files['file']

        if file.filename == '':
            flash('No file selected', 'error')
            return render_template('bulk_import.html')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                df = pd.read_excel(filepath)

                required_cols = ['name', 'register_number', 'year']
                df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')

                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    flash(f'Missing columns: {", ".join(missing_cols)}', 'error')
                    os.remove(filepath)
                    return render_template('bulk_import.html')

                db = get_db()
                success_count = 0
                error_count = 0

                for index, row in df.iterrows():
                    try:
                        name = str(row['name']).strip()
                        register_number = str(row['register_number']).strip()
                        year_raw = str(row['year']).strip()
                        year = normalize_year(year_raw)

                        student_dept = dept
                        if 'department' in df.columns or 'dept' in df.columns:
                            col_name = 'department' if 'department' in df.columns else 'dept'
                            if pd.notna(row.get(col_name)):
                                student_dept = str(row[col_name]).strip().upper()

                        email = f'{register_number}@student.edu'
                        phone = '0000000000'
                        parent_name = 'Parent'
                        parent_phone = '0000000000'
                        address = 'Not Provided'

                        if 'email' in df.columns and pd.notna(row.get('email')):
                            email = str(row['email']).strip()
                        if 'phone' in df.columns and pd.notna(row.get('phone')):
                            phone = str(row['phone']).strip()

                        existing = db.execute('SELECT id FROM students WHERE register_number = ?',
                                            (register_number,)).fetchone()
                        if existing:
                            error_count += 1
                            continue

                        dept_prefix = {'CSE': 'cse', 'ECE': 'ece', 'IT': 'it', 'AIDS': 'aids'}.get(student_dept, 'std')
                        count = db.execute('SELECT COUNT(*) as count FROM students WHERE department = ?',
                                          (student_dept,)).fetchone()['count']
                        student_id = f'{dept_prefix}{10000 + count + 1}'
                        password = register_number[-6:] if len(register_number) >= 6 else register_number

                        db.execute('''INSERT INTO students
                                     (student_id, name, register_number, department, year,
                                      email, phone, parent_name, parent_phone, address, password)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                  (student_id, name, register_number, student_dept, year,
                                   email, phone, parent_name, parent_phone, address, password))
                        sync_student_credentials(db, student_id)
                        success_count += 1

                    except Exception:
                        error_count += 1

                db.commit()
                os.remove(filepath)

                if success_count > 0:
                    flash(f'Successfully imported {success_count} students!', 'success')
                if error_count > 0:
                    flash(f'{error_count} records skipped (duplicates or errors)', 'error')

                return redirect(url_for('admin_students'))

            except Exception as e:
                flash('Error processing file', 'error')
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            flash('Invalid file type. Please upload Excel file (.xlsx or .xls)', 'error')

    return render_template('bulk_import.html')

def normalize_year(year_str):
    year_str = str(year_str).lower().strip()
    if '1' in year_str or 'first' in year_str:
        return '1st Year'
    elif '2' in year_str or 'second' in year_str:
        return '2nd Year'
    elif '3' in year_str or 'third' in year_str:
        return '3rd Year'
    elif '4' in year_str or 'fourth' in year_str:
        return '4th Year'
    return '1st Year'

@app.route('/admin/user_credentials')
@admin_required
def user_credentials():
    dept = session['department']
    db = get_db()
    year_filter = request.args.get('year', 'all')

    if session.get('role') == 'principal':
        dept = request.args.get('department', 'CSE')

    if year_filter == 'all':
        students = db.execute('''SELECT student_id, name, register_number, year, password, department
                                FROM students WHERE department = ? ORDER BY year, name''',
                             (dept,)).fetchall()
    else:
        students = db.execute('''SELECT student_id, name, register_number, year, password, department
                                FROM students WHERE department = ? AND year = ? ORDER BY name''',
                             (dept, year_filter)).fetchall()

    students_by_year = {}
    for student in students:
        year = student['year']
        if year not in students_by_year:
            students_by_year[year] = []
        students_by_year[year].append(student)

    year_order = ['1st Year', '2nd Year', '3rd Year', '4th Year']
    sorted_years = sorted(students_by_year.keys(), key=lambda x: year_order.index(x) if x in year_order else 99)

    return render_template('user_credentials.html',
                          students=students,
                          students_by_year=students_by_year,
                          sorted_years=sorted_years,
                          year_filter=year_filter)

@app.route('/admin/reset_password/<student_id>', methods=['POST'])
@admin_required
def reset_password(student_id):
    db = get_db()

    if session.get('role') == 'principal':
        student = db.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    else:
        dept = session['department']
        student = db.execute('SELECT * FROM students WHERE student_id = ? AND department = ?',
                            (student_id, dept)).fetchone()

    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('user_credentials'))

    new_password = student['register_number'][-6:]
    db.execute('UPDATE students SET password = ? WHERE student_id = ?', (new_password, student_id))
    sync_student_credentials(db, student_id)
    db.commit()

    flash(f'Password reset for {student["name"]}', 'success')
    return redirect(url_for('user_credentials'))

@app.route('/admin/delete_student/<student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    db = get_db()

    if session.get('role') == 'principal':
        student = db.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    else:
        dept = session['department']
        student = db.execute('SELECT * FROM students WHERE student_id = ? AND department = ?',
                            (student_id, dept)).fetchone()

    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('admin_students'))

    deleted_leave_count = db.execute('SELECT COUNT(*) AS count FROM leave_applications WHERE student_id = ?',
                                    (student_id,)).fetchone()['count']

    db.execute('DELETE FROM leave_applications WHERE student_id = ?', (student_id,))
    db.execute('DELETE FROM user_credentials WHERE LOWER(username) = ?', (student_id.lower(),))
    db.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
    db.commit()

    flash(f"Deleted {student['name']} ({student_id}) and removed {deleted_leave_count} related leave record(s)", 'success')

    next_page = request.form.get('next_page', 'students')
    if next_page == 'credentials':
        return redirect(url_for('user_credentials'))
    if next_page == 'profile':
        return redirect(url_for('admin_students'))
    return redirect(url_for('admin_students'))

@app.route('/admin/leave_approvals')
@admin_required
def admin_leave_approvals():
    db = get_db()
    status = request.args.get('status', 'pending')

    if session.get('role') == 'principal':
        dept = request.args.get('department', None)
        if dept:
            leaves = db.execute('''SELECT * FROM leave_applications
                                  WHERE department = ? AND status = ?
                                  ORDER BY applied_time DESC''', (dept, status)).fetchall()
        else:
            leaves = db.execute('''SELECT * FROM leave_applications
                                  WHERE status = ?
                                  ORDER BY applied_time DESC''', (status,)).fetchall()
    else:
        dept = session['department']
        leaves = db.execute('''SELECT * FROM leave_applications
                              WHERE department = ? AND status = ?
                              ORDER BY applied_time DESC''', (dept, status)).fetchall()

    return render_template('admin_leave_approvals.html', leaves=leaves, status=status)

@app.route('/admin/leave/<int:leave_id>', methods=['GET', 'POST'])
@admin_required
def admin_leave_detail(leave_id):
    db = get_db()

    if session.get('role') == 'principal':
        leave = db.execute('SELECT * FROM leave_applications WHERE id = ?', (leave_id,)).fetchone()
    else:
        dept = session['department']
        leave = db.execute('SELECT * FROM leave_applications WHERE id = ? AND department = ?',
                          (leave_id, dept)).fetchone()

    if not leave:
        flash('Leave request not found', 'error')
        return redirect(url_for('admin_leave_approvals'))

    if request.method == 'POST':
        if leave['status'] != 'pending':
            flash('This leave request has already been processed', 'error')
            return render_template('admin_leave_detail.html', leave=leave)

        action = request.form.get('action', '').strip()
        remarks = request.form.get('remarks', '').strip()

        if action not in ['approve', 'reject']:
            flash('Invalid action', 'error')
            return render_template('admin_leave_detail.html', leave=leave)

        status = 'approved' if action == 'approve' else 'rejected'
        processed_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        db.execute('''UPDATE leave_applications
                     SET status = ?, admin_remarks = ?, processed_time = ?, processed_by = ?
                     WHERE id = ?''',
                  (status, remarks, processed_time, session.get('name', session['username']), leave_id))
        db.commit()

        flash(f'Leave {status} successfully', 'success')
        return redirect(url_for('admin_leave_approvals'))

    return render_template('admin_leave_detail.html', leave=leave)

# ==================== STUDENT ROUTES ====================

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    student_id = session['student_id']
    db = get_db()

    student = db.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    leaves = db.execute('SELECT * FROM leave_applications WHERE student_id = ?', (student_id,)).fetchall()

    total_used = sum(leave['num_days'] for leave in leaves if leave['status'] == 'approved')
    pending = len([l for l in leaves if l['status'] == 'pending'])
    approved = len([l for l in leaves if l['status'] == 'approved'])
    rejected = len([l for l in leaves if l['status'] == 'rejected'])

    return render_template('student_dashboard.html',
                          student=student,
                          total_used=total_used,
                          pending=pending,
                          approved=approved,
                          rejected=rejected)

@app.route('/student/apply_leave', methods=['GET', 'POST'])
@student_required
def apply_leave():
    student_id = session['student_id']
    db = get_db()

    student = db.execute('SELECT * FROM students WHERE student_id = ?', (student_id,)).fetchone()
    leaves = db.execute('SELECT * FROM leave_applications WHERE student_id = ? AND status = "approved"',
                       (student_id,)).fetchall()
    days_already_taken = sum(leave['num_days'] for leave in leaves)

    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()
        session_type = normalize_session_type(request.form.get('session_type', ''))
        from_date = request.form.get('from_date', '').strip()
        to_date = request.form.get('to_date', '').strip()
        student_signature = request.form.get('student_signature', '')
        parent_signature = request.form.get('parent_signature', '')

        # Validate required fields
        if not reason or not from_date or not to_date:
            flash('Please fill all required fields', 'error')
            return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

        try:
            parsed_from = datetime.strptime(from_date, '%Y-%m-%d').date()
            parsed_to = datetime.strptime(to_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid leave date format', 'error')
            return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

        if parsed_from > parsed_to:
            flash('From date cannot be after To date', 'error')
            return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

        day_span = (parsed_to - parsed_from).days + 1
        if day_span <= 0:
            flash('Number of days must be greater than 0', 'error')
            return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

        if session_type in ['FN', 'AN'] and day_span != 1:
            flash('FN or AN leave can only be applied for a single day', 'error')
            return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

        num_days = 0.5 if session_type in ['FN', 'AN'] else float(day_span)

        if not is_likely_valid_signature(student_signature) or not is_likely_valid_signature(parent_signature):
            flash('Both signatures are required', 'error')
            return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

        applied_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            db.execute('''INSERT INTO leave_applications
                         (student_id, name, register_number, department, year, reason,
                          from_date, to_date, num_days, session_type, days_already_taken,
                          student_signature, parent_signature, applied_time)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (student_id, student['name'], student['register_number'],
                       student['department'], student['year'], reason, from_date, to_date,
                       num_days, session_type, int(days_already_taken), student_signature,
                       parent_signature, applied_time))
            db.commit()

            flash('Leave application submitted successfully!', 'success')
            return redirect(url_for('leave_status'))
        except Exception as e:
            flash('Error submitting application. Please try again.', 'error')

    return render_template('apply_leave.html', student=student, days_already_taken=days_already_taken)

@app.route('/student/leave_status')
@student_required
def leave_status():
    student_id = session['student_id']
    db = get_db()

    leaves = db.execute('SELECT * FROM leave_applications WHERE student_id = ? ORDER BY applied_time DESC',
                       (student_id,)).fetchall()

    return render_template('leave_status.html', leaves=leaves)

@app.route('/student/my_leaves')
@student_required
def my_leaves():
    student_id = session['student_id']
    db = get_db()

    leaves = db.execute('SELECT * FROM leave_applications WHERE student_id = ? ORDER BY applied_time DESC',
                       (student_id,)).fetchall()

    return render_template('my_leaves.html', leaves=leaves)

# ==================== API ENDPOINTS ====================

@app.route('/api/leave/count')
@admin_required
def api_leave_count():
    db = get_db()

    if session.get('role') == 'principal':
        count = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE status = "pending"').fetchone()['count']
    else:
        dept = session['department']
        count = db.execute('SELECT COUNT(*) as count FROM leave_applications WHERE department = ? AND status = "pending"',
                          (dept,)).fetchone()['count']

    return jsonify({'count': count})

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return redirect(url_for('login'))

@app.errorhandler(500)
def server_error(error):
    return 'Server error occurred. Please refresh and try again.', 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
