## 响应码

```json 
# --------------- 系统级错误码 ---------------
# ***** 普通错误码 *****
success_msg = {"code": 0, 'msg': "成功"}
not_catch_error = {"code": 1, 'msg': "服务器异常"}
error_msg = {"code": 10, 'msg': "失败"}

# ***** 数据库错误码 ***** 100 - 120 *****
data_missing = {"code": 100, 'msg': "数据库缺少必要数据"}

# ***** 响应错误码 *****
not_found_error = {"code": 404, 'msg': "URL 不存在"}

# --------------- 业务错误码 ---------------
# ***** 基础错误码 ***** 1000 - 1009 *****
args_error = {"code": 1001, 'msg': "请求参数不正确"}

# ***** 签名错误 ***** 1010 - 1029 *****
sign_exception = {"code": 1010, 'msg': "签名异常"}
sign_error = {"code": 1011, 'msg': "签名错误"}
sign_timeout = {"code": 1012, 'msg': "签名超时"}
sign_require = {"code": 1013, 'msg': "签名必要字段缺失"}
sign_msg_error = {"code": 1014, 'msg': "签名信息错误"}
sign_key_invalid = {"code": 1015, 'msg': "签名key无效"}
sign_key_not_bind_project = {"code": 1016, 'msg': "签名key未绑定项目ID"}
sign_rsa_not_found = {"code": 1017, 'msg': "未匹配到对应密钥对"}
sign_rsa_invalid = {"code": 1018, 'msg': "非本密钥对加密信息"}
sign_rsa_exception = {"code": 1019, 'msg': "加解密出现异常"}

# ***** 对外数据错误 ***** 1030 - 1039 *****
out_data_missing = {"code": 1030, 'msg': "缺少必要数据"}

# ***** 币种基础数据 ***** 1040 - 1049 *****
coin_missing = {"code": 1040, 'msg': "未找到该币种"}
rpc_service_error = {"code": 1041, 'msg': "请求RPC服务器错误"}

# ***** 币种错误 ***** 1100 - 1199 *****
balance_rpc_error = {"code": 1100, 'msg': "请求余额RPC失败"}
tx_miss = {"code": 1101, 'msg': "交易未找到"}
sender_invalid = {"code": 1102, 'msg': "发送地址未找到"}
address_invalid = {"code": 1103, 'msg': "地址非本钱包地址", 'data': False}
send_tx_error = {"code": 1104, 'msg': "发送交易失败"}
fee_args_error = {"code": 1105, 'msg': "动态手续费参数获取异常, 无法发送交易"}
tx_send_error = {"code": 1106, 'msg': "交易发送失败"}
passphrase_invalid = {"code": 1107, 'msg': "密码错误"}
not_support_coin = {"code": 1110, 'msg': "暂不支持该交易币种"}

# ***** 项目方有关错误 ***** 1200 - 1299 *****
project_miss = {"code": 1200, 'msg': "未找到项目方数据"}
project_passphrase_miss = {"code": 1201, 'msg': "项目未设置任何币种密码, 请先设置币种密码"}
coin_passphrase_miss = {"code": 1202, 'msg': "当前币种未设置密码, 请先设置币种密码"}
coin_passphrase_error = {"code": 1203, 'msg': "密码缺少"}

```

