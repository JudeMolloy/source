import traceback

from flask import render_template, url_for, flash, request, session
from werkzeug.urls import url_parse
from werkzeug.utils import redirect
from app import app, db
from app.forms import LoginForm, RegistrationForm, RequestForm, CustomerForm
from flask_login import current_user, login_user, logout_user, login_required
from app.models import User, Confirmation, Request
from libs.email import MailgunException
from deorators import check_email_confirmed


@app.route('/')
def index():
        return render_template('buy.html', title='Home')


@app.route('/request',  methods = ['GET', 'POST'])
def request():
    form = RequestForm()

    if form.validate_on_submit():
        form_data = {
            'product_name': form.product_name.data,
            'size': form.size.data,
            'extra_info': form.extra_info.data,
        }
        session['product_request_data'] = form_data
        return redirect(url_for('details'))

    return render_template('request.html', form=form)


@app.route('/details', methods = ['GET', 'POST'])
def details():
    form = CustomerForm()

    if form.validate_on_submit():
        data = session['product_request_data']
        product_request = Request(
            product_name=data['product_name'],
            size=data['size'],
            extra_info=data['extra_info'],
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
        )
        print(product_request)
    return render_template('details.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password. Please try again.')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(forename=form.forename.data,
                        surname=form.surname.data,
                        email=form.email.data)
            user.set_password(form.password.data)
            user.save_to_db()

            # Send confirmation email.
            confirmation = Confirmation(user.id)
            confirmation.save_to_db()
            user.send_confirmation_email()

            flash('Account created successfully!')
            return redirect(url_for('login'))
        except MailgunException as e:
            user.delete_from_db()  # Must delete user as they won't be able to confirm account.
            flash('Error sending confirmation email.')
            return redirect(url_for('register'))
        except:
            traceback.print_exc()
            user.delete_from_db()
            flash('Error registering user.')
            return redirect(url_for('register'))
    return render_template('register.html', title='Register', form=form)


@app.route('/email-confirmation-sent')
@login_required
def email_confirmation_sent():
    name = current_user.full_name
    email = current_user.email

    return render_template("email-confirmation-sent.html")


@app.route('/email-confirmation-re-sent')
@login_required
def resend_email_confirmation():
    email = current_user.email
    current_user.send_confirmation_email()
    return render_template("email-confirmation-re-sent.html")


@app.route('/unconfirmed-email')
@login_required
def unconfirmed_email():
    email = current_user.email
    return render_template("unconfirmed-email.html")
