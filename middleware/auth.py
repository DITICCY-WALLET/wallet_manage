import time
import json

from models.models import ApiAuth
from sign.sign import sign_data
from code_status import (sign_error, sign_timeout, sign_require, sign_msg_error,
                         sign_key_invalid)


class Auth(object):
    __EXCLUDE = ['signsture', 'accessKey']
    __SIGN_REQUIRE = __EXCLUDE + ['timestamp']
    # 秒 * 分
    # TODO 为了方便调试, 这里 * 1000000 确保接口不会超期请求.
    TIMEOUT_SECONDS = 60 * 5 * 1000000

    def __init__(self, request):
        self.requests = request
        self.data = self.get_data()
        self.api_auth = None

    def get_auth(self, access_key) -> ApiAuth:
        return ApiAuth.query.filter_by(access_key=access_key).first()

    def get_data(self):
        try:
            data = self.requests.json
        except Exception:
            data = None

        if data is None:
            try:
                data = json.loads(self.requests.text)
            except Exception:
                data = None
        return data

    def order_data(self):
        keys_order = sorted(self.data)
        data = '&'.join(['{}={}'.format(key, self.data[key]) for key in keys_order if key not in self.__EXCLUDE])
        return data

    def check_time(self):
        local_time = time.time()
        try:
            if (float(self.timestamp) + self.TIMEOUT_SECONDS) > local_time:
                return None
        except Exception:
            return sign_msg_error
        return sign_timeout

    def check(self):
        if self.data is None:
            return sign_msg_error
        self.signsture = self.data.get('signsture')
        self.accessKey = self.data.get('accessKey')
        self.timestamp = self.data.get('timestamp')

        # 检查字段必要性
        for key in self.__SIGN_REQUIRE:
            require_sign_key = getattr(self, key)
            if require_sign_key is None:
                return sign_require
        # 检查时间
        timeout = self.check_time()
        if timeout is not None:
            return timeout
        auth = self.get_auth(self.accessKey)
        self.api_auth = auth
        if not auth:
            return sign_error
        if auth.status == 0:
            return sign_key_invalid
        # TODO 检查IP暂时没有做
        # 检查签名
        data = self.order_data()
        secret = auth.secret_key
        sign_str = sign_data(data, secret)
        print("signed string is : {}".format(sign_str))
        if sign_str == self.signsture:
            return True
        return sign_error
