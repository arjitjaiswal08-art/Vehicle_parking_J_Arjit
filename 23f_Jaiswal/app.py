from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = 'parkingsecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Create models

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(128), nullable=False)
    details = db.Column(db.String(256), nullable=True)
    user = db.relationship('User')

    def __repr__(self):
        return f'<Activity {self.action} by {self.user_id} at {self.timestamp}>'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    pincode = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    reservations = db.relationship('Reservation', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    prime_location_name = db.Column(db.String(100), nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(20), nullable=False)
    maximum_spots = db.Column(db.Integer, nullable=False)
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<ParkingLot {self.name}>'

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(1), default='A')  # 'A' for Available, 'O' for Occupied
    reservations = db.relationship('Reservation', backref='spot', lazy=True)
    
    def __repr__(self):
        return f'<ParkingSpot {self.spot_number} in Lot {self.lot_id}>'

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    parking_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp = db.Column(db.DateTime, nullable=True)
    total_cost = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    owner_name = db.Column(db.String(120), nullable=True)
    vehicle_number = db.Column(db.String(32), nullable=True)
    
    def __repr__(self):
        return f'<Reservation {self.id}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize database and create admin

def create_tables():
    db.create_all()
    
    # Create admin if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@parking.com',
            password=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = ParkingLot.query.filter(
            (ParkingLot.name.ilike(f'%{query}%')) |
            (ParkingLot.prime_location_name.ilike(f'%{query}%'))
        ).all()
    return render_template('search_results.html', query=query, results=results)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        full_name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        pincode = request.form.get('pincode')
        password = request.form.get('password')
        
        user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
        if user_exists:
            flash('Username or email already exists', 'danger')
        else:
            new_user = User(
                username=username,
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                pincode=pincode,
                password=generate_password_hash(password),
                is_admin=False
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('user_dashboard'))
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = total_spots - occupied_spots
    users_count = User.query.filter_by(is_admin=False).count()
    # Fetch all lots and their spots
    parking_lots = ParkingLot.query.all()
    for lot in parking_lots:
        lot.spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    # Fetch recent activities (last 10)
    recent_activities = Activity.query.order_by(Activity.timestamp.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
                           total_lots=total_lots,
                           total_spots=total_spots,
                           occupied_spots=occupied_spots,
                           available_spots=available_spots,
                           users_count=users_count,
                           parking_lots=parking_lots,
                           recent_activities=recent_activities)


@app.route('/admin/parking-lots')
@login_required
def admin_parking_lots():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    parking_lots = ParkingLot.query.all()
    return render_template('admin/parking_lots.html', parking_lots=parking_lots)

@app.route('/admin/parking-lot/add', methods=['GET', 'POST'])
@login_required
def add_parking_lot():
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        prime_location = request.form.get('prime_location')
        price = float(request.form.get('price'))
        address = request.form.get('address')
        pincode = request.form.get('pincode')
        max_spots = int(request.form.get('max_spots'))
        if ParkingLot.query.filter_by(name=name).first():
            flash('Parking lot with this name already exists', 'danger')
            return redirect(url_for('add_parking_lot'))
        if ParkingLot.query.filter(db.func.lower(ParkingLot.name) == db.func.lower(name)).first():
            flash('Parking lot with this prime location already exists', 'danger')
            return redirect(url_for('add_parking_lot'))
        
        
        # Create new parking lot
        new_lot = ParkingLot(
            name=name,
            prime_location_name=prime_location,
            price_per_hour=price,
            address=address,
            pincode=pincode,
            maximum_spots=max_spots
        )
        db.session.add(new_lot)
        db.session.commit()
        
        # Create parking spots for this lot
        for i in range(1, max_spots + 1):
            spot = ParkingSpot(lot_id=new_lot.id, spot_number=i, status='A')
            db.session.add(spot)
        
        db.session.commit()
        flash('Parking lot created successfully', 'success')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('admin/add_parking_lot.html')

