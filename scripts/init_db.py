from flask import Flask
from exts import db
from config.config import config
from key.generate_key import generate_rsa_key, generate_ack
from models.models import *
app = Flask(__name__)
app.config.from_object(config)

db.init_app(app)
app.app_context().push()

db.create_all()

session = db.session()

sign_key = generate_ack()
rsa_key = generate_rsa_key()

# session.begin(subtransactions=True)
project = Project(1, 'lucky', "http://agent.niuniu2020.com/upayret/payret", sign_key['access_key'],
                  sign_key['secret_key'])




