from flask import Blueprint

employmentrate = Blueprint(
    'employmentrate',
    __name__,
    template_folder='templates',
    static_folder='static'
)

from . import views