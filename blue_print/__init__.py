import json

from flask import Blueprint, make_response, jsonify, request
from blue_print.v1.controller import block_height, get_balance_by_address, get_wallet_total_balance, get_tx_by_tx_hash, \
    is_mine_address, send_transaction_handle, set_passphrase, create_address, set_deposit_order_id
from code_status import args_error
from httplibs.response import ResponseObject


v1 = Blueprint('v1', __name__)


def get_json(req):
    _json = request.json
    if _json is None:
        try:
            _json = json.loads(request.data)
        except Exception as e:
            _json = None
    return _json


@v1.route('/getBlockHeight', methods=['POST'])
def get_block_height():
    """获取区块高度

    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | remark |
    |--------|--------|--------|--------|

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | currentHeight | false | int | 当前高度 |
    | highestHeight | false | int | 最新高度 |
    - ##### json
    > {"currentHeight": 6367304,"highestHeight": 8529747}
    @@@
    """
    return make_response(jsonify(block_height()))


@v1.route('/newAddress', methods=['POST'])
def new_address():
    """生成新地址
    生成新地址, 当前接口是同步响应返回, 所以该方法不建议一次调用超过10
    V2 版本将升级为异步, 需要提供 callback 地址, 届时可生成较大数量地址

    `该接口必须要在先设置密码后才能使用`
    @@@
    #### 签名
    [v] 必须

    #### args

    暂不需要入参

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | count | false | int | 10 | 生成地址数量 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | addresses | false | array[string] | 地址, ['新地址'...] |
    - ##### json
    > ["abc", "bbc"]
    @@@
    """
    _json = get_json(request)
    project_id = request.project_id

    if _json is not None:
        coin = _json.get("coin", 'Ethereum')
        count = _json.get("count", 10)
        if count is not None and isinstance(count, int):
            return make_response(jsonify(create_address(project_id, coin, count)))

    result = ResponseObject.raise_args_error()

    return make_response(jsonify(result))


@v1.route('/getBalance', methods=['POST'])
def get_balance():
    """获取地址余额
    查询某地址余额

    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | address | false | string |  | 查询地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | balance | false | string | 余额 |
    - ##### json
    > "100.00"
    @@@
    :return:
    """
    _json = get_json(request)

    if _json is not None:
        address = _json.get("address")
        if address is not None:
            return make_response(jsonify(get_balance_by_address(address)))

    result = ResponseObject.raise_args_error()

    return make_response(jsonify(result))


@v1.route('/getTotalBalance', methods=['POST'])
def get_total_balance():
    """查询所有地址总余额

    @@@
    #### 签名
    [v] 必须

    #### args
    暂不需要入参

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | balance | false | string | 余额 |
    - ##### json
    > "100.00"
    @@@
    """
    result = get_wallet_total_balance()
    return make_response(jsonify(result))


@v1.route('/sendTransaction', methods=['POST'])
def send_transaction():
    """发送交易
    向指定账户发送交易

    发送交易之后不一定就会成功.
    业务解决：
            1. 等待用户确认
    技术解决：
            1. 需要使用 getTransactoon 确认
            2. 等待推送

    ******* 这里是重要, 一定要看 *******
    该接口包含的 actionId 字段为校验幂等字段.
    该字段必须唯一, 且如果交易存在的情况下, 不会重复发送交易.
    ******* 这里是重要, 一定要看 *******

    `该接口必须要在先设置密码后才能使用`
    @@@
    #### 签名
    [v] 必须

    #### args
    暂不需要入参

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | actionId | false | string | | 执行码 |
    | sender | false | string |  | 发送地址 |
    | receiver | false | string | | 接口地址 |
    | amount | false | string | | 发送金额 |
    | coin | true | string | Ethereum | 币种, 默认使用ETH ERC20 的 USDT, 当前该选项更改暂时无效 |
    | contract | true | string | null | 合约地址, 默认使用USDT, 若指定时指使用指定 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | txHash | false | string | 交易流水号 |
    - ##### json
    > "100.00"
    @@@
    """
    _json = get_json(request)
    project_id = request.project_id

    if _json is not None:
        action_id = _json.get("actionId")
        sender = _json.get("address")
        receiver = _json.get("receiver")
        amount = _json.get("amount")
        coin = _json.get("coin", 'Ethereum')
        contract = _json.get("contract")
        if None not in [action_id, sender, receiver, amount]:
            return make_response(jsonify(send_transaction_handle(project_id, action_id, sender, receiver, amount, coin, contract)))

    result = ResponseObject.raise_args_error()
    return make_response(jsonify(result))


