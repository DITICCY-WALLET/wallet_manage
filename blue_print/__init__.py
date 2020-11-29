import json
import re
from werkzeug.exceptions import abort

from flask import Blueprint, make_response, jsonify, request
# from flask_restful import Api, Resource, reqparse
from blue_print.v1.controller import block_height, get_balance_by_address, \
    get_wallet_total_balance, get_tx_by_tx_hash, is_mine_address, send_transaction_handle, \
    set_passphrase, create_address, set_deposit_order_id, add_coin_ctl, get_project_info_ctl, \
    update_project_info_ctl, remove_address_ctl, set_hot_addr_ctl, set_collect_addr_ctl, \
    set_render_addr_ctl, set_fee_ctl, turn_status_ctl, add_project_coin_ctl

from blue_print.v1 import controller as v1_controller
from digit import digit

from httplibs.response import ResponseObject
from middleware.request_args_parase import RequestJsonParser
from enumer.routine import DBStatusEnum

v1 = Blueprint('v1', __name__)


def get_json(req):
    _json = request.json
    if _json is None:
        try:
            _json = json.loads(request.data)
        except Exception as e:
            raise abort(400, ResponseObject.raise_args_error(msg="JSON 匹配不正确"))
    return _json


@v1.route('/getBlockHeight', methods=['POST', 'GET'])
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
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument("masterCoinId", type=int, required=True)
    parser.add_argument("count", type=int, required=False, default=10)
    args = parser.get_argument()
    result = create_address(args.projectId, args.masterCoinId, args.count)
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
    | masterCoinId | false | int |  | 查询币种, 这里只能使用主链币的 ID |
    | address | false | string |  | 查询地址 |
    | penetrate | true | bool | | 直查节点, 不校验钱包是否支持该币种. 该参数可能导致使用异常 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | balance | false | string | 余额 |
    - ##### json
    > "100.00"
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("masterCoinId", type=int, required=True)
    parser.add_argument("address", type=str, required=True)
    parser.add_argument("contract", type=str, required=False)
    # parser.add_argument('penetrate', type=bool, required=False, default=False)
    args = parser.get_argument()
    result = get_balance_by_address(args.masterCoinId, args.address, args.contract)
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
    | projectId | false | int | | 项目 ID |
    | coinId | false | int | | 币种 ID |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | balance | false | string | 余额 |
    - ##### json
    > "100.00"
    @@@
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument("coinId", type=int, required=True)
    args = parser.get_argument()
    result = get_wallet_total_balance(args.projectId, args.coinId)
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
    | projectId | false |  int | | 项目 ID |
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
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument("actionId", type=str, required=True)
    parser.add_argument('address', type=str, required=True, trim=True)
    parser.add_argument('receiver', type=str, required=True, trim=True)
    parser.add_argument('amount', type=str, required=True, trim=True, check_func=digit.is_number)
    parser.add_argument('coinId', type=str, required=True, trim=True)
    parser.add_argument('contract', type=str, required=False)
    args = parser.get_argument()
    result = send_transaction_handle(args.projectId, args.actionId, args.address, args.receiver,
                                     args.amount, args.coinId, args.contract)
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
    parser = RequestJsonParser()
    parser.add_argument('txHash', type=str, required=True, trim=True)
    args = parser.get_argument()
    result = get_tx_by_tx_hash(args.txHash)
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
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('address', type=str, required=True, trim=True)
    args = parser.get_argument()
    result = is_mine_address(args.projectId, args.address)

    return make_response(jsonify(result))


