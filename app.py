from flask import Flask, render_template, request, redirect, jsonify, session, flash, url_for
from flask_mysqldb import MySQL
from datetime import datetime,timedelta
import mysql.connector
import bcrypt
import os


app = Flask(__name__)

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'user_database'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

app.secret_key = os.urandom(24)
data = {
    "accounts": [
        {"name": "", "card_number": "", "balance": ""},
    ],
    "transactions": [],
    "bills": [],
    "goals": []
}

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/home')
def home():
    try:
        if 'user_id' not in session:
            return redirect('/')

        user_id = session['user_id']
        name = session.get('name', 'User')  # Get user's name from session
        current_date = datetime.now().strftime("%B %d, %Y")

        cur = mysql.connection.cursor()

        cur.execute("""
                    SELECT category, SUM(amount) as total 
                    FROM transactions 
                    WHERE user_id = %s AND type = 'Debit' 
                    GROUP BY category
                """, (user_id,))
        expense_data = cur.fetchall()

        cur.execute("""
                    SELECT date, category, amount, type 
                    FROM transactions 
                    WHERE user_id = %s 
                    ORDER BY date DESC 
                    LIMIT 5
                """, (user_id,))
        recent_transactions = cur.fetchall()

        today = datetime.now().date()
        upcoming_days = 7
        cur.execute("""
                    SELECT name, due_date, amount 
                    FROM bills 
                    WHERE user_id = %s 
                    AND status = 'Unpaid' 
                    AND due_date BETWEEN %s AND %s
                    ORDER BY due_date ASC
                """, (user_id, today, today + timedelta(days=upcoming_days)))
        upcoming_bills = cur.fetchall()

        cur.execute("""
                    SELECT goal_name 
                    FROM goals 
                    WHERE user_id = %s AND status = 'Achieved'
                """, (user_id,))
        achieved_goals = [row['goal_name'] for row in cur.fetchall()]

        cur.close()
        categories = [row['category'] for row in expense_data]
        amounts = [float(row['total']) for row in expense_data]

        return render_template(
            'home.html',
            name=name,
            current_date=current_date,
            categories=categories,
            amounts=amounts,
            recent_transactions=recent_transactions,
            upcoming_bills=upcoming_bills,
            achieved_goals=achieved_goals
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/signup', methods=['POST'])
def signup():
    try:
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                    (name, email, hashed_password))
        mysql.connection.commit()
        cur.close()

        flash('Sign Up Successful! Please log in.', 'success')
        return redirect('/')

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/signin', methods=['POST'])
def signin():
    try:
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # Successful login
            session['user_id'] = user['id']
            session['name'] = user['name']
            return redirect('/home')
        else:
            flash('Invalid email or password!', 'error')
            return redirect('/')

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/balances")
def balances():
    try:
        user_id = session['user_id']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM accounts WHERE user_id = %s", (user_id,))
        accounts = cur.fetchall()
        cur.close()
        return render_template("balances.html", accounts=accounts)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/add_account", methods=["POST"])
def add_account():
    try:
        user_id = session['user_id']
        name = request.form["name"]
        card_number = request.form["card_number"]
        balance = float(request.form["balance"])

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO accounts (user_id, name, card_number, balance) VALUES (%s, %s, %s, %s)",
            (user_id, name, card_number, balance),
        )
        mysql.connection.commit()
        cur.close()

        flash("Account added successfully!", "success")
        return redirect(url_for("balances"))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/transaction")
def transactions():
    try:
        user_id = session['user_id']
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT id, name FROM accounts WHERE user_id = %s
        """, (user_id,))
        accounts = cur.fetchall()

        cur.execute("""
            SELECT t.*, a.name as account_name 
            FROM transactions t 
            JOIN accounts a ON t.account_id = a.id 
            WHERE a.user_id = %s
        """, (user_id,))
        transactions = cur.fetchall()

        cur.close()
        return render_template("transaction.html", transactions=transactions, accounts=accounts)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    try:
        user_id = session['user_id']
        account_id = request.form.get("account_id")
        amount = request.form.get("amount")
        t_type = request.form.get("type")
        category = request.form.get("category")
        date = request.form.get("date")

        print(f"Account ID: {account_id}, Amount: {amount}, Type: {t_type}, Category: {category}, Date: {date}")
        if not account_id or not amount or not t_type or not category or not date:
            raise ValueError("Missing required form fields")

        amount = float(amount)
        cur = mysql.connection.cursor()
        if t_type == "Debit":
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, account_id))
        else:
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, account_id))

        cur.execute(
            "INSERT INTO transactions (account_id, amount, type, category, date, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (account_id, amount, t_type, category, date, user_id)
        )
        mysql.connection.commit()
        cur.close()

        flash("Transaction added successfully!", "success")
        return redirect(url_for("transactions"))  # Redirect to 'transactions' page to reload the transactions list

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_upcoming_notifications(user_id):
    upcoming_days = 7
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("""
                SELECT name, due_date
                FROM bills
                WHERE user_id = %s AND status = 'Unpaid' AND due_date BETWEEN CURDATE() AND CURDATE() + INTERVAL %s DAY
            """, (user_id, upcoming_days))
            notifications = cur.fetchall()
        return notifications

    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return []

@app.route('/bills')
def bills():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    try:
        with mysql.connection.cursor() as cur:
            cur.execute("""
                SELECT id, name, amount, due_date, status
                FROM bills
                WHERE user_id = %s
                ORDER BY due_date ASC
            """, (user_id,))
            bills = cur.fetchall()

        notifications = get_upcoming_notifications(user_id)
        return render_template('bills.html', bills=bills, notifications=notifications)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_bill', methods=['POST'])
def add_bill():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    name = request.form['name']
    amount = request.form['amount']
    due_date = request.form['due_date']
    status = request.form['status']

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("""
                INSERT INTO bills (user_id, name, amount, due_date, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, name, amount, due_date, status))
            mysql.connection.commit()

        return redirect('/bills')

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_bill_status', methods=['POST'])
def update_bill_status():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access'}), 403

    data = request.json
    bill_id = data.get('id')

    try:
        with mysql.connection.cursor() as cur:
            cur.execute("""
                UPDATE bills
                SET status = 'Paid'
                WHERE id = %s AND user_id = %s
            """, (bill_id, session['user_id']))
            mysql.connection.commit()

        return jsonify({'success': 'Bill marked as Paid'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/expenses")
def expenses():
    try:
        user_id = session['user_id']
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT SUM(amount) AS total, type 
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY type
        """, (user_id,))
        transaction_totals = cur.fetchall()

        credit_total = 0
        debit_total = 0

        for total in transaction_totals:
            if total['type'] == 'Credit':
                credit_total = total['total']
            elif total['type'] == 'Debit':
                debit_total = total['total']

        cur.execute("""
            SELECT category, SUM(amount) AS total 
            FROM transactions 
            WHERE user_id = %s AND type = 'Debit' 
            GROUP BY category
        """, (user_id,))
        category_totals = cur.fetchall()

        cur.close()
        return render_template("expenses.html", credit_total=credit_total, debit_total=debit_total,
                               category_totals=category_totals)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/goals', methods=['GET', 'POST'])
def goals():
    cursor = mysql.connection.cursor()

    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    cursor.execute("SELECT SUM(balance) AS total_balance FROM accounts WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    total_balance = result['total_balance'] if result and result['total_balance'] is not None else 0

    if request.method == 'POST':
        goal_name = request.form['goal_name']
        target_amount = float(request.form['target_amount'])
        status = 'Achieved' if total_balance >= target_amount else 'Pending'

        cursor.execute("""
            INSERT INTO goals (user_id, goal_name, target_amount, status) 
            VALUES (%s, %s, %s, %s)
        """, (user_id, goal_name, target_amount, status))
        mysql.connection.commit()

    cursor.execute("SELECT id, goal_name, target_amount, status FROM goals WHERE user_id = %s", (user_id,))
    goals = cursor.fetchall()
    achieved_goals = []

    for goal in goals:
        current_status = 'Achieved' if total_balance >= goal['target_amount'] else 'Pending'
        if current_status == 'Achieved':
            achieved_goals.append(goal['goal_name'])

        cursor.execute("UPDATE goals SET status = %s WHERE id = %s", (current_status, goal['id']))

    mysql.connection.commit()
    cursor.close()

    return render_template('goals.html', goals=goals, notifications=achieved_goals)

if __name__ == '__main__':
    app.run(debug=True)