@v1.route('/getTransaction', methods=['POST'])
def get_transaction():
    """查询交易详情

    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | txHash | false | string |  | 交易流水号 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | sender | false | string | 发送地址 |
    | receiver | false | string | 接口地址 |
    | txHash | false | string | 交易流水号 |
    | value | false | string | 交易金额 |
    | blockHeight | false | int | 所在高度 |
    | blockTime | false | int | 时间戳, 秒级 |
    | contract | true | string | 合约地址 |
    | isValid | false | bool | 是否有效 |
    | confirmNumber | false | int | 最新确认数 |


    - ##### json
    > {“sender”: "1392019302193029",
    "receiver": "1392019302193029",
    "txHash": "1392019302193029",
    "value": "100.00",
    "blockHeight": 10000,
    "blockTime": 10000,
    "contract": "1392019302193029",
    "isValid": true,
    "confirmNumber": 100
    }
    @@@
    :return:
    """
    _json = get_json(request)

    if _json is not None:
        tx_hash = _json.get("txHash")
        if tx_hash is not None:
            return make_response(jsonify(get_tx_by_tx_hash(tx_hash)))

    result = ResponseObject.raise_args_error()
    return make_response(jsonify(result))


@v1.route('/checkAddress', methods=['POST'])
def check_address():
    """查询某地址是否归属我方钱包中

    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | address | false | string |  | 查询地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isSet | false | bool | 是否为我方地址 |
    - ##### json
    > "100.00"
    @@@
    :return:
    """
    _json = get_json(request)
    project_id = request.project_id

    if _json is not None:
        address = _json.get("address")
        if address is not None:
            return make_response(jsonify(is_mine_address(project_id, address)))

    result = ResponseObject.raise_args_error()
    return make_response(jsonify(result))


@v1.route('/setWalletPassphrase', methods=['POST'])
def set_wallet_passphrase():
    """设置钱包密码

    该字段是加密传输, 加密算法请见...
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | secret | false | string |  | 密钥 |
    | coin | true | string | Ethereum | 币种, 默认使用ETH ERC20 的 USDT, 当前该选项更改暂时无效 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isSet | false | bool | 是否设置成功 |

    - ##### json
    > true
    @@@
    :return:
    """
    _json = get_json(request)
    project_id = request.project_id

    if _json is not None:
        secret = _json.get("secret")
        coin = _json.get("coin", 'Ethereum')
        if secret is not None or coin is None:
            return make_response(jsonify(set_passphrase(project_id, coin, secret)))

    result = ResponseObject.raise_args_error()
    return make_response(jsonify(result))


@v1.route('/addOrderId', methods=['POST'])
def add_order_id():
    """添加订单号
    ********* 这个地方逻辑有问题, 当前无法处理 ********
    外部给预某个订单号, 给外界推送匹配订单号
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | orderId | false | string |  | 订单号 |
    | address | false | string | | 订单绑定的地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isSet | false | bool | 是否设置成功 |

    - ##### json
    > true
    @@@
    :return:
    """
    _json = get_json(request)
    project_id = request.project_id

    if _json is not None:
        order_id = _json.get("orderId")
        address = _json.get("address")
        if order_id is not None or address is None:
            return make_response(jsonify(set_deposit_order_id(project_id, order_id, address)))

    result = ResponseObject.raise_args_error()
    return make_response(jsonify(result))
