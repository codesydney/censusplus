from flask_wtf import FlaskForm
#from flask.ext.wtf import Form
from wtforms import StringField, IntegerField, SubmitField, HiddenField
from wtforms import validators
from wtforms.validators import DataRequired
from werkzeug.datastructures import MultiDict

class MainForm(FlaskForm):
	OpendTitle = StringField("OPEND")
	InputAddress = StringField('Input an address and select one from suggested addresses',[validators.Required("Enter your address")])	
	Submit1 = SubmitField('Get Report',render_kw={"size":"90"})	    

class TryAgainForm(FlaskForm):
    InputAddress = StringField('Cannot find the inputed address, please input an address and select one from suggested addresses', \
                    [validators.Required("Enter your address")])
    Submit1 = SubmitField('Try again',render_kw={"size":"90"})