import traceback
import os

from flask import render_template, url_for, flash, request, session
from datetime import datetime
from werkzeug.urls import url_parse
from werkzeug.utils import redirect
from app import app, db
from app.forms import (
    LoginForm,
    RegistrationForm,
    RequestForm,
    CustomerForm,
    CreatePaymentLinkForm,
    CompanyForm,
    EmailConfirmationCodeForm, 
)
from flask_login import current_user, login_user, logout_user, login_required
from app.models.user import User
from app.models.confirmation import Confirmation
from app.models.request import Request
from app.models.company import Company
from app.models.usage_period import UsagePeriod
from app.models.payment_link import PaymentLink
from app.models.order import Order
from libs.email import MailgunException, Email
from libs.otp import OTP
from libs.upload import upload_file_to_bucket
from deorators import check_email_confirmed
from sqlalchemy import desc, asc

AWS_COMPANY_LOGOS_FOLDER = os.environ.get('AWS_COMPANY_LOGOS_FOLDER')
AWS_PRODUCT_IMG_FOLDER = os.environ.get('AWS_PRODUCT_IMG_FOLDER')
ITEMS_PER_PAGE = 10

# HELPER FUNCTIONS

def company_access(user_id, company_endpoint):
    company = Company.find_company_by_endpoint(company_endpoint)

    if company:
        # check if company is related to current user
        if company.user.id == user_id:
            return company

    return False

def is_company(company_endpoint):
    company = Company.find_company_by_endpoint(company_endpoint)

    if company:
            return company

    return False


@app.route('/')
def index():
    form = RegistrationForm()
    return render_template('landing/landing.html', form=form)


@app.route('/<company_endpoint>',  methods = ['GET', 'POST'])
def request_item(company_endpoint):
    company = is_company(company_endpoint)
    if company:
        form = RequestForm()

        if form.validate_on_submit():
            form_data = {
                'product_name': form.product_name.data,
                'size': form.size.data,
                'extra_info': form.extra_info.data,
            }
            session['product_request_data'] = form_data
            return redirect(url_for('details', company_endpoint=company_endpoint))

        return render_template('request.html', form=form, company=company)
    else:
        return render_template("errors/404.html")


@app.route('/<company_endpoint>/details', methods = ['GET', 'POST'])
def details(company_endpoint):
    company = Company.find_company_by_endpoint(company_endpoint)
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
            company_id=company.id,
        )
        product_request.save_to_db()
        return redirect(url_for('request_complete', company_endpoint=company_endpoint))

    return render_template('details.html', form=form, company=company)


@app.route('/<company_endpoint>/request-complete')
def request_complete(company_endpoint):
    company = is_company(company_endpoint)
    if company:
        return render_template('request-complete.html', company=company)
    return render_template("errors/404.html")


@app.route('/<company_endpoint>/<payment_link_id>')
def payment_link(company_endpoint, payment_link_id):
    company = is_company(company_endpoint)
    if company:
        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        if payment_link.expired:
            return render_template('offer-expired.html', company=company) 
        if company.accept_cash:
            if payment_link.deposit_percentage != 0 and not None:
                cash_payment_status = "available with {}% deposit".format(payment_link.deposit_percentage)
            else:
                cash_payment_status = "available"
        else:
            cash_payment_status = "unavailable"
        #print(datetime.fromtimestamp(payment_link.expire_at / 1e3))
        #expiry_date = datetime.fromtimestamp(payment_link.expire_at / 1e3).strftime('%d %b %Y')
        #print(expiry_date)

        return render_template('buy.html', company=company, payment_link=payment_link, cash_payment_status=cash_payment_status)
    return render_template("errors/404.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
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
                        phone=form.phone.data,
                        email=form.email.data)
            user.set_password(form.password.data)
            user.save_to_db()

            # Send confirmation email.
            confirmation = Confirmation(user.id)
            confirmation.save_to_db()
            user.send_confirmation_email()
            login_user(user, remember=False)

            flash('Account created successfully!')
            return redirect(url_for('email_confirmation_sent'))
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


@app.route('/email-confirmation-sent', methods = ['GET', 'POST'])
@login_required
def email_confirmation_sent():
    status = False
    name = current_user.forename
    email = current_user.email

    resend = request.args.get('resend')
    unconfirmed = request.args.get('unconfirmed')
    print(resend)
    if unconfirmed == "true":
        message1 = "You must confirm your email to access this page."
        message2 = "If you still have not recieved a confirmation code via email please contact support."
    elif resend == "true":
        if current_user.has_reached_confirmation_limit():
            message1 = "We have already sent multiple confirmation emails."
            message2 = "If you still have not recieved a confirmation code via email please contact support."
        else:  
            # resend the email
            current_user.send_confirmation_email()
            message1 = "A new email has been sent to {}. Please enter the code below to verify your account.".format(email)
    else: 
        message1 = "Thanks for creating an account {}!".format(name)
        message2 = "A confirmation code has been sent to {}. Please enter the code below to verify your account.".format(email)
    
    form = EmailConfirmationCodeForm()

    if form.validate_on_submit():
        confirmation = current_user.most_recent_confirmation
        otp = confirmation.otp
        if form.otp.data == otp:
            confirmation.confirmed = True
            return redirect(url_for('create_company'))
        else:
            status = True
    return render_template("email-confirmation-sent.html", form=form, message1=message1, message2=message2, incorrect=status)



