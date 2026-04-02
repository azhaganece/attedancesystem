# EduLeave Pro

A comprehensive leave management system built with Flask, HTML, CSS, JavaScript, and SQLite.

## Features

- **Admin Panel**: Department-specific admin accounts for CSE, ECE, IT, and AIDS
- **Student Portal**: Student login and leave application system
- **Leave Management**: Apply, approve, reject leave requests with signatures
- **Dashboard**: Statistics and recent activity
- **Responsive Design**: Works on desktop and mobile devices

## Setup

1. Install Python 3.8 or higher
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python app.py
   ```
4. Open your browser to `http://localhost:5000`

## Admin Credentials

- Principal: `principal / sincet@2025`
- CSE Admin: `admin_cse / cse@2025`
- ECE Admin: `admin_ece / ece@2025`
- IT Admin: `admin_it / it@2025`
- AIDS Admin: `admin_aids / aids@2025`
- AIML Admin: `admin_aiml / aiml@2025`
- MECH Admin: `admin_mech / mech@2025`
- AGRI Admin: `admin_agri / agri@2025`

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set the following:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Add environment variables if needed

## Database

The application uses SQLite (`database.db`) which is created automatically on first run. The database includes:
- `admins` table: Admin accounts
- `students` table: Student information
- `leave_applications` table: Leave requests

## Project Structure

```
eduleave-pro/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Procfile              # For Render deployment
├── database.db           # SQLite database (created automatically)
├── templates/            # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── admin_dashboard.html
│   ├── admin_students.html
│   ├── admin_student_profile.html
│   ├── add_student.html
│   ├── admin_leave_approvals.html
│   ├── admin_leave_detail.html
│   ├── student_dashboard.html
│   ├── apply_leave.html
│   ├── leave_status.html
│   └── my_leaves.html
└── static/               # CSS and JS files
    ├── css/
    │   └── style.css
    └── js/
        └── script.js
```