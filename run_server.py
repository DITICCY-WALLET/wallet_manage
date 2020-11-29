from flask import Flask
from flask import request, make_response
from flask.json import jsonify
from flask_docs import ApiDoc
from flask_apscheduler import APScheduler

from config import runtime
from blue_print import v1

from httplibs.response import ResponseObject, sign_key_not_bind_project
from middleware.auth import Auth
from models.models import ApiAuth
from exts import db
from config.config import config
from tasks.scan_chain import ScanEthereumChain
from lock import ProcessLock

app = Flask(__name__)

app.register_blueprint(v1, url_prefix='/api/v1/')

runtime.app = app


@app.before_request
def auth():
    if app.config.get('OPEN_SIGN_AUTH') and any([request.path.startswith(path) for path in app.config.get('SIGN_API')]):
        try:
            _auth = Auth(request)
            allow = _auth.check()
        except Exception as e:
            return make_response(jsonify(ResponseObject.raise_sign_exception()), 200)
        if isinstance(allow, dict):
            return make_response(jsonify(ResponseObject.error(**allow)), 200)
        # 如果是有
        if _auth.api_auth.project_id is None:
            return make_response(jsonify(ResponseObject.error(**sign_key_not_bind_project)), 200)
        request.projectId = _auth.api_auth.project_id
    if not app.config.get('OPEN_SIGN_AUTH'):
        # 为调试使用
        request.projectId = 1


@app.errorhandler(404)
def err40x(e):
    return make_response(jsonify(ResponseObject.raise_404_error()), 404)


@app.errorhandler(400)
def err40x(e):
    if isinstance(e.description, (dict, list)):
        return make_response(jsonify(e.description), 400)
    return make_response(jsonify(ResponseObject.raise_args_error(msg="JSON 匹配不正确")), 400)


@app.errorhandler(500)
@app.errorhandler(501)
@app.errorhandler(502)
@app.errorhandler(503)
@app.errorhandler(504)
def err50x(e):
    return make_response(jsonify(ResponseObject.raise_exception()), e.code)


@app.route('/ping', methods=['GET', 'POST'])
def ping():
    return 'pong'


@app.route('/check', methods=['GET', 'POST'])
def hello_world():
    api = ApiAuth.query.filter_by(access_key='123').first()
    print(api)
    return str(api)


def echo():
    print(1)


app.config.from_object(config)
app.app_context().push()
ApiDoc(app)
db.init_app(app)

# 预读数据到缓存中
ScanEthereumChain.read_address()
ScanEthereumChain.read_coins()

scheduler = APScheduler()
scheduler.init_app(app)
scheduler_lock = ProcessLock(scheduler.start, filename='wallet-manage-scheduler.lock')
scheduler_lock.lock_run()

if __name__ == '__main__':
    app.run(port=config.PORT)
