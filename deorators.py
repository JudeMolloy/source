from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

# Redirects user if they have not confirmed their email address.
def check_email_confirmed(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.most_recent_confirmation.confirmed:
            return func(*args, **kwargs)
        return redirect(url_for('unconfirmed_email'))

    return decorated_function