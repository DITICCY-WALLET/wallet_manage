# coding: utf-8
import multiprocessing
import os
import sys
# worker数量
workers = multiprocessing.cpu_count() * 2 + 1
# workers = 1

# 优雅关闭给worker的时候
graceful_timeout = 60

# 单个worker处理超时时间
timeout = 60

# worker 类型
worker_class = 'gevent'

# Http请求最大字节
limit_request_line = 8190

# Http头最大字段数量
limit_request_fields = 200

# The Access log file to write to.
accesslog = '/var/logs/run_server_gunicorn_access.log'

# The Error log file to write to.
errorlog = '/var/logs/run_server_gunicorn_error.log'

# The granularity of Error log outputs.
loglevel = 'info'
