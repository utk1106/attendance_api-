from flask import Flask, render_template, redirect, url_for, request, flash,jsonify
import geocoder
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity,create_refresh_token
from flask_sqlalchemy import SQLAlchemy
from database import db
import requests
from sqlalchemy import and_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user, login_manager
from models import User,LeaveRequest,Attendance,OfficeLocation
from datetime import datetime,timedelta,date
from utils import is_within_office,write_attendance_to_sheet,get_place_name
from sqlalchemy.orm import joinedload

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'dcd68e52cdd2e409ca027ddc4bcec3560685af6e83092c0e90f0692828847d42'
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=6)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ashwin:ashwin@localhost:5432/ashwin'
app.config['SECRET_KEY'] = 'your_unique_secret_key'
IST_OFFSET = timedelta(hours=5, minutes=30)
jwt = JWTManager(app)
db.init_app(app)
ALLOWED_SUPERIORS = {"ashwinnair@gmail.com"}
login_manager = LoginManager(app)
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/realtime-sheet')
def realtime_sheet():
    return render_template('realtime_sheet.html')


@app.route('/api/sheet-data')
def get_sheet_data():
    try:
        records = Attendance.query.options(joinedload(Attendance.user)).all()
        sheet_data = [
            {
                "Employee Name": rec.user.username,
                "Date": rec.login_time.date().isoformat(),
                "Login Time": rec.login_time.strftime("%H:%M"),
                "Logout Time": rec.logout_time.strftime("%H:%M") if rec.logout_time else '',
                "Location": rec.place
            }
            for rec in records
        ]
        return jsonify(sheet_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"error":"User with this email already exists"}), 400
        
        if not username or not email or not password:
            return jsonify({"error": "Username, email, and password are required"}), 400

        if role == "superior" and email not in ALLOWED_SUPERIORS:
            return jsonify({"error": "You are not allowed to register as a superior"}), 403
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created!', 'success')
        return jsonify({"message": "User Registered Successfully"}), 201

@app.route('/login', methods=['GET', 'POST'])
def login():
    data = request.json  # Accept JSON body instead of form data
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and user.password == password:
        access_token = create_access_token(identity={"id": user.id, "role": user.role, "username": user.username})
        refresh_token = create_refresh_token(identity={"id": user.id, "role": user.role, "username": user.username})
        return jsonify({"access_token": access_token, "refresh_token": refresh_token}), 200

    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'superior':
        leave_requests = LeaveRequest.query.all()
        return render_template('dashboard.html', leave_requests=leave_requests)
    
    return render_template('dashboard.html')

@app.route('/api/leave', methods=['GET', 'POST'])
@jwt_required()
def apply_leave():
    user_identity = get_jwt_identity()  # Get logged-in user info
    user_id = user_identity['id']

    if request.method == 'POST':
        data = request.get_json()
        start_date = datetime.strptime(data['start_date'], "%Y-%m-%d").date()
        end_date = datetime.strptime(data['end_date'], "%Y-%m-%d").date()

        # if not leave_type or not start_date or not end_date or not reason:
        #     return jsonify({"error": "All fields are required"}), 400

        leave_request = LeaveRequest(
            user_id=user_id, 
            leave_type=data['leave_type'], 
            start_date=start_date, 
            end_date=end_date, 
            reason=data['reason'], 
            status='pending'
        )
        db.session.add(leave_request)
        db.session.commit()

        return jsonify({"message": "Leave application submitted successfully"}), 201

    # GET request - Fetch all leaves of the logged-in user
    leave_requests = LeaveRequest.query.filter_by(user_id=user_id).all()
    leave_data = [
        {
            "id": leave.id,
            "leave_type": leave.leave_type,
            "start_date": datetime.strptime(leave.start_date, "%Y-%m-%d").date().isoformat() if isinstance(leave.start_date, str) else leave.start_date.isoformat(),
            "end_date": datetime.strptime(leave.end_date, "%Y-%m-%d").date().isoformat() if isinstance(leave.end_date, str) else leave.end_date.isoformat(),
            "reason": leave.reason,
            "status": leave.status
        }
        for leave in leave_requests
    ]
    
    return jsonify(leave_data), 200

@app.route('/approve_leave/<int:leave_id>', methods=['POST'])
@jwt_required()
def approve_leave(leave_id):
    try:
        current_user_data = get_jwt_identity()

        current_user_id = current_user_data['id']
        current_user = db.session.get(User,current_user_id)

        if not current_user or current_user.role != 'superior':
            return jsonify({"message": "Access denied. Only superiors can approve leaves."}), 403

        leave_request = db.session.get(LeaveRequest, leave_id)

        if leave_request.status == "approved":
            return jsonify({"message": "Leave is already approved."}), 400

        leave_request.status = 'approved'
        db.session.commit()
    except Exception as e:
        print(e )
    return jsonify({"message":"Leave approved successfully", "leave_id": leave_id, "status": "approved"}), 200

