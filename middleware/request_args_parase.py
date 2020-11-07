import json
from collections import namedtuple

from flask import request
from werkzeug.exceptions import abort

from httplibs.response import ResponseObject

"""
入口请求参数检测
"""


class RequestJsonParser(object):
    def __init__(self):
        self.request = request
        self._json = self.get_json()

    def get_json(self):
        _json = self.request.json
        if _json is None:
            try:
                _json = json.loads(self.request.data)
            except Exception as e:
                raise abort(400, ResponseObject.raise_args_error(msg="JSON 匹配不正确"))
        return _json

    def add_argument(self, key, type=None, required=False, choices=None, default="",
                     helper=None, trim=False, check_func=None, **kwargs):
        if helper is None:
            helper = {}
        value = self._json.get(key)
        if required and value is None:
            raise abort(400, ResponseObject.raise_args_error(
                msg=isinstance(helper, dict) and helper.get('required') or helper
                or "{} 字段为必填项".format(key)))
        elif not required and value is None:
            value = self._json[key] = default

        if choices is not None and isinstance(choices, (tuple, list)):
            if value not in choices:
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('choices') or helper
                    or "{} 必须选项必须为 {}".format(key, ' or '.join(choices))))

        if type is not None:
            if not isinstance(value, type):
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('type') or helper
                    or "{} 格式必须为 {}".format(key, type.__name__)))

        if check_func is not None and callable(check_func):
            result = check_func(value, **kwargs)
            if not result:
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('check_func') or helper
                    or "{} 字段未通过校验".format(key)))

        if isinstance(value, str) and trim:
            self._json[key] = value.strip()

        return self

    def get_argument(self):
        keys = list(self._json.keys())
        Argument = namedtuple("Argument", keys)
        return Argument(*self._json.values())















