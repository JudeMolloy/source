import phonenumbers
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, FloatField
from wtforms.validators import DataRequired, EqualTo, Email, ValidationError, Length
from wtforms.widgets import TextArea
from app.models.user import User


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

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
        

class CreatePaymentLinkForm(FlaskForm):
    full_name = StringField('Customer Full Name*', validators=[DataRequired()])
    product_name = StringField('Product Name*', validators=[DataRequired()])
    size = StringField('Size*', validators=[DataRequired()])
    price = FloatField('Price*', validators=[DataRequired()])
    info = StringField('Info')

    submit = SubmitField('Send Payment Link')
    
