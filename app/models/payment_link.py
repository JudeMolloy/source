from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from app import app, db, login


PAYMENT_LINK_EXPIRATION_DELTA = 604800  # 7 days (in seconds). Could possibly make this customisable.


class PaymentLink(db.Model):
    __tablename__ = "payment_links"

    id = db.Column(db.String(50), primary_key=True)

    expire_at = db.Column(db.Integer, nullable=False)

    active = db.Column(db.Boolean, default=True, nullable=False)
    paid = db.Column(db.Boolean, default=False, nullable=False)

    price = db.Column(db.Float, nullable=False)
    info = db.Column(db.String)
    product_image_url = db.Column(db.String)


    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # one-to-one relationship with request.
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=True)


    # ensure when generating link that the correct company url is used.
    def __init__(self, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self.id = uuid4().hex
        self.expire_at = int(time()) + PAYMENT_LINK_EXPIRATION_DELTA
        self.user_id = user_id

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
