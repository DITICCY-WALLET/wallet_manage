import json
from collections import namedtuple
import logging

from flask import request
from werkzeug.exceptions import abort

from httplibs.response import ResponseObject

"""
入口请求参数检测
"""


class RequestJsonParser(object):

    def __init__(self, logger=None):
        self.request = request
        self._json = self.get_json()
        self.logger = logger or logging.getLogger(__name__)

    def get_json(self):
        _json = self.request.json
        if _json is None:
            try:
                _json = json.loads(self.request.data)
            except Exception as e:
                raise abort(400, ResponseObject.raise_args_error(msg="JSON 匹配不正确"))
        return _json

    def add_argument(self, key, type=None, required=False, choices=None, default=None,
                     helper=None, trim=False, check_func=None, handle_func=None, **kwargs):
        """
        添加参数
        :param key: 请求的关键字
        :param type: 关键字类型
        :param required: 是否必填
        :param choices: value 值选择在 choices
        :param default: 默认值
        :param helper: dict or None 返回说明指定字段的提示, 若不指定则按默认代码返回
        :param trim: 去除字符串两边的空格
        :param check_func: 自定义 bool 检验函数
        :param handle_func: 自定义 handler 处理函数, 会覆盖之前的值
        :param kwargs:
        :return: self
        """
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
            if value is not None and value not in choices:
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('choices') or helper
                    or "{} 必须选项必须为 {}".format(key, ' or '.join(choices))))

        if type is not None and required:
            if not isinstance(value, type):
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('type') or helper
                    or "{} 数据类型必须为 {}".format(key, type.__name__)))

        if check_func is not None and callable(check_func):
            result = check_func(value, **kwargs)
            if not result:
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('check_func') or helper
                    or "{} 字段未通过校验".format(key)))

        if isinstance(value, str) and trim:
            self._json[key] = value.strip()

        if handle_func is not None and callable(handle_func):
            try:
                result = handle_func(value, **kwargs)
            except Exception as e:
                self.logger.info("Handle_func Function Except Error: func: {} args:{} error: {}".
                                 format(handle_func.__name__, kwargs, e))
                raise abort(400, ResponseObject.raise_args_error(
                    msg=isinstance(helper, dict) and helper.get('handle_func') or helper
                    or "{} 字段处理不符合规则".format(key)
                ))
            else:
                if not required:
                    self._json[key] = result
                elif required and result:
                    self._json[key] = result
                else:
                    raise abort(400, ResponseObject.raise_args_error(
                        msg=isinstance(helper, dict) and helper.get('handle_func') or helper
                        or "{} 经 handle 处理后不符合参数规则".format(key)
                    ))

        return self

    def get_argument(self):
        """
        返回含有正确参数的对象
        :return: Object -> Argument
        """
        keys = list(self._json.keys())
        Argument = namedtuple("Argument", keys)
        return Argument(*self._json.values())















