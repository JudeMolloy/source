from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from app import app, db, login
from libs.otp import OTP


CONFIRMATION_EXPIRATION_DELTA = 1800  # 30 minutes (in seconds).


class Confirmation(db.Model):
    __tablename__ = "confirmations"

    id = db.Column(db.String(50), primary_key=True)
    otp = db.Column(db.String(6))
    expire_at = db.Column(db.Integer, nullable=False)
    confirmed = db.Column(db.Boolean(create_constraint=False), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def __init__(self, user_id: int, **kwargs):
        super().__init__(**kwargs)
        self.id = uuid4().hex
        self.otp = OTP.generate(6)
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
