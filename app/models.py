from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db, login
from libs.email import Mailgun

CONFIRMATION_EXPIRATION_DELTA = 1800  # 30 minutes (in seconds).


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    confirmations = db.relationship("Confirmation", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return '<User: {} {}>'.format(self.forename, self.surname)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def most_recent_confirmation(self):
        return self.confirmations.order_by(db.desc(Confirmation.expire_at)).first()

    @property
    def is_confirmed(self):
        return self.most_recent_confirmation.confirmed

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


class Confirmation(db.Model):
    __tablename__ = "confirmations"

    id = db.Column(db.String(50), primary_key=True)
    expire_at = db.Column(db.Integer, nullable=False)
    confirmed = db.Column(db.Boolean(create_constraint=False), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User")

    def __init__(self, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self.id = uuid4().hex
        self.expire_at = int(time()) + CONFIRMATION_EXPIRATION_DELTA
        self.confirmed = False
        self.user_id = user_id

    @classmethod
    def find_by_id(cls, _id: str):
        return cls.query.filter_by(id=_id).first()

    @property
    def expired(self):
        return time() > self.expire_at  # True if the confirmation has expired.

    def force_expire(self):
        if not self.expired:
            self.expire_at = int(time())
            self.save_to_db()

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()