@app.route('/admin/parking-lot/edit/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def edit_parking_lot(lot_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    if request.method == 'POST':
        lot.name = request.form.get('name')
        lot.prime_location_name = request.form.get('prime_location')
        lot.price_per_hour = float(request.form.get('price'))
        lot.address = request.form.get('address')
        lot.pincode = request.form.get('pincode')
        new_max_spots = int(request.form.get('max_spots'))
        
        # Handle increase or decrease in parking spots
        current_spots = len(lot.spots)
        if new_max_spots > current_spots:
            # Add more spots
            for i in range(current_spots + 1, new_max_spots + 1):
                spot = ParkingSpot(lot_id=lot.id, spot_number=i, status='A')
                db.session.add(spot)
        elif new_max_spots < current_spots:
            # Check if any spots to be removed are occupied
            spots_to_remove = ParkingSpot.query.filter(
                ParkingSpot.lot_id == lot.id,
                ParkingSpot.spot_number > new_max_spots,
                ParkingSpot.status == 'O'
            ).first()
            
            if spots_to_remove:
                flash('Cannot reduce spots. Some spots to be removed are occupied.', 'danger')
                return redirect(url_for('edit_parking_lot', lot_id=lot.id))
            
            # Remove excess spots
            ParkingSpot.query.filter(
                ParkingSpot.lot_id == lot.id,
                ParkingSpot.spot_number > new_max_spots
            ).delete()
        
        lot.maximum_spots = new_max_spots
        db.session.commit()
        flash('Parking lot updated successfully', 'success')
        return redirect(url_for('admin_parking_lots'))
    
    return render_template('admin/edit_parking_lot.html', lot=lot)

@app.route('/admin/parking-lot/delete/<int:lot_id>')
@login_required
def delete_parking_lot(lot_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    
    # Check if any spots are occupied
    occupied_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
    if occupied_spots > 0:
        flash('Cannot delete parking lot. Some spots are occupied.', 'danger')
        return redirect(url_for('admin_parking_lots'))
    
    # Delete all reservations for spots in this lot
    spot_ids = [spot.id for spot in lot.spots]
    if spot_ids:
        Reservation.query.filter(Reservation.spot_id.in_(spot_ids)).delete(synchronize_session=False)
    db.session.delete(lot)
    db.session.commit()
    flash('Parking lot deleted successfully', 'success')
    return redirect(url_for('admin_parking_lots'))

@app.route('/admin/parking-spots/<int:lot_id>')
@login_required
def admin_parking_spots(lot_id):
    if not current_user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).order_by(ParkingSpot.spot_number).all()
    
    # Get active reservations for occupied spots
    active_reservations = {}
    for spot in spots:
        if spot.status == 'O':
            reservation = Reservation.query.filter_by(spot_id=spot.id, is_active=True).first()
            active_reservations[spot.spot_number] = reservation

    return render_template('admin/parking_spots.html', lot=lot, spots=spots, active_reservations=active_reservations)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('user_dashboard'))
    q = request.args.get('q', '').strip()
    if q:
        users = User.query.filter(
            User.is_admin == False,
            (
                User.username.ilike(f'%{q}%') |
                User.full_name.ilike(f'%{q}%') |
                User.email.ilike(f'%{q}%')
            )
        ).all()
    else:
        users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/summary')
@login_required
def admin_summary():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('user_dashboard'))
    # Get overall summary
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    occupied_spots = ParkingSpot.query.filter_by(status='O').count()
    available_spots = total_spots - occupied_spots
    users_count = User.query.filter_by(is_admin=False).count()
    # Get lot-wise summary
    lots = ParkingLot.query.all()
    lot_summary = []
    for lot in lots:
        lot_total_spots = ParkingSpot.query.filter_by(lot_id=lot.id).count()
        lot_occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        lot_available_spots = lot_total_spots - lot_occupied_spots
        lot_summary.append({
            'name': lot.name,
            'total': lot_total_spots,
            'occupied': lot_occupied_spots,
            'available': lot_available_spots,
            'occupancy_rate': round((lot_occupied_spots / lot_total_spots) * 100 if lot_total_spots > 0 else 0, 2)
        })
    # Get revenue summary (if Reservation has total_cost)
    total_revenue = db.session.query(func.sum(Reservation.total_cost)).scalar() or 0

    # Calculate today's revenue (completed reservations today)
    today = datetime.now().date()
    today_revenue = db.session.query(func.sum(Reservation.total_cost)).filter(
        Reservation.leaving_timestamp != None,
        func.date(Reservation.leaving_timestamp) == today
    ).scalar() or 0

    return render_template('admin/summary.html', 
                          total_lots=total_lots,
                          total_spots=total_spots,
                          occupied_spots=occupied_spots,
                          available_spots=available_spots,
                          users_count=users_count,
                          lot_summary=lot_summary,
                          total_revenue=total_revenue,
                          today_revenue=today_revenue)

