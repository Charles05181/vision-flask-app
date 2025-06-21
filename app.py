from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import pymssql
from datetime import datetime, timedelta
import webbrowser
from threading import Timer
import random
import string
import os


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Database connection details
server = 'SQL8010.site4now.net'
database = 'db_aaafa7_visionapp'
username = 'db_aaafa7_visionapp_admin'
password = 'Charles@0518'

def create_connection():
    try:
        connection = pymssql.connect(
            server=server,
            user=username,
            password=password,
            database=database
        )
        return connection
    except pymssql.Error as e:
        print(f"The error '{e}' occurred")
        return None

def get_current_time():
    return datetime.now()

def add_expiration_date_column():
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                IF NOT EXISTS (
                    SELECT * FROM sys.columns 
                    WHERE object_id = OBJECT_ID('Users') AND name = 'expiration_date'
                )
                BEGIN
                    ALTER TABLE Users ADD expiration_date DATE;
                END
            """)
            conn.commit()
        except Exception as e:
            print(f"Failed to add expiration_date column: {e}")
        finally:
            conn.close()

def delete_expired_users():
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        try:
            today = get_current_time().date()
            cursor.execute("DELETE FROM Users WHERE expiration_date < ?", (today,))
            conn.commit()
        except Exception as e:
            print(f"Failed to delete expired users: {e}")
        finally:
            conn.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['username']
        password = request.form['password']
        conn = create_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM Users WHERE user_id = %s AND password = %s", (user_id, password))
            result = cursor.fetchone()
            conn.close()

            if result and result[0] == "A":
                session['logged_in'] = True
                session['username'] = user_id
                add_expiration_date_column()
                delete_expired_users()
                return redirect(url_for('dashboard'))
        flash('Invalid credentials or not an admin!', 'error')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, role, password, expiration_date, is_logged_in FROM Users")
        users = cursor.fetchall()
        conn.close()

        user_data = []
        for user in users:
            user_id, role, password, expiration_date, is_logged_in = user
            user_data.append({
                'user_id': user_id,
                'role': "Admin" if role == "A" else "User",
                'password': password,
                'expiration_date': expiration_date.strftime('%Y-%m-%d') if expiration_date else "N/A",
                'is_logged_in': bool(is_logged_in)
            })

        return render_template('dashboard.html', users=user_data)
    return render_template('dashboard.html', users=[])

@app.route('/logout_user/<user_id>')
def logout_user(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET is_logged_in = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        flash(f'User {user_id} logged out successfully', 'success')

    return redirect(url_for('dashboard'))

@app.route('/logout_all_users')
def logout_all_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET is_logged_in = 0")
        conn.commit()
        conn.close()
        flash('All users have been logged out successfully.', 'success')

    return redirect(url_for('dashboard'))

@app.route('/delete_user/<user_id>')
def delete_user(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        flash(f'User {user_id} deleted successfully', 'success')

    return redirect(url_for('dashboard'))

@app.route('/add_user', methods=['POST'])
def add_user():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    new_user_id = request.form['new_user_id']
    new_password = request.form['new_password']
    role = request.form['role']
    validity_days = request.form.get('validity_days', '0')

    if not new_user_id or not new_password or not role:
        flash('Please fill all required fields!', 'error')
        return redirect(url_for('dashboard'))

    if role == "User" and not validity_days.isdigit():
        flash('Please enter a valid number of days for users!', 'error')
        return redirect(url_for('dashboard'))

    expiration_date = None
    if role == "User":
        expiration_date = (get_current_time() + timedelta(days=int(validity_days))).date()

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (user_id, role, password, expiration_date) VALUES (?, ?, ?, ?)",
                (new_user_id, "A" if role == "Admin" else "U", new_password, expiration_date)
            )
            conn.commit()
            flash('User added successfully!', 'success')
        except Exception as e:
            flash(f'Failed to add user: {e}', 'error')
        finally:
            conn.close()

    return redirect(url_for('dashboard'))

@app.route('/generate_users', methods=['POST'])
def generate_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    base_username = request.form['base_username']
    count = int(request.form['count'])
    validity_days = int(request.form.get('validity_days', '30'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        for _ in range(count):
            suffix = ''.join(random.choices(string.digits, k=5))
            username = f"{base_username}{suffix}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            expiration_date = (get_current_time() + timedelta(days=validity_days)).date()

            try:
                cursor.execute("INSERT INTO Users (user_id, role, password, expiration_date) VALUES (?, ?, ?, ?)",
                               (username, "U", password, expiration_date))
            except Exception as e:
                flash(f'Error creating user {username}: {e}', 'error')

        conn.commit()
        conn.close()
        flash(f'{count} users generated successfully.', 'success')

    return redirect(url_for('dashboard'))

@app.route('/export_users')
def export_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, role, password, expiration_date, is_logged_in FROM Users")
        users = cursor.fetchall()
        conn.close()

        def generate():
            yield 'User ID,Role,Password,Expiration Date,Status\n'
            for user in users:
                yield f"{user[0]},{'Admin' if user[1] == 'A' else 'User'},{user[2]},{user[3] or ''},{'Logged In' if user[4] else 'Logged Out'}\n"

        return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=users.csv"})

    flash("Failed to export users.", "error")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