@app.route('/email-confirmation-re-sent')
@login_required
def resend_email_confirmation():
    # resend the email
    if current_user.has_reached_confirmation_limit():
        message1 = "We have already sent multiple confirmation emails."
        message2 = "Please wait 10 minutes to recieve the confirmation email."
    else:  
        current_user.send_confirmation_email()

    status = False
    name = current_user.full_name
    email = current_user.email
    form = EmailConfirmationCodeForm()

    if form.validate_on_submit():
        confirmation = current_user.most_recent_confirmation
        otp = confirmation.otp
        if form.otp.data == otp:
            confirmation.confirmed = True
            return redirect(url_for('create_company'))
        else:
            status = True
    return render_template("email-confirmation-re-sent.html", form=form, name=name, email_address=email, incorrect=status)


@app.route('/unconfirmed-email')
def unconfirmed_email():
    satus=False
    name = current_user.full_name
    email = current_user.email
    form = EmailConfirmationCodeForm()

    if form.validate_on_submit():
        confirmation = current_user.most_recent_confirmation
        otp = confirmation.otp
        if form.otp.data == otp:
            confirmation.confirmed = True
            return redirect(url_for('create_company'))
        else:
            status = True
    return render_template("email-confirmation-sent.html", form=form, name=name, email_address=email, incorrect=status)


@app.route('/create-company', methods = ['GET', 'POST'])
@login_required
def create_company():
    # check if user has already created a company.
    user = User.query.filter_by(id=current_user.id).first()
    company = Company.query.filter_by(user=user).first()
    if company:
        return redirect(url_for('company_settings', company_endpoint=company.endpoint))
    
    form = CompanyForm()

    if form.validate_on_submit():
        company = Company(
            name=form.name.data,
            endpoint=form.endpoint.data,
            accept_cash=form.accept_cash.data,
            twitter_url=form.twitter_url.data,
            facebook_url=form.facebook_url.data,
            instagram_url=form.instagram_url.data,
            user=current_user,
            )
        company_logo = request.files["file"]
        if company_logo:
            try:
                company_logo_url = upload_file_to_bucket(company_logo, AWS_COMPANY_LOGOS_FOLDER)
            except:
                traceback.print_exc()
                return render_template("errors/500.html")

            company.logo_url = company_logo_url

        company.save_to_db()
        return redirect(url_for('company_settings', company_endpoint=company.endpoint))
        
    return render_template("create-company.html", form=form)


# ADMIN ROUTES (SAAS CUSTOMERS NOT MASTERO EMPLOYEES)

@app.route('/<company_endpoint>/admin/requests')
@login_required
def company_requests(company_endpoint):
    company = company_access(current_user.id, company_endpoint)
    if company:
        page = request.args.get('page', 1, type=int)
        requests = Request.query.filter_by(company_id=company.id).order_by(Request.datetime.desc()).paginate(
        page, ITEMS_PER_PAGE, False)
        print(requests.total)
        next_url = url_for('company_requests', company_endpoint=company.endpoint, page=requests.next_num) if requests.has_next else None
        prev_url = url_for('company_requests', company_endpoint=company.endpoint, page=requests.prev_num) if requests.has_prev else None
        print(requests)
        from_number = ((page - 1) * ITEMS_PER_PAGE) + 1
        to_number = min((page * ITEMS_PER_PAGE), requests.total)

        return render_template("admin/requests.html", company=company, requests=requests.items,
         prev_url=prev_url, next_url=next_url, total_requests=requests.total, from_number=from_number,
          to_number=to_number)

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/request/<request_id>')
@login_required
def company_request(company_endpoint, request_id):
    company = company_access(current_user.id, company_endpoint)
    if company:

        request = Request.query.filter_by(company_id=company.id, id=request_id).first_or_404()
        return render_template("admin/request.html", company=company, request=request)

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/request/<request_id>/could-not-source')
@login_required
def company_could_not_source_request(company_endpoint, request_id):
    company = company_access(current_user.id, company_endpoint)
    if company:

        request = Request.query.filter_by(company_id=company.id, id=request_id).first_or_404()
        request.could_not_source()
        request.save_to_db()
        return redirect(url_for('company_request', company_endpoint=company.endpoint, request_id=request.id))

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/settings', methods = ['GET', 'POST'])
@login_required
def company_settings(company_endpoint):
    company = company_access(current_user.id, company_endpoint)

    if company:
        form = CompanyForm(obj=company)

        if form.validate_on_submit():
            company.name=form.name.data
            company.endpoint=form.endpoint.data
            company.accept_cash=form.accept_cash.data
            company.twitter_url=form.twitter_url.data
            company.facebook_url=form.facebook_url.data
            company.instagram_url=form.instagram_url.data

            company_logo = request.files["file"]
            if company_logo:
                try:
                    company_logo_url = upload_file_to_bucket(company_logo, AWS_COMPANY_LOGOS_FOLDER)
                except:
                    traceback.print_exc()
                    return render_template("errors/500.html")

                company.logo_url = company_logo_url

            company.save_to_db()
            return redirect(url_for('company_requests', company_endpoint=company.endpoint))
            
        return render_template("admin/settings.html", form=form, company=company)
    return render_template("errors/404.html")



