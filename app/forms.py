import phonenumbers
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, FloatField
from wtforms.fields.html5 import TelField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError, Length, NumberRange, Optional
from wtforms.widgets import TextArea
from app.models.user import User
from flask_login import current_user


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    forename = StringField('First Name*', validators=[DataRequired()])
    surname = StringField('Last Name*', validators=[DataRequired()])
    email = StringField('Email*', validators=[DataRequired(), Email()])
    phone = StringField('Phone*', validators=[DataRequired(), Length(max=16)])
    password = PasswordField('Password*', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password*', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_phone(self, phone):
        try:
            p = phonenumbers.parse(phone.data)
            if not phonenumbers.is_valid_number(p):
                raise ValueError()
        except (phonenumbers.phonenumberutil.NumberParseException, ValueError):
            raise ValidationError('Invalid phone number')
        
        user = User.query.filter_by(phone=phone.data).first()
        if user is not None and user != current_user:
            raise ValidationError('Please use a different phone number.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')


class RequestForm(FlaskForm):
    product_name = StringField('Name of Product*', validators=[DataRequired()])
    size = StringField('Size*', validators=[DataRequired()])
    extra_info = StringField('Extra Information', widget=TextArea())
    submit = SubmitField('Continue')


class CustomerForm(FlaskForm):
    full_name = StringField('Full Name*', validators=[DataRequired(),  Length(max=64)])
    email = StringField('Email*', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone*', validators=[DataRequired(), Length(max=16)])

    submit = SubmitField('Send Request')

    def validate_phone(self, phone):
        try:
            p = phonenumbers.parse(phone.data)
            if not phonenumbers.is_valid_number(p):
                raise ValueError()
        except (phonenumbers.phonenumberutil.NumberParseException, ValueError):
            
            raise ValidationError('Invalid phone number')


class CompanyForm(FlaskForm):
    name = StringField('Company Name*', validators=[DataRequired()])
    endpoint = StringField('Custom Link*', validators=[DataRequired()])

    accept_cash = BooleanField('Accept Cash Payments')

    twitter_url = StringField('Twitter Link')
    facebook_url = StringField('Facebook Link')
    instagram_url = StringField('Instagram Link')

    submit = SubmitField('Save')

    def validate_endpoint(self, endpoint):
        company = Company.query.filter_by(endpoint=endpoint.data).first()
        if company is not None:
            raise ValidationError('mastero.co/{} is already taken. Please use a different endpoint.'.format(endpoint.data))


class CreatePaymentLinkForm(FlaskForm):
    customer_full_name = StringField('Customer Full Name*', validators=[DataRequired()])
    product_name = StringField('Product Name*', validators=[DataRequired()])
    size = StringField('Size*', validators=[DataRequired()])
    price = FloatField('Price*', validators=[DataRequired()])
    info = StringField('Info')

    deposit_percentage = FloatField('Deposit Percentage', validators=[Optional(), NumberRange(min=5, max=99)])

    submit = SubmitField('Send Payment Link')
    

class EmailConfirmationCodeForm(FlaskForm):
    otp = TelField('Enter Code', validators=[DataRequired(), Length(max=6)])
    submit = SubmitField('Continue')


class BillingInfoForm(FlaskForm):
    full_name = StringField('Full Name*', validators=[DataRequired()])
    email = StringField('Email*', validators=[DataRequired(), Email(),  Length(max=120)])
    address1 = StringField('Address 1*', validators=[DataRequired(),  Length(max=128)])
    address2 = StringField('Address 2', validators=[Length(max=128)])
    city = StringField('City/Town*', validators=[DataRequired(),  Length(max=100)])
    country = StringField('Country*', validators=[DataRequired(),  Length(max=64)])
    postcode = StringField('Postcode*', validators=[DataRequired(),  Length(max=16)])
    submit = SubmitField('Continue')