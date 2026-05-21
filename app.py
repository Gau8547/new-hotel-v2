from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret123"

def init_db():
    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    # Admin table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    # Rooms table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_no TEXT,
        type TEXT,
        rent REAL,
        status TEXT
    )
    """)

    # Bookings table
    cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    phone TEXT,
    room_id INTEGER,
    checkin_date TEXT,
    duration INTEGER,
    due_date TEXT,
    payment_status TEXT DEFAULT 'Pending'
)
""")

    # Default admin
    cursor.execute("SELECT * FROM admin")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admin VALUES (NULL,'admin','1234')")

    # ✅ ADD THIS PART (default rooms)
    cursor.execute("SELECT COUNT(*) FROM rooms")
    count = cursor.fetchone()[0]

    if count == 0:
        default_rooms = []

        for i in range(301, 313):
            default_rooms.append((str(i), "Standard", 1000, "Available"))

        for i in range(401, 413):
            default_rooms.append((str(i), "Deluxe", 1500, "Available"))

        for i in range(501, 513):
            default_rooms.append((str(i), "Premium", 2000, "Available"))

        cursor.executemany("""
        INSERT INTO rooms (room_no, type, rent, status)
        VALUES (?,?,?,?)
        """, default_rooms)

    conn.commit()
    conn.close()
# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        conn = sqlite3.connect("hotel.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=? AND password=?", (u,p))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['admin'] = u
            return redirect('/')
        else:
            return "Invalid Login"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/login')

# ---------------- DASHBOARD ----------------
@app.route('/')
def home():
    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    # Room stats
    cursor.execute("SELECT COUNT(*) FROM rooms")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM rooms WHERE status='Available'")
    available = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM rooms WHERE status='Occupied'")
    occupied = cursor.fetchone()[0]

    # Booking alerts
    cursor.execute("SELECT due_date FROM bookings")
    bookings = cursor.fetchall()

    today = datetime.now().date()

    overdue = 0
    due_today = 0

    for b in bookings:
        due = datetime.strptime(b[0], "%Y-%m-%d").date()

        if today > due:
            overdue += 1
        elif today == due:
            due_today += 1

    conn.close()

    return render_template(
        'index.html',
        total_rooms=total,
        available_rooms=available,
        occupied_rooms=occupied,
        overdue_count=overdue,
        due_today_count=due_today
    )
# ---------------- ROOMS ----------------
@app.route('/rooms')
def rooms():
    if 'admin' not in session:
        return redirect('/login')

    search = request.args.get('search', '')
    status = request.args.get('status', '')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    query = "SELECT * FROM rooms WHERE 1=1"
    params = []

    # 🔍 Search by room number
    if search:
        query += " AND room_no LIKE ?"
        params.append(f"%{search}%")

    # 🎯 Filter by status
    if status:
        query += " AND status=?"
        params.append(status)

    cursor.execute(query, params)
    rooms = cursor.fetchall()
    conn.close()

    # 🏢 Group by floor
    grouped = {}

    for r in rooms:
        floor = str(r[1])[0]  # first digit (3,4,5)
        if floor not in grouped:
            grouped[floor] = []
        grouped[floor].append(r)

    return render_template("rooms.html", grouped=grouped)

# ---------------- BOOKING ----------------

@app.route('/booking', methods=['GET','POST'])
def booking():
    import sqlite3
    from flask import request, redirect, render_template

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, room_no FROM rooms WHERE status='Available'")
    rooms = cursor.fetchall()

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            phone = request.form.get('phone')
            room_id = request.form.get('room_id')
            checkin = request.form.get('checkin')
            duration = request.form.get('duration')

            if not all([name, phone, room_id, checkin, duration]):
                return "Invalid input ❌"

            duration = int(duration)

            from datetime import datetime, timedelta
            due_date = (datetime.strptime(checkin, "%Y-%m-%d") + timedelta(days=duration)).strftime("%Y-%m-%d")

            cursor.execute("""
            INSERT INTO bookings (name, phone, room_id, checkin_date, duration, due_date)
            VALUES (?,?,?,?,?,?)
            """, (name, phone, room_id, checkin, duration, due_date))

            cursor.execute("UPDATE rooms SET status='Occupied' WHERE id=?", (room_id,))

            conn.commit()
            conn.close()

            return redirect('/rooms')

        except Exception as e:
            import traceback
            return "<pre>" + traceback.format_exc() + "</pre>"

    conn.close()
    return render_template("booking.html", rooms=rooms)

# ---------------- add checkout----------------

