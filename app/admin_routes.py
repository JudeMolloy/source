import traceback
import os
import stripe

from flask import render_template, url_for, flash, request, session
from datetime import datetime
from werkzeug.urls import url_parse
from werkzeug.utils import redirect
from app import app, db
from app.forms import LoginForm
from flask_login import current_user, login_user, logout_user, login_required


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password. Please try again.')
            return redirect(url_for('admin_login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('mastero/admin-login.html', title='Sign In', form=form)