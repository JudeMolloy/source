from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_admin import Admin
from flask_migrate import Migrate
from flask_talisman import Talisman

app = Flask(__name__)
Talisman(app, content_security_policy=[])
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'

# Admin setup
from app.models.user import User
from app.models.confirmation import Confirmation
from app.models.request import Request
from app.models.company import Company
from app.models.usage_period import UsagePeriod
from app.models.payment_link import PaymentLink
from app.models.order import Order
from app.models.enquiry import Enquiry

from app.admin import ProtectedAdminHomeView, AdminView, ModelView

# Set the admin theme
#app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

admin = Admin(app, name='Mastero', template_mode='bootstrap4', index_view=ProtectedAdminHomeView(url='/admin'))

# Add the admin views
admin.add_view(AdminView(User, db.session, endpoint='members'))
admin.add_view(ModelView(Confirmation, db.session, endpoint='confirmations'))
admin.add_view(ModelView(Request, db.session, endpoint='requests'))
admin.add_view(ModelView(Company, db.session, endpoint='companies'))
admin.add_view(ModelView(UsagePeriod, db.session, endpoint='usage-periods'))
admin.add_view(ModelView(PaymentLink, db.session, endpoint='payment-links'))
admin.add_view(ModelView(Order, db.session, endpoint='orders'))
admin.add_view(ModelView(Enquiry, db.session, endpoint='enquiries'))


from app import routes, payment_routes, admin_routes, models, errors
