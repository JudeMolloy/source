from flask import url_for, request

from db import db
from uuid import uuid4
from time import time
from datetime import datetime
from app import app, db, login
from app.models.user import User


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), index=True)
    logo_url = db.Column(db.String)
    endpoint = db.Column(db.String(64), unique=True)

    # social media
    twitter_url = db.Column(db.String)
    facebook_url = db.Column(db.String)
    instagram = db.Column(db.String)

    # one-to-one relationship with user.
    user = db.relationship('User', backref='company', lazy=True, uselist=False)

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_from_db(self):
        db.session.delete(self)
        db.session.commit()