# User routes

@app.route('/user/find-parking')
@login_required
def find_parking():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    location = request.args.get('location', '').strip()
    query = db.session.query(ParkingLot).join(ParkingSpot, ParkingLot.id == ParkingSpot.lot_id).filter(ParkingSpot.status == 'A')
    if location:
        query = query.filter(ParkingLot.prime_location_name.ilike(f'%{location}%'))
    lots = query.group_by(ParkingLot.id).all()
    return render_template('user/find_parking.html', lots=lots)

@app.route('/user/track-usage')
@login_required
def track_usage():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    # Get user's parking history
    history = Reservation.query.filter_by(user_id=current_user.id, is_active=False).order_by(Reservation.parking_timestamp.desc()).all()
    total_spent = sum([r.total_cost for r in history])
    return render_template('user/track_usage.html', history=history, total_spent=total_spent)

@app.route('/user/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    # Only allow non-admin users to edit their profile
    if current_user.is_admin:
        flash('Admins cannot edit user profile from here.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Get current user from db
    user = db.session.get(User, current_user.id)
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        pincode = request.form.get('pincode')
        vehicle_number = request.form.get('vehicle_number')
        password = request.form.get('password')

        # Validate and update fields
        if name:
            setattr(user, 'full_name', name)
        if email:
            user.email = email
        if phone:
            setattr(user, 'phone', phone)
        if address:
            setattr(user, 'address', address)
        if pincode:
            setattr(user, 'pincode', pincode)
        if vehicle_number is not None:
            setattr(user, 'vehicle_number', vehicle_number)
        # Only update password if provided
        if password:
            user.password = generate_password_hash(password)
        try:
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('user_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating profile. Please try again.', 'danger')
    # Render form with current values
    return render_template('user/edit_profile.html')

@app.route('/user/book-spot/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def book_spot(lot_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    lot = ParkingLot.query.get_or_404(lot_id)
    available_spots = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').all()
    if not available_spots:
        flash('No available spots in this lot.', 'warning')
        return redirect(url_for('user_dashboard'))
    spot = available_spots[0]  # Default to first available spot
    vehicle_number = request.form.get('vehicle_number')
    start_time = request.form.get('start_time')
    if request.method == 'POST':
        # Redirect to confirmation page with booking details
        # Pass vehicle_number and start_time as query parameters in the URL's query string
        return redirect(url_for('confirm_booking', lot_id=lot_id) + f'?vehicle_number={vehicle_number or ""}&start_time={start_time or ""}')
    return render_template('user/book_spot.html', lot=lot, spot=spot, start_time=start_time, vehicle_number=vehicle_number)

@app.route('/user/history')
@login_required
def user_history():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    history = Reservation.query.filter_by(user_id=current_user.id, is_active=False).order_by(Reservation.parking_timestamp.desc()).all()
    return render_template('user/history.html', history=history)


@app.route('/user/view-spot/<int:spot_id>')
@login_required
def view_spot(spot_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    spot = ParkingSpot.query.get_or_404(spot_id)
    lot = ParkingLot.query.get_or_404(spot.lot_id)
    reservation = None
    if spot.status == 'O':
        reservation = Reservation.query.filter_by(spot_id=spot_id, is_active=True).first()
    return render_template('user/view_spot.html', spot=spot, lot=lot, reservation=reservation)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # Get user's active reservation
    active_reservation = Reservation.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    # Get user's parking history
    history = Reservation.query.filter_by(user_id=current_user.id, is_active=False).order_by(Reservation.parking_timestamp.desc()).all()
    
    # Get parking lots with available spots
    lots_with_available_spots = db.session.query(ParkingLot).\
        join(ParkingSpot, ParkingLot.id == ParkingSpot.lot_id).\
        filter(ParkingSpot.status == 'A').\
        group_by(ParkingLot.id).\
        all()
    
    return render_template('user/dashboard.html', active_reservation=active_reservation, history=history, lots_with_available_spots=lots_with_available_spots, now=datetime.now())

@app.route('/user/confirm-booking/<int:lot_id>', methods=['GET', 'POST'])
@login_required
def confirm_booking(lot_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    active_reservation = Reservation.query.filter_by(user_id=current_user.id, is_active=True).first()
    if active_reservation:
        flash('You already have an active reservation', 'warning')
        return redirect(url_for('user_dashboard'))
    lot = ParkingLot.query.get_or_404(lot_id)
    available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    vehicle_number = request.args.get('vehicle_number') or request.form.get('vehicle_number')
    start_time = request.args.get('start_time') or request.form.get('start_time')
    if request.method == 'POST':
        if not available_spot:
            flash('No parking spots available in this lot', 'danger')
            return redirect(url_for('user_dashboard'))
        new_reservation = Reservation(
            user_id=current_user.id,
            spot_id=available_spot.id,
            parking_timestamp=datetime.now(),
            is_active=True,
            owner_name=current_user.full_name if hasattr(current_user, 'full_name') else current_user.username,
            vehicle_number=vehicle_number
        )
        available_spot.status = 'O'
        db.session.add(new_reservation)
        db.session.commit()
        flash(f'Spot {available_spot.spot_number} booked successfully in {lot.name}', 'success')
        return redirect(url_for('user_dashboard'))
    return render_template('user/confirm_booking.html', lot=lot, spot=available_spot, vehicle_number=vehicle_number, start_time=start_time)

@app.route('/user/release-spot/<int:reservation_id>')
@login_required
def release_spot(reservation_id):
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    reservation = Reservation.query.get_or_404(reservation_id)
    
    # Check if reservation belongs to current user
    if reservation.user_id != current_user.id:
        flash('Unauthorized action', 'danger')
        return redirect(url_for('user_dashboard'))
    
    # Calculate total cost
    spot = ParkingSpot.query.get(reservation.spot_id)
    lot = ParkingLot.query.get(spot.lot_id)
    
    leaving_time = datetime.now()  # Use local time for release
    hours_parked = (leaving_time - reservation.parking_timestamp).total_seconds() / 3600
    total_cost = round(hours_parked * lot.price_per_hour, 2)
    
    # Update reservation
    reservation.leaving_timestamp = leaving_time
    reservation.total_cost = total_cost
    reservation.is_active = False
    
    # Update spot status
    spot.status = 'A'
    
    db.session.commit()
    
    flash(f'Parking spot released. Total cost: ₹{total_cost:.2f}', 'success')
    return redirect(url_for('user_dashboard'))

# API routes
@app.route('/api/lots', methods=['GET'])
def api_lots():
    lots = ParkingLot.query.all()
    result = []
    
    for lot in lots:
        total_spots = len(lot.spots)
        available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        
        result.append({
            'id': lot.id,
            'name': lot.name,
            'location': lot.prime_location_name,
            'price': lot.price_per_hour,
            'total_spots': total_spots,
            'available_spots': available_spots
        })
    
    return jsonify(result)

@app.route('/api/spots/<int:lot_id>', methods=['GET'])
def api_spots(lot_id):
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    result = []
    
    for spot in spots:
        result.append({
            'id': spot.id,
            'spot_number': spot.spot_number,
            'status': 'Available' if spot.status == 'A' else 'Occupied'
        })
    
    return jsonify(result)

# Developer preview routes for templates not directly routed
@app.route('/preview/base')
def preview_base():
    return render_template('base.html')

if __name__ == '__main__':
    if not os.path.exists('instance'):
        os.makedirs('instance')
    with app.app_context():
        create_tables()
    app.run(debug=True, port=5002)