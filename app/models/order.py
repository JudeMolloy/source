from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from app import app, db, login


PAYMENT_LINK_EXPIRATION_DELTA = 604800  # 7 days (in seconds). Could possibly make this customisable.


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.String(50), primary_key=True)

    completion_datetime = db.Column(db.DateTime)

    paid = db.Column(db.Boolean, default=False, nullable=False)
    deposit = db.Column(db.Boolean, default=False, nullable=False)

    customer_full_name = db.Column(db.String(128))



    # many-to-one relationship with company.
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False) 

    # one-to-one relationship with payment link.
    payment_link_id = db.Column(db.Integer, db.ForeignKey('payment_links.id'), nullable=True)


    # ensure when generating link that the correct company url is used.
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = uuid4().hex

    @property
    def expired(self):
        return time() > self.expire_at  # True if the payment_link has expired.


    @classmethod
    def find_by_id(cls, _id: str):
        return cls.query.filter_by(id=_id).first()

    @property
    def expired(self):
        return time() > self.expire_at  # True if the confirmation has expired.

    def deactivate(self):
        self.active = False

    def customer_paid(self):
        self.paid = True

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()