@app.route('/checkout/<int:id>')
def checkout(id):
    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("SELECT room_id FROM bookings WHERE id=?", (id,))
    room_id = cursor.fetchone()[0]

    # Remove booking
    cursor.execute("DELETE FROM bookings WHERE id=?", (id,))

    # 🔥 Set room to CLEANING
    cursor.execute("UPDATE rooms SET status='Cleaning' WHERE id=?", (room_id,))

    conn.commit()
    conn.close()

    return redirect('/rooms')

    # ---------------- edit booking----------------
@app.route('/edit_booking/<int:id>', methods=['GET','POST'])
def edit_booking(id):
    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    if request.method == 'POST':
        duration = int(request.form['duration'])
        checkin = datetime.strptime(request.form['checkin'], "%Y-%m-%d")

        due_date = checkin + timedelta(days=duration)

        cursor.execute("""
        UPDATE bookings SET checkin_date=?, duration=?, due_date=?
        WHERE id=?
        """, (
            checkin.strftime("%Y-%m-%d"),
            duration,
            due_date.strftime("%Y-%m-%d"),
            id
        ))

        conn.commit()
        conn.close()

        return redirect('/bookings')

    cursor.execute("SELECT * FROM bookings WHERE id=?", (id,))
    booking = cursor.fetchone()
    conn.close()

    return render_template('edit_booking.html', booking=booking)

   # ---------------- EDIT ROOM ----------------
@app.route('/edit_room/<int:id>', methods=['GET','POST'])
def edit_room(id):
    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    if request.method == 'POST':
        room_no = request.form['room_no']
        type = request.form['type']
        rent = request.form['rent']
        status = request.form['status']

        cursor.execute("""
        UPDATE rooms SET room_no=?, type=?, rent=?, status=? WHERE id=?
        """, (room_no, type, rent, status, id))

        conn.commit()
        conn.close()

        return redirect('/rooms')

    cursor.execute("SELECT * FROM rooms WHERE id=?", (id,))
    room = cursor.fetchone()
    conn.close()

    return render_template('edit_room.html', room=room)

    # ---------------- clean done----------------

@app.route('/clean_done/<int:id>')
def clean_done(id):
    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE rooms SET status='Available' WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/rooms')

# ---------------- pending ----------------

@app.route('/pending')
def pending():
    if 'admin' not in session:
        return redirect('/login')

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT bookings.*, rooms.room_no 
    FROM bookings
    JOIN rooms ON bookings.room_id = rooms.id
    """)

    data = cursor.fetchall()
    conn.close()

    today = datetime.now().date()
    pending_list = []

    for b in data:
        due = datetime.strptime(b[6], "%Y-%m-%d").date()

        if today >= due:
            pending_list.append(b)

    return render_template("pending.html", bookings=pending_list)
# ---------------- bill ----------------

from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

@app.route('/bill/<int:id>')
def bill(id):
    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("""
    SELECT bookings.*, rooms.room_no 
    FROM bookings
    JOIN rooms ON bookings.room_id = rooms.id
    WHERE bookings.id=?
    """, (id,))

    b = cursor.fetchone()
    conn.close()

    filename = f"bill_{id}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph(f"Customer: {b[1]}", styles['Normal']))
    content.append(Paragraph(f"Room: {b[7]}", styles['Normal']))
    content.append(Paragraph(f"Check-in: {b[4]}", styles['Normal']))
    content.append(Paragraph(f"Due Date: {b[6]}", styles['Normal']))

    doc.build(content)

    return send_file(filename, as_attachment=True)

# ---------------- restore ----------------

@app.route('/restore_room/<int:id>')
def restore_room(id):
    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("UPDATE rooms SET status='Available' WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/rooms')

# ---------------- add room ----------------
@app.route('/rooms')
def rooms():
    import sqlite3
    from flask import render_template, request

    conn = sqlite3.connect("hotel.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM rooms")
    data = cursor.fetchall()

    # group by floor
    grouped = {}
    for r in data:
        floor = str(r[1])[0]  # first digit of room number
        if floor not in grouped:
            grouped[floor] = []
        grouped[floor].append(r)

    conn.close()

    return render_template("rooms.html", grouped=grouped)

# ---------------- delete room ----------------

@app.route('/delete_room/<int:id>')
def delete_room(id):
    import sqlite3
    from flask import redirect

    try:
        conn = sqlite3.connect("hotel.db")
        cursor = conn.cursor()

        cursor.execute("DELETE FROM rooms WHERE id=?", (id,))
        conn.commit()
        conn.close()

        return redirect('/rooms')

    except Exception as e:
        return str(e)# 


@app.route('/')
def home():
    return "APP IS RUNNING"
# ---------------- RUN ----------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True)