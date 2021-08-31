from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db, login
from libs.email import Mailgun


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    plan = db.Column(db.String(16), default='none')

    # one-to-many relationship with confirmation.
    confirmations = db.relationship("Confirmation", lazy="dynamic", cascade="all, delete-orphan")
    
    # one-to-many relationship with confirmation.
    payment_links = db.relationship("PaymentLink", lazy="dynamic", cascade="all, delete-orphan")

    # one-to-many relationship with usage period.
    usage_periods = db.relationship("UsagePeriod", lazy="dynamic", cascade="all, delete-orphan")

    # one-to-one relationship with company.
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)

    def __repr__(self):
        return '<User: {} {}>'.format(self.forename, self.surname)

    @property
    def active_subscription(self):
        return self.plan != 'none'

    @property
    def most_recent_confirmation(self):
        return self.confirmations.order_by(db.desc(Confirmation.expire_at)).first()

    @property
    def is_confirmed(self):
        return self.most_recent_confirmation.confirmed

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def send_confirmation_email(self):
        link = request.url_root[:-1] + url_for("confirmation", confirmation_id=self.most_recent_confirmation.id)
        subject = "Email Confirmation - Mastero"
        text = "Click the link to confirm your account: {}".format(link)
        html = '<html><a href="{}">Click here to confirm account</a><p>This link will expire in 30 minutes.</p></html>'.format(link)

        return Mailgun.send_email([self.email], subject, text, html)

    @classmethod
    def find_by_email(cls, email: str):
        return cls.query.filter_by(email=email).first()

    @classmethod
    def find_by_id(cls, _id: int):
        return cls.query.filter_by(id=_id).first()

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()
