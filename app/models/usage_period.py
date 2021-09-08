from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import app, db, login
from libs.email import Email


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class UsagePeriod(db.Model):
    __tablename__ = "usage_periods"

    id = db.Column(db.Integer, primary_key=True)

    start = db.Column(db.DateTime, default=datetime.utcnow())
    end = db.Column(db.DateTime)

    # Counts
    email_count = db.Column(db.Integer, default=0)
    sms_count = db.Column(db.Integer, default=0)

    # many-to-one relationship with user.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    def __repr__(self):
        return '<Usage Period - Start:{} End:{}>'.format(self.start.date, self.end.date)

    def __init__(self, term, user_id):
        self.start = datetime.utcnow()
        if term == 'annually':
            self.end = datetime.utcnow() + relativedelta(years=+1)
        elif term == 'monthly':
            self.end = datetime.utcnow() + relativedelta(months=+1)
        self.email_count = 0
        self.sms_count = 0
        self.user_id = user_id

    @property
    def is_active(self):
        if not self.end:
            return False
        return self.end > datetime.utcnow()

    def force_end(self):
        self.end = datetime.utcnow()

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()
