import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tryguessthislokurrrrrnonotthat'
    
    DATABASE_URL = os.environ.get('DATABASE_URL')

    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL').replace("s://", "sql://", 1) or \
                              'sqlite:///' + os.path.join(basedir, 'app.db')
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')