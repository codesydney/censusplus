from flask import Flask
#from flask_sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap

import os

app = Flask(__name__, static_folder = './main/static')
#app.config.from_object("config")
app.config.from_object(os.environ['APP_SETTINGS'])
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
#db = SQLAlchemy(app)

bootstrap = Bootstrap(app)

#importing main must be after db = SQLAlchemy(app)
from .main import main
from .population import population
from .birthrate import birthrate
from .employmentrate import employmentrate

app.register_blueprint(main,url_prefix='')
app.register_blueprint(population,url_prefix='/population')
app.register_blueprint(birthrate,url_prefix='/birthrate')
app.register_blueprint(employmentrate,url_prefix='/employmentrate')