@app.route('/<company_endpoint>/admin/account-settings')
@login_required
def company_account_settings(company_endpoint):
    # code to find the relevant company and display only their information if the user matches it

    return render_template("admin/account-settings.html")


@app.route('/<company_endpoint>/admin/payment-links')
@login_required
def company_payment_links(company_endpoint):
    company = company_access(current_user.id, company_endpoint)
    if company:
        payment_links = PaymentLink.query.filter_by(company_id=company.id).all()
        print(payment_links)
        return render_template("admin/payment-links.html", company=company, payment_links=payment_links)

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/payment-link/<payment_link_id>')
@login_required
def company_payment_link(company_endpoint, payment_link_id):
    company = company_access(current_user.id, company_endpoint)
    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        return render_template("admin/payment-link.html", company=company, payment_link=payment_link)

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/delete-payment-link/<payment_link_id>')
@login_required
def company_delete_payment_link(company_endpoint, payment_link_id):
    company = company_access(current_user.id, company_endpoint)
    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()
        payment_link.delete_from_db()
        return redirect(url_for('company_payment_links', company_endpoint=company_endpoint))

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/create-payment-link/<request_id>', methods = ['GET', 'POST'])
@login_required
def company_create_payment_link(company_endpoint, request_id):
    company = company_access(current_user.id, company_endpoint)

    if company:

        product_request = Request.query.filter_by(company_id=company.id, id=request_id).first_or_404()

        form = CreatePaymentLinkForm()

        form.customer_full_name.data = product_request.full_name
        form.product_name.data = product_request.product_name
        form.size.data = product_request.size 

        if form.validate_on_submit():

            payment_link = PaymentLink(
                customer_full_name=form.customer_full_name.data,
                product_name=form.product_name.data,
                size=form.size.data,
                price=form.price.data,
                info=form.info.data,
                deposit_percentage=form.deposit_percentage.data,
                company_id=company.id,
                request_id=product_request.id
                )
            product_image = request.files["file"]
            if product_image:
                try:
                    product_image_url = upload_file_to_bucket(product_image, AWS_PRODUCT_IMG_FOLDER)
                except:
                    traceback.print_exc()
                    return render_template("errors/500.html")

                payment_link.product_image_url = product_image_url

            payment_link.save_to_db()

            # send sms text message and email.

            # set request to sourced.
            product_request.product_sourced()
            product_request.save_to_db()

            return redirect(url_for('company_payment_links', company_endpoint=company.endpoint))

        return render_template("admin/create-payment-link.html", form=form, company=company)
    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/edit-payment-link/<payment_link_id>', methods = ['GET', 'POST'])
@login_required
def company_edit_payment_link(company_endpoint, payment_link_id):
    company = company_access(current_user.id, company_endpoint)

    if company:

        payment_link = PaymentLink.query.filter_by(company_id=company.id, id=payment_link_id).first_or_404()

        form = CreatePaymentLinkForm(obj=payment_link)

        if form.validate_on_submit():

            payment_link.customer_full_name=form.customer_full_name.data
            payment_link.product_name=form.product_name.data
            payment_link.size=form.size.data
            payment_link.price=form.price.data
            payment_link.info=form.info.data
            payment_link.deposit_percentage=form.deposit_percentage.data
            
            product_image = request.files["file"]
            if product_image:
                try:
                    product_image_url = upload_file_to_bucket(product_image, AWS_PRODUCT_IMG_FOLDER)
                except:
                    traceback.print_exc()
                    return render_template("errors/500.html")

                payment_link.product_image_url = product_image_url

            payment_link.save_to_db()
            return redirect(url_for('company_payment_links', company_endpoint=company.endpoint))

        return render_template("admin/edit-payment-link.html", form=form, company=company, payment_link=payment_link)
    return render_template("errors/404.html")

# COMPANY ORDERS

@app.route('/<company_endpoint>/admin/orders')
@login_required
def company_orders(company_endpoint):
    company = company_access(current_user.id, company_endpoint)
    if company:
        orders = Order.query.filter_by(company_id=company.id).all()
        print(orders)
        return render_template("admin/orders.html", company=company, orders=orders)

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/order/<order_id>')
@login_required
def company_order(company_endpoint, order_id):
    company = company_access(current_user.id, company_endpoint)
    if company:

        order = Order.query.filter_by(company_id=company.id, id=order_id).first_or_404()
        return render_template("admin/order.html", company=company, order=order)

    return render_template("errors/404.html")