@v1.route('/setWalletPassphrase', methods=['POST'])
def set_wallet_passphrase():
    """设置钱包密码

    该字段是加密传输, 加密算法请见 TODO 待补充加密算法文档
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
    # _json = get_json(request)
    # project_id = request.project_id

    # if _json is not None:
    #     secret = _json.get("secret")
    #     coin = _json.get("coin", 'Ethereum')
    #     if secret is not None or coin is None:
    #         return make_response(jsonify(set_passphrase(project_id, coin, secret)))

    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True, trim=True)
    parser.add_argument('secret', type=str, required=True, trim=True)
    args = parser.get_argument()
    result = set_passphrase(args.projectId, args.coinId, args.secret)
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


@v1.route('/coinList', methods=['POST', "GET"])
def coin_list():
    """币种列表
    返回当前支持的币种
    @@@
    #### 签名
    [x] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|


    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | coinName | false | String | 币种名称 |
    | decimal | false | int | 币种Wei |
    | symbol | false | String | 币种简称 |
    | masterName | false | String | 币种主链名称, 如果不是合约该名称与coinName相同 |
    | contract | true | String | 合约地址 |
    | supply | true | String | 币种总量, 该信息极可能不准确, 仅提供参考价值 |

    - ##### json
    >
    @@@
    :return:
    :return:
    """
    list_coin = v1_controller.get_coin_list()
    return ResponseObject.success(data=list_coin)


@v1.route('/addCoin', methods=['POST'])
def add_coin():
    """币种列表
    新添加一个 ERC20 币种
    @@@
    #### 签名
    [x] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    # | masterName | false | String | | 币种主链名称, 如果不是合约该名称与coinName相同 |
    | masterCoinId | false | Int | | 主链币 ID |
    | contract | false | String | | 合约地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isAdd | false | bool | 币种主链名称, 如果不是合约该名称与coinName相同 |

    - ##### json
    >
    @@@
    :return:
    """

    parser = RequestJsonParser()
    parser.add_argument("masterCoinId", type=str, required=True, trim=True, check_func=str.lower,
                        helper={"required": "masterName 不可缺失",
                                "type": "masterName 类型不匹配"})
    parser.add_argument("contract", type=str, required=True, trim=True, check_func=str.lower,
                        helper="字段必须以0x开头")
    args = parser.get_argument()
    is_success = add_coin_ctl(args.masterCoinId, args.contract)
    return make_response(jsonify(is_success))


@v1.route('/getProjectInfo', methods=['GET', 'POST'])
def get_project_info():
    """获取项目方信息
    返回当前支持的币种
    @@@
    #### 签名
    [x] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | projectId | false | Int | 项目方ID |
    | name | false | String | 项目方名称 |
    | callbackUrl | false | String | 回调URL |
    | accessKey | false | String | 请求 |
    | publicKey | false | String | 特殊事件公钥, 对于非对称加密 |
    | coins | true | List | 各币种设置 |
    | coins.[].coinName | true | String | 币种名称 |
    | coins.[].hotAddress | true | String | 热钱包地址 |
    | coins.[].collectionAddress | true | String | 归集钱包地址 |
    | coins.[].renderAddress | true | String | 补充手续费钱包地址 |
    | coins.[].fee | true | String | 币种手续费 |
    | coins.[].isDeposit | true | Int | 当前是否开启充币 1 是, 0 Null 否 |
    | coins.[].isWithdraw | true | Int | 当前是否开启提币 1 是, 0 Null 否 |
    | coins.[].isCollect | true | Int | 当前是否开启归集 1 是, 0 Null 否 |

    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True, trim=True, handle_func=str.lower)
    args = parser.get_argument()
    project_info = get_project_info_ctl(args.projectId)
    return make_response(jsonify(project_info))


@v1.route('/updateProjectInfo', methods=["POST"])
def update_project_info():
    """修改项目方资料
    修改项目方资料
    @@@
    #### 签名
    [√] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | callbackUrl | false | String | | 回调 URL |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 修改项目方资料是否成功 |

    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('callbackUrl', type=str, required=True, trim=True,
                        handle_func=lambda x: re.compile('http[s]?://.*?').fullmatch(x).group(),
                        helper={"handle_func": "callbackUrl 不符合 url 规则, 请匹配正则 http[s]?://.*?"})
    args = parser.get_argument()
    is_success_obj = update_project_info_ctl(args.projectId, args.callbackUrl)
    return make_response(jsonify(is_success_obj))


@v1.route("/proxyNode", methods=["POST"])
def proxy_node():
    """代理请求节点
    TODO ********* 延期实现 ********
    代理请求节点 & 通过 Proxy 直接访问节点
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|

    - ##### json
    >
    @@@
    :return:
    """


@v1.route("/setWarnRobot", methods=["POST"])
def set_warn_robot():
    """设置报警机器人URL
    TODO ********* 延期实现 ********
    设置机器人, 供报警使用
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|

    - ##### json
    >
    @@@
    :return:
    """


@v1.route("/getRobotList", methods=["POST"])
def get_robot_list():
    """查看支持的机器人列表
    TODO ********* 延期实现 ********
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|

    - ##### json
    >
    @@@
    :return:
    """


@v1.route("/setWarnRule", methods=["POST"])
def set_warn_rule():
    """设置报警条件
    TODO ********* 延期实现 ********
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|

    - ##### json
    >
    @@@
    :return:
    """


@v1.route("/removeAddress", methods=["POST"])
def remove_address():
    """废弃钱包地址
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方 ID |
    | coinId | false | Int | | 币种 ID |
    | address | false | String | | 热钱包地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 废弃地址是否成功 |

    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('address', type=str, required=True)
    args = parser.get_argument()
    is_success_obj = remove_address_ctl(args.projectId, args.coinId, args.address)
    return make_response(jsonify(is_success_obj))


@v1.route("/setHotAddress", methods=["POST"])
def set_hot_addr():
    """设置热钱包地址
    设置热钱包地址, 给归集(优先级低于归集地址)和提现使用
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |
    | hotAddress | false | String | | 热钱包地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 地址是否成功 |

    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('hotAddress', type=str, required=True)
    args = parser.get_argument()
    is_success_obj = set_hot_addr_ctl(args.projectId, args.coinId, args.hotAddress)
    return make_response(jsonify(is_success_obj))


@v1.route("/setCollectAddress", methods=["POST"])
def set_collect_address():
    """设置归集钱包地址
    设置归集钱包地址, 用于归集(优先级低于归集地址), 暂无对外方法,
    该地址当前一般为外部地址.
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |
    | collectAddress | false | String | | 热钱包地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 地址是否成功 |

    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('collectAddress', type=str, required=True)
    args = parser.get_argument()
    is_success_obj = set_hot_addr_ctl(args.projectId, args.coinId, args.address)
    return make_response(jsonify(is_success_obj))


