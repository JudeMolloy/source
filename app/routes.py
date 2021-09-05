import traceback
import os

from flask import render_template, url_for, flash, request, session
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
from libs.email import MailgunException, Email
from libs.otp import OTP
from libs.upload import upload_file_to_bucket
from deorators import check_email_confirmed

AWS_COMPANY_LOGOS_FOLDER = os.environ.get('AWS_COMPANY_LOGOS_FOLDER')
AWS_PRODUCT_IMG_FOLDER = os.environ.get('AWS_PRODUCT_IMG_FOLDER')

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
        return render_template('buy.html', title='Home')


@app.route('/<company_endpoint>/request',  methods = ['GET', 'POST'])
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
        print(payment_link)
        return render_template('buy.html', company=company, payment_link=payment_link)
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
        return redirect(url_for('company_requests', company_endpoint=company.endpoint))
        
    return render_template("create-company.html", form=form)



# ADMIN ROUTES (SAAS CUSTOMERS NOT MASTERO EMPLOYEES)

@app.route('/<company_endpoint>/admin/requests')
@login_required
def company_requests(company_endpoint):
    company = company_access(current_user.id, company_endpoint)
    if company:
        requests = Request.query.filter_by(company_id=company.id).all()
        print(requests)
        return render_template("admin/requests.html", company=company, requests=requests)

    return render_template("errors/404.html")


@app.route('/<company_endpoint>/admin/request/<request_id>')
@login_required
def company_request(company_endpoint, request_id):
    company = company_access(current_user.id, company_endpoint)
    if company:

        request = Request.query.filter_by(company_id=company.id, id=request_id).first_or_404()
        return render_template("admin/request.html", company=company, request=request)

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
def company_account_settings(company_endpoint):
    # code to find the relevant company and display only their information if the user matches it

    return render_template("admin/account-settings.html")


@app.route('/<company_endpoint>/admin/payment_links')
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


@app.route('/<company_endpoint>/admin/create-payment-link/<request_id>')
def company_create_payment_link(company_endpoint, request_id):
    company = company_access(current_user.id, company_endpoint)

    if company:

        request = Request.query.filter_by(company_id=company.id, id=request_id).first_or_404()

        form = CreatePaymentLinkForm()

        form.customer_full_name.data = request.full_name
        form.product_name.data = request.product_name
        form.size.data = request.size 

        if form.validate_on_submit():
            payment_link = PaymentLink(
                customer_full_name=form.customer_full_name.data,
                product_name=form.product_name.data,
                size=form.size.data,
                price=form.price.data,
                info=form.info.data,
                deposit_percentage=form.deposit_percentage.data,
                company_id=company.id,
                )
            product_image = request.files["file"]
            if product_image:
                try:
                    product_image_url = upload_file_to_bucket(company_logo, AWS_PRODUCT_IMG_FOLDER)
                except:
                    traceback.print_exc()
                    return render_template("errors/500.html")

                payment_link.product_image_url = product_image_url

            payment_link.save_to_db()
            return redirect(url_for('company_payment_links', company_endpoint=company.endpoint))

        return render_template("admin/create-payment-link.html", form=form, company=company)
    return render_template("errors/404.html")


@app.route('/test')
def test():
    otp = OTP.generate(6)
    subject = "Email Confirmation - Mastero"
    text = "Your one time password is: {}".format(otp)
    html = '<html>Your account confirmation code is: {}<p>This code will expire in 30 minutes.</p></html>'.format(otp)

    test = Email.send_email(['judemolloy07@hotmail.com'], subject, text, html)

    print(test)
    return("ok nice.")

