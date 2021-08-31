from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from app import app, db, login


class Request(db.Model):
    __tablename__ = "requests"

    id = db.Column(db.Integer, primary_key=True)

    # request part
    product_name = db.Column(db.String(128), index=True)
    size = db.Column(db.String(64))
    extra_info = db.Column(db.String)

    # customer part
    full_name = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(16), index=True)

    sourced = db.Column(db.Boolean, default=False, nullable=False)

    # one-to-one relationship with payment link.
    payment_link = db.relationship('PaymentLink', backref='request', lazy=True, uselist=False)

    # generates a unique payment link.
    def generate_payment_link(self):
        pass

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()

