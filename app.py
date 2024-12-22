from flask import Flask, render_template, request, redirect, jsonify, session, flash, url_for
from flask_mysqldb import MySQL
from datetime import datetime
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

# Secret key for session management
app.secret_key = os.urandom(24)

data = {
    "accounts": [
        {"name": "", "card_number": "", "balance": ""},
    ],
    "transactions": [],
    "bills":[]
}
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/home')
def home():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return redirect('/')

        user_id = session['user_id']
        name = session.get('name', 'User')  # Get user's name from session
        current_date = datetime.now().strftime("%B %d, %Y")

        # Check if the user already has a card
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM cards WHERE user_id = %s", (user_id,))
        card = cur.fetchone()
        cur.close()

        has_card = card is not None
        return render_template('home.html', name=name, current_date=current_date, has_card=has_card)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/signup', methods=['POST'])
def signup():
    try:
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Insert user into the database
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

        # Check user in the database
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
    return render_template("balances.html", accounts=data["accounts"])


@app.route("/add_account", methods=["POST"])
def add_account():
    name = request.form["name"]
    card_number = request.form["card_number"]
    balance = float(request.form["balance"])
    data["accounts"].append({"name": name, "card_number": card_number, "balance": balance})
    return redirect(url_for("balances"))


@app.route("/transaction")
def transactions():
    return render_template("transaction.html", accounts=data["accounts"], transactions=data["transactions"])


@app.route("/add_transaction", methods=["POST"])
def add_transaction():
    account = request.form["account"]
    amount = float(request.form["amount"])
    t_type = request.form["type"]
    category = request.form["category"]
    date = request.form["date"]

    # Update balance
    for acc in data["accounts"]:
        if acc["name"] == account:
            if t_type == "Debit":
                acc["balance"] -= amount
            else:
                acc["balance"] += amount

    data["transactions"].append(
        {"account": account, "amount": amount, "type": t_type, "category": category, "date": date})
    return redirect(url_for("transactions"))

@app.route("/bills")
def bills():
    return render_template("bills.html", bills=data["bills"])


@app.route("/add_bill", methods=["POST"])
def add_bill():
    name = request.form["name"]
    amount = float(request.form["amount"])
    due_date = request.form["due_date"]
    status = request.form["status"]

    data["bills"].append(
        {"name": name, "amount": amount, "due_date": due_date, "status": status}
    )

    return redirect(url_for("bills"))

if __name__ == '__main__':
    app.run(debug=True)