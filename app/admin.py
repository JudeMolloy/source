from flask import url_for, request
from flask_admin import expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login.utils import current_user
from werkzeug.utils import redirect
from app.models.user import User

class ProtectedAdminHomeView(AdminIndexView):

    # Ensures the user is authenticated and an admin accounts
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect(url_for('admin_login', next=request.url))

    @expose('/')
    def index(self):
        #return self.render('/mastero-admin/index.html')
        pass


class AdminView(ModelView):
    # Allows CSV export of the model view.
    can_export = True

    # Ensures the user is authenticated and one of the admin accounts
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect(url_for('admin-login', next=request.url))
