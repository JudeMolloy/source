from flask import url_for, request, render_template

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db, login
from libs.email import Email
from app.models.payment_link import PaymentLink
from app.models.confirmation import Confirmation
from app.models.usage_period import UsagePeriod
from libs.otp import OTP


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    forename = db.Column(db.String(64), index=True)
    surname = db.Column(db.String(64), index=True)

    email = db.Column(db.String(120), index=True, unique=True)
    phone = db.Column(db.String(16), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    plan = db.Column(db.String(16), default='none')

    stripe_customer_id = db.Column(db.String(64), index=True)
    stripe_subscription_id = db.Column(db.String(64), index=True)
    stripe_connected_account_id = db.Column(db.String(64), index=True)

    stripe_connect_details_submitted = db.Column(db.Boolean, default=False, nullable=False)
    stripe_connect_charges_enabled = db.Column(db.Boolean, default=False, nullable=False)

    # one-to-many relationship with confirmation.
    confirmations = db.relationship("Confirmation", lazy="dynamic", cascade="all, delete-orphan")

    # one-to-many relationship with usage period.
    usage_periods = db.relationship("UsagePeriod", lazy="dynamic", cascade="all, delete-orphan")

    # one-to-one relationship with company.
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))

    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return '<User: {} {}>'.format(self.forename, self.surname)

    @property
    def full_name(self):
        return self.forename + " " + self.surname

    @property
    def active_membership(self):
        if self.most_recent_usage_period:
            return self.most_recent_usage_period.is_active
        return False

    @property
    def most_recent_confirmation(self):
        return self.confirmations.order_by(db.desc(Confirmation.expire_at)).first()

    @property
    def has_reached_confirmation_limit(self):
        confirmations = self.confirmations.order_by(db.desc(Confirmation.expire_at)).filter_by(expired=False).all()
        if len(confirmations) >= 2:
            return True
        return False

    @property
    def is_confirmed(self):
        return self.most_recent_confirmation.confirmed

    @property
    def most_recent_usage_period(self):
        return self.usage_periods.order_by(db.desc(UsagePeriod.end)).first()
    
    def update_subscription(self, term):
        usage_period = UsagePeriod(term=term, user_id=self.id)
        usage_period.save_to_db()

    def end_subscription(self):
        self.most_recent_usage_period.force_end()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def send_confirmation_email(self):
        otp = self.most_recent_confirmation.otp
        subject = "Email Confirmation Code - Mastero"
        text = "Your one time password is: {}".format(otp)
        html = render_template('email/confirmation-code.html', otp=otp)

        return Email.send_email([self.email], subject, text, html)

    @classmethod
    def find_by_email(cls, email: str):
        return cls.query.filter_by(email=email).first()

    @classmethod
    def find_by_stripe_subscription_id(cls, stripe_subscription_id: str):
        return cls.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()

    @classmethod
    def find_by_stripe_connected_account_id(cls, stripe_connected_account_id: str):
        return cls.query.filter_by(stripe_connected_account_id=stripe_connected_account_id).first()

    @classmethod
    def find_by_id(cls, _id: int):
        return cls.query.filter_by(id=_id).first()

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()
