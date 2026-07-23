from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import pymssql
from datetime import datetime, timedelta
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
        cursor.execute("UPDATE Users SET is_logged_in = 0 WHERE user_id = %s", (user_id,))
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
        cursor.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
        conn.commit()
        conn.close()
        flash(f'User {user_id} deleted successfully', 'success')

    return redirect(url_for('dashboard'))

@app.route('/delete_selected_users', methods=['POST'])
def delete_selected_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    selected_users = request.form.getlist('selected_users')
    if not selected_users:
        flash('No users selected for deletion.', 'error')
        return redirect(url_for('dashboard'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        deleted_count = 0
        for user_id in selected_users:
            try:
                cursor.execute("DELETE FROM Users WHERE user_id = %s", (user_id,))
                deleted_count += 1
            except Exception as e:
                flash(f'Error deleting user {user_id}: {e}', 'error')
        conn.commit()
        conn.close()
        flash(f'{deleted_count} user(s) deleted successfully.', 'success')

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
            cursor.execute("INSERT INTO Users (user_id, role, password, expiration_date) VALUES (%s, %s, %s, %s)",
                           (new_user_id, "A" if role == "Admin" else "U", new_password, expiration_date))
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

    base_username = request.form['base_username'].strip()
    count = int(request.form['count'])
    validity_days = int(request.form.get('validity_days', '30'))
    common_password = request.form.get('password', '')

    if not base_username:
        flash('Base username is required.', 'error')
        return redirect(url_for('dashboard'))

    if not common_password:
        flash('Password is required for generating multiple users.', 'error')
        return redirect(url_for('dashboard'))

    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        # Find highest existing numeric suffix
        cursor.execute("SELECT user_id FROM Users WHERE user_id LIKE %s", (base_username + '%',))
        existing = cursor.fetchall()
        max_num = 0
        for row in existing:
            uid = row[0]
            if uid.startswith(base_username):
                suffix = uid[len(base_username):]
                if suffix.isdigit():
                    num = int(suffix)
                    if num > max_num:
                        max_num = num

        start_num = max_num + 1
        created_users = []
        created_count = 0
        for i in range(count):
            new_user_id = base_username + str(start_num + i)
            expiration_date = (get_current_time() + timedelta(days=validity_days)).date()
            try:
                cursor.execute("INSERT INTO Users (user_id, role, password, expiration_date) VALUES (%s, %s, %s, %s)",
                               (new_user_id, "U", common_password, expiration_date))
                created_users.append(new_user_id)
                created_count += 1
            except Exception as e:
                flash(f'Error creating user {new_user_id}: {e}', 'error')

        conn.commit()
        conn.close()

        if created_count > 0:
            # Store info in session to display on summary page
            session['generated_info'] = {
                'usernames': created_users,
                'password': common_password,
                'validity_days': validity_days,
                'expiration_date': (get_current_time() + timedelta(days=validity_days)).date().strftime('%Y-%m-%d')
            }
            return redirect(url_for('generated_users'))
        else:
            flash('No users were created. Check errors.', 'error')

    return redirect(url_for('dashboard'))

@app.route('/generated_users')
def generated_users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    gen_info = session.pop('generated_info', None)
    if not gen_info:
        flash('No user generation data found.', 'error')
        return redirect(url_for('dashboard'))
    return render_template('generated_users.html', info=gen_info)

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