@v1.route("/setRenderAddress", methods=["POST"])
def set_render_address():
    """设置补充手续费地址
    补充手续费地址, 用于向用户地址提供手续费, 以此来归集 Token 币.
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |
    | renderAddress | false | String | | 手续费地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 地址是否成功 |
    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('renderAddress', type=str, required=True)
    args = parser.get_argument()
    is_success_obj = set_collect_addr_ctl(args.projectId, args.coinId, args.renderAddress)
    return make_response(jsonify(is_success_obj))


@v1.route("/setRenderRule", methods=["POST"])
def set_render_rule():
    """设置归集条件
    设置归集条件, 可以确认是否需要归集与归集的额外条件
    TODO 该接口延期实现
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isAdd | false | bool | 地址是否成功 |
    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('collectAddress', type=str, required=True)
    args = parser.get_argument()
    is_success_obj = set_render_addr_ctl(args.projectId, args.coinId, args.collectAddress)
    return make_response(jsonify(is_success_obj))


@v1.route("/setFee", methods=["POST"])
def set_fee():
    """设置手续费
    设置手续费, 如果是 ETH 则为 GasPrice.
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |
    | gas | true | Int | | 币种 ID |
    | gasPrice | true | Int | | 币种 ID |
    | fee | true | String | | 手续费地址 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 地址是否成功 |
    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('gas', type=str, required=False)
    parser.add_argument('gasPrice', type=str, required=False)
    parser.add_argument('fee', type=str, required=False)
    args = parser.get_argument()
    is_success_obj = set_fee_ctl(args.projectId, args.coinId, args.gas,
                                 args.gasPrice, args.fee)
    return make_response(jsonify(is_success_obj))


@v1.route("/turnStatus", methods=["POST"])
def turn_status():
    """暂停/恢复充提
    @@@
    #### 签名
    [v] 必须

    #### args

    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |
    | isDeposit | true | Int |  | 开闭充币, 0 关 1 开, 其他选项暂时不接受 |
    | isWithdraw | true | Int |  | 开闭提币, 0 关 1 开, 其他选项暂时不接受 |
    | isCollect | true | Int |  | 开闭归集, 0 关 1 开, 其他选项暂时不接受 |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 地址是否成功 |
    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument('isDeposit', type=int, choices=(DBStatusEnum.NO.value,
                                                        DBStatusEnum.YES.value))
    parser.add_argument('isWithdraw', type=int, choices=(DBStatusEnum.NO.value,
                                                         DBStatusEnum.YES.value))
    parser.add_argument('isCollect', type=int, choices=(DBStatusEnum.NO.value,
                                                        DBStatusEnum.YES.value))
    args = parser.get_argument()
    is_success_obj = turn_status_ctl(args.projectId, args.coinId, args.isDeposit,
                                     args.isWithdraw, args.isCollect)
    return make_response(jsonify(is_success_obj))


@v1.route("/addProjectCoin", methods=["POST"])
def add_project_coin():
    """增加项目方支持币种
    @@@
    #### 签名
    [v] 必须

    #### args
    | args | nullable | type | default | remark |
    |--------|--------|--------|--------|--------|
    | projectId | false | Int | | 项目方ID |
    | coinId | false | Int | | 币种 ID |
    | hotAddress | false | | |
    | gas | false | | |
    | gasPrice | false | | |
    | fee | false | | |
    | collectAddress | false | | |
    | feeAddress | false | | |
    | isDeposit | false | | |
    | isWithdraw | false | | |
    | isCollect | false | | |

    #### return
    | args | nullable | type | remark |
    |--------|--------|--------|--------|
    | isChange | false | bool | 地址是否成功 |
    - ##### json
    >
    @@@
    :return:
    """
    parser = RequestJsonParser()
    parser.add_argument("projectId", type=int, required=True)
    parser.add_argument('coinId', type=int, required=True)
    parser.add_argument("hotAddress", type=int, required=True)
    parser.add_argument("collectAddress", type=int, required=True)
    parser.add_argument('feeAddress', type=int, required=True)
    parser.add_argument('gas', type=int, required=True)
    parser.add_argument("gasPrice", type=int, required=True)
    parser.add_argument('fee', type=int, required=True)
    parser.add_argument('isDeposit', type=str, choices=(DBStatusEnum.NO, DBStatusEnum.YES))
    parser.add_argument('isWithdraw', type=str, choices=(DBStatusEnum.NO, DBStatusEnum.YES))
    parser.add_argument('isCollect', type=str, choices=(DBStatusEnum.NO, DBStatusEnum.YES))
    args = parser.get_argument()
    is_success_obj = add_project_coin_ctl(args.projectId,
                                          args.coinId,
                                          args.hotAddress,
                                          args.collectAddress,
                                          args.feeAddress,
                                          args.gas,
                                          args.gasPrice,
                                          args.fee,
                                          args.isDeposit,
                                          args.isWithdraw,
                                          args.isCollect)
    return make_response(jsonify(is_success_obj))