@app.route('/reject_leave/<int:leave_id>', methods=['POST'])
@jwt_required()
def reject_leave(leave_id):
    try:
        current_user_data = get_jwt_identity()
        current_user_id = current_user_data['id']  # Get the logged-in user ID from JWT
        current_user = db.session.get(User,current_user_id)
        if not current_user or current_user.role != 'superior':
            return jsonify({"message": "Access denied. Only superiors can approve/reject leaves."}), 403
        if current_user.role == 'superior':
            leave_request = db.session.get(LeaveRequest, leave_id)
            leave_request.status = 'rejected'
            db.session.commit()
            flash('Leave rejected!', 'danger')
    except Exception as e:
        print(e)
    return jsonify({"message":"Leave was rejected", "leave_id": leave_id, "status": "rejected"}), 200

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

def get_location():
    response = requests.get("https://api64.ipify.org?format=json")
    public_ip = response.json().get("ip")
    url = f"https://ipinfo.io/{public_ip}/json"
    response = requests.get(url)
    data = response.json()
    location = data.get("loc", "0,0")
    latitude, longitude = location.split(",")
    return latitude,longitude

@app.route('/api/attendance/login', methods=['POST'])
@jwt_required()
def mark_attendance_login():
    latitude,longitude = get_location()
    place_name = get_place_name(latitude,longitude)
    user_identity = get_jwt_identity()
    user_id = user_identity['id']
    user_name = user_identity['username']

    current_time_utc = datetime.utcnow()
    current_time_ist = current_time_utc + IST_OFFSET
    today_date_ist = current_time_ist.date()

    existing_attendance = Attendance.query.filter(
        and_(
            Attendance.user_id == user_id,
            Attendance.login_time >= today_date_ist,
            Attendance.login_time < today_date_ist + timedelta(days=1)
        )
    ).first()

    if existing_attendance:
        return jsonify({"error": "Attendance already marked for today"}), 400

    # Record new login entry
    new_attendance = Attendance(
        user_id=user_id,
        login_time=current_time_ist,
        place=place_name
    )
    db.session.add(new_attendance)
    db.session.commit()
    
    Sheet_response = write_attendance_to_sheet(user_name,login_time=current_time_ist,logout_time=None,place=place_name)
    if "error" in Sheet_response:
        return jsonify({"error": "Log-in recorded but failed to update Sheet", "details": Sheet_response["details"]}), 500
    
    return jsonify({
        "message": "Log-in recorded",
        "login_time": current_time_ist.strftime("%Y-%m-%d %H:%M:%S IST")
    }), 201

# Mark Attendance (Logout)
@app.route('/api/attendance/logout', methods=['POST'])
@jwt_required()
def mark_attendance_logout():
    latitude,longitude = get_location()
    user_identity = get_jwt_identity()
    user_name = user_identity['username']
    user_id = user_identity['id']

    today = date.today()
    attendance = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.login_time >= datetime.combine(today, datetime.min.time())
    ).order_by(Attendance.login_time.desc()).first()

    if not attendance:
        return jsonify({"error": "No attendance record found for today"}), 404

    if not is_within_office(latitude, longitude):
        return jsonify({"error": "You are not within the allowed office location"}), 403

    # Update the log-out time to the latest time
    logout_time_utc = datetime.utcnow()
    logout_time_ist = logout_time_utc + IST_OFFSET
    print(type(logout_time_ist))
    attendance.logout_time = logout_time_ist
    db.session.commit()
    write_attendance_to_sheet(user_name,login_time=None, logout_time=logout_time_ist,place=None)
    return jsonify({"message": "Log-out recorded"}), 200
# Get Employee Attendance
@app.route('/api/attendance/my', methods=['GET'])
@jwt_required()
def get_my_attendance():
    user_details = get_jwt_identity()
    userid = user_details['id']
    attendance_records = Attendance.query.filter_by(user_id=userid).all()
    records = [
        {
            "date": record.login_time.date().isoformat(),
            "login_time": record.login_time.strftime("%H:%M") if record.login_time else None,
            "logout_time": record.logout_time.strftime("%H:%M") if record.logout_time else None,
            "location": f"{record.latitude}, {record.longitude}"
        }
        for record in attendance_records
    ]
    return jsonify(records), 200

# Admin: Set Office Location 
@app.route('/api/settings/office-location', methods=['POST'])
@jwt_required()
def set_office_location():
    user_data = get_jwt_identity()
    user_id = user_data['id']
    user = db.session.get(User, user_id)  # Fetch user from DB
    
    if not user or user.role != 'superior':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius = data.get("radius")  # Radius in meters

    if not latitude or not longitude or not radius:
        return jsonify({"error": "Latitude, longitude, and radius are required"}), 400

    office = OfficeLocation.query.first()
    if office:
        office.latitude = latitude
        office.longitude = longitude
        office.radius = radius
    else:
        office = OfficeLocation(latitude=latitude, longitude=longitude, radius=radius)
        db.session.add(office)

    db.session.commit()
    return jsonify({"message": "Office location updated successfully"}), 200
# Admin: Get Office Location
# @app.route('/api/settings/office-location', methods=['GET'])
# @login_required
# def get_office_location():
#     if current_user.role != 'superior':
#         return jsonify({"error": "Unauthorized"}), 403

#     office = OfficeLocation.query.first()
#     if not office:
#         return jsonify({"error": "No office location set"}), 404

#     return jsonify({
#         "latitude": office.latitude,
#         "longitude": office.longitude,
#         "radius": office.radius
#     }), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
