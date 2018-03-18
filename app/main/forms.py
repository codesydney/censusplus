from flask_wtf import FlaskForm
#from flask.ext.wtf import Form
from wtforms import StringField, IntegerField, SubmitField, HiddenField
from wtforms import validators
from wtforms.validators import DataRequired
from werkzeug.datastructures import MultiDict

class MainForm(FlaskForm):
	OpendTitle = StringField("OPEND")
	InputAddress = StringField('Search for your address',[validators.Required("Enter your address")])	
	Submit1 = SubmitField('GO',render_kw={"size":"90"})	    

class TryAgainForm(FlaskForm):
    InputAddress = StringField('Address not found. Please try again.', \
                    [validators.Required("Search for your address")])
    Submit1 = SubmitField('Try again',render_kw={"size":"90"})