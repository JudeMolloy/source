from flask import url_for, request
from db import db
from time import time
from datetime import datetime
from app import app, db, login


class Enquiry(db.Model):
    __tablename__ = "enquiries"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True)
    subject = db.Column(db.String(128))
    message = db.Column(db.String)

    sent_at = db.Column(db.DateTime, default=datetime.utcnow())

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()

