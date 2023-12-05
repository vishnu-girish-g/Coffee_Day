from flask import Flask, flash, render_template, request, redirect, send_from_directory, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI')
db = SQLAlchemy()
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


class User(UserMixin, db.Model):
    id = db.Column(db.INTEGER, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(50), nullable=False)


class Coffee(db.Model):
    coffee_id = db.Column(db.INTEGER, primary_key=True)
    coffee_type = db.Column(db.String(50), nullable=False)
    milk_ml = db.Column(db.Integer, nullable=False)
    water_ml = db.Column(db.Integer, nullable=False)
    coffee_ml = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)


class Resources(db.Model):
    resource_id = db.Column(db.INTEGER, primary_key=True)
    milk_stock = db.Column(db.Integer, nullable=False)
    water_stock = db.Column(db.Integer, nullable=False)
    coffee_stock = db.Column(db.Integer, nullable=False)
    balance = db.Column(db.Float, nullable=False)


with app.app_context():
    db.create_all()


# HOME_PAGE
@app.route('/')
def home():
    return render_template("home.html")


# REGISTER PAGE
@app.route('/sign_up', methods=['POST', 'GET'])
def sign_up():
    if request.method == 'POST':
        username = request.form['uname']
        email = request.form['email']
        password = request.form['pass']

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already taken', 'error')
        else:
            hash_pass = generate_password_hash(password, method='pbkdf2:sha256', salt_length=5)
            new_user = User(username=username, email=email, password=hash_pass)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)

            return render_template("welcome.html", name=username.upper())
    return render_template("sign_up.html")


# LOGIN PAGE
@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    username = request.form.get('username')
    password = request.form.get('password')

    result = db.session.execute(db.select(User).where(User.username == username))
    user = result.scalar()
    # user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        return redirect(url_for('welcome'))
    else:
        flash("Invalid username or password")
    return render_template("login.html")


@app.route('/welcome')
@login_required
def welcome():
    return render_template("welcome.html", name=current_user.username)


@app.route('/coffee', methods=['POST', 'GET'])
@login_required
def coffee():
    if request.method == 'POST':
        coffee_type = request.form.get('coffee_type')
        return handle_coffee_type(coffee_type)
    return render_template("welcome.html")


def handle_coffee_type(coffee_type):
    if coffee_type in {'espresso', 'latte', 'cappuccino'}:
        if has_enough_resources(coffee_type):
            session['coffee_name'] = coffee_type
            return redirect(url_for("payment"))
        else:
            return "OUT OF STOCK"


def has_enough_resources(coffee_name):
    coffee_resources = db.session.query(Coffee).filter_by(coffee_type=coffee_name).first()

    if coffee_resources:
        available_resources = db.session.query(Resources).first()
        if (
                available_resources.milk_stock >= coffee_resources.milk_ml and
                available_resources.coffee_stock >= coffee_resources.coffee_ml and
                available_resources.water_stock >= coffee_resources.water_ml
        ):
            return True
        else:
            return False


@app.route('/payment', methods=["GET", "POST"])
@login_required
def payment():
    if request.method == 'POST':
        coffee_name = session.get('coffee_name')
        quarter = request.form.get('quarter')
        dime = request.form.get('dimes')
        nickel = request.form.get('nickels')
        penny = request.form.get('pennies')
        total_amount_inserted = (int(quarter) * 0.25) + (int(dime) * 0.10) + (int(nickel) * 0.05) + (int(penny) * 0.01)
        coffee = Coffee.query.filter_by(coffee_type=coffee_name).first()
        change = 0
        if total_amount_inserted > coffee.amount:
            change = total_amount_inserted - coffee.amount
        elif total_amount_inserted < coffee.amount:
            short = coffee.amount - total_amount_inserted
            return redirect("unsuccess.html")
        if update_resources(coffee_name):
            session['change'] = change
            session[coffee_name] = coffee_name
            return redirect(url_for("success"))
    return render_template('payment.html')


def update_resources(coffee_name):
    coffee = Coffee.query.filter_by(coffee_type=coffee_name).first()
    resources = Resources.query.first()
    if coffee and resources:
        if resources.milk_stock > 0 and resources.water_stock > 0 and resources.coffee_stock > 0:
            resources.milk_stock -= coffee.milk_ml
            resources.coffee_stock -= coffee.coffee_ml
            resources.water_stock -= coffee.water_ml
            resources.balance += coffee.amount
            db.session.commit()
            return True
        else:
            return "Restock required"


@app.route('/success')
def success():
    change = session.get('change')
    return render_template("success.html", change=change)


# logout
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/add-res")
def add_resources():
    milk = int(request.args.get('milk', 0))
    water = int(request.args.get('water', 0))
    coffee = int(request.args.get('coffee', 0))
    balance = float(request.args.get('balance', 0.0))

    resources = db.session.query(Resources).first()

    if resources:
        resources.milk_stock += milk
        resources.water_stock += water
        resources.coffee_stock += coffee
        resources.balance += balance
    else:
        new_resources = Resources(
            milk_stock=milk,
            water_stock=water,
            coffee_stock=coffee,
            balance=balance
        )
        db.session.add(new_resources)
    db.session.commit()
    return redirect(url_for('report'))


@app.route('/add-drink')
def add_drink():
    name = request.args.get('name')
    water = request.args.get('water')
    milk = request.args.get('milk')
    coffee = request.args.get('coffee')
    money = request.args.get('money')
    new_drink = Coffee(
        coffee_type=name,
        water_ml=water,
        milk_ml=milk,
        coffee_ml=coffee,
        amount=money
    )
    db.session.add(new_drink)
    db.session.commit()
    flash("Drink added successfully!")
    return redirect(url_for('home'))


@app.route('/report')
def report():
    resources = Resources.query.first()
    if resources:
        amount = resources.balance
        milk = resources.milk_stock
        water = resources.water_stock
        coffee = resources.coffee_stock
        return render_template("report.html", milk=milk, coffee=coffee, water=water, amount=amount)
    else:
        return "No resources found in the database"


if __name__ == "__main__":
    app.run(debug=True, port=5006)
