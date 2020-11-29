from blue_print.v1.service.address_server import set_address
from coin.resolver.eth_resolver import EthereumResolver
from digit.digit import hex_to_int, int_to_hex
from digit import safe_math
from enumer.coin_enum import AddressTypeEnum
from enumer.routine import DBStatusEnum
from exceptions import JsonRpcError
from httplibs.response import ResponseObject
from models.models import Coin, Address, Transaction, RpcConfig, ProjectCoin, ProjectOrder, Project
from config import runtime
from code_status import *
from sign.rsa import RsaCrypto
from log import logger


def check_passphrase(project_coin, secret) -> (bool, object, str, object):
    # private_key = project_coin.ProjectCoin.hot_pk
    private_key = project_coin.Project.hot_pk
    if private_key is None:
        return False, ResponseObject.error(**sign_rsa_not_found), None, None
    crypto = RsaCrypto()
    crypto.import_key(private_key)
    try:
        passphrase = crypto.decrypt(secret)
    except Exception as e:
        return False, ResponseObject.error(**sign_rsa_invalid), None, None

    rpc = RpcConfig.get_rpc()
    if rpc is None:
        return False, ResponseObject.error(**out_data_missing), None, None

    is_correct_passphrase = rpc.open_wallet(passphrase=passphrase,
                                            address=project_coin.ProjectCoin.hot_address)
    if not is_correct_passphrase:
        return False, ResponseObject.error(**passphrase_invalid), None, None
    return True, crypto, passphrase, rpc


def get_secret(project_id, coin_id) -> (bool, object):
    project_secret = runtime.rsa_secret.get(project_id)
    if project_secret is None:
        return False, ResponseObject.error(**project_passphrase_miss)

    coin_secret = project_secret.get(coin_id)
    if coin_secret is None:
        return False, ResponseObject.error(**coin_passphrase_miss)

    secret = coin_secret.get('secret')
    crypto = coin_secret.get('crypto')
    if not all([secret, crypto]):
        return False, ResponseObject.error(**coin_passphrase_miss)
    return True, secret


def block_height():
    rpc = RpcConfig.get_rpc()
    if rpc is None:
        return ResponseObject.error(**out_data_missing)
    try:
        node_height = rpc.get_block_height().to_dict()
    except Exception as e:
        return ResponseObject.error(**rpc_service_error)
    return ResponseObject.success(data=node_height)


def create_address(project_id, coin_name, count):
    is_valid_secret, secret_result = get_secret(project_id, coin_name)
    if not is_valid_secret:
        return secret_result
    secret = secret_result

    project_coin = ProjectCoin.get_pro_coin_by_pid_cname(project_id, coin_name)
    if not project_coin:
        return ResponseObject.error(**sign_rsa_not_found)

    is_valid_pass, result, passphrase, rpc = check_passphrase(project_coin, secret)
    if not is_valid_pass:
        return result

    addresses = rpc.new_address(passphrase=passphrase, count=count)
    if not isinstance(addresses, (list, tuple)):
        addresses = [addresses]
    success_count = 0
    addresses_add_list = []
    for address in addresses:
        if address is not None:
            addresses_add_list.append(
                {"project_id": project_id, 'address': address,
                 "coin_id": project_coin.ProjectCoin.coin_id,
                 "address_type": AddressTypeEnum.DEPOSIT.value})
            success_count += 1
            runtime.project_address[address] = {
                "project_id": project_id,
                "coin_id": project_coin.ProjectCoin.coin_id,
                "coin_name": coin_name
            }
    Address.add_addresses(addresses_add_list)
    return ResponseObject.success(data=addresses)


def get_balance_by_address(master_coin_id: int, address: str, contract: str = None):
    """这里只能查单个地址的余额"""
    # coin = Coin.get_coin_lj_contract_by_id(master_coin_id)
    if contract is not None:
        filter_args = {
            "master_id": master_coin_id,
            "contract": contract
        }
    else:
        filter_args = {"id": master_coin_id}

    coin = Coin.query.filter_by(**filter_args)

    if coin is None:
        return ResponseObject.error(**coin_missing)

    rpc = RpcConfig.get_rpc_by_coin(master_coin_id)
    if rpc is None:
        return ResponseObject.error(**out_data_missing)
    try:
        balance_hex = rpc.get_balance(address, contract)
    except Exception as e:
        return ResponseObject.error(**rpc_service_error)
    if balance_hex:
        balance = safe_math.divided(hex_to_int(balance_hex), safe_math.e_calc(coin.decimal))
    else:
        return ResponseObject.error(**balance_rpc_error)

    return ResponseObject.success(data=balance.to_eng_string())


def get_wallet_total_balance(project_id, coin_id):
    """目前该接口逻辑仅针对于 ETH USDT"""
    rpc = RpcConfig.get_rpc()
    if rpc is None:
        return ResponseObject.error(**out_data_missing)
    coin = Coin.get_erc20_usdt_coin()
    if coin is None:
        return ResponseObject.error(**coin_missing)
    try:
        balance = rpc.get_wallet_balance(contract=coin.contract)
    except Exception as e:
        return ResponseObject.error(**rpc_service_error)
    if balance or balance == 0:
        balance = safe_math.divided(balance, safe_math.e_calc(coin.decimal))
    else:
        return ResponseObject.error(**balance_rpc_error)
    return ResponseObject.success(data=balance.to_eng_string())


def get_tx_by_tx_hash(tx_hash: str):
    rpc = RpcConfig.get_rpc()
    if rpc is None:
        return ResponseObject.error(**out_data_missing)
    chain_info = rpc.get_block_height()

    tx = Transaction.get_tx_coin_by_tx_hash(tx_hash=tx_hash)
    if tx:
        return ResponseObject.success(data={"sender": tx.Transaction.sender,
                                            "receiver": tx.Transaction.receiver,
                                            "txHash": tx.Transaction.tx_hash,
                                            "value": safe_math.divided(tx.Transaction.amount,
                                                                       safe_math.e_calc(
                                                                           tx.Coin.decimal)
                                                                       ).to_eng_string(),
                                            "blockHeight": tx.Transaction.height,
                                            "blockTime": tx.Transaction.block_time,
                                            "contract": tx.Transaction.contract,
                                            "isValid": True if tx.Transaction.status == 1 else False,
                                            "confirmNumber": chain_info.highest_height - tx.Transaction.height
                                            if tx.Transaction.height > 0 else 0
                                            })
    else:
        tx_origin, receipt_origin = rpc.get_transaction_by_hash(tx_hash)
        if tx_origin and receipt_origin:
            tx, receipt = EthereumResolver.resolver_transaction(
                tx_origin), EthereumResolver.resolver_receipt(
                receipt_origin)
            block_info = rpc.get_block_by_number(int_to_hex(tx.block_height), False)
            if not block_info:
                return ResponseObject.error(**rpc_block_not_found)
            block = EthereumResolver.resolver_block(block_info, False)
            if tx.contract is not None:
                coin = Coin.get_erc20_usdt_coin()
            else:
                coin = Coin.get_coin(name='Ethereum')
            if coin is None:
                return ResponseObject.error(**coin_missing)
            return ResponseObject.success(data={"sender": tx.sender,
                                                "receiver": tx.receiver,
                                                "txHash": tx.tx_hash,
                                                "value": safe_math.divided(tx.value,
                                                                           safe_math.e_calc(
                                                                               coin.decimal)
                                                                           ).to_eng_string(),
                                                "blockHeight": tx.block_height,
                                                "blockTime": block.timestamp,
                                                "contract": tx.contract,
                                                "isValid": True if receipt.status == 1 else False,
                                                "confirmNumber": chain_info.highest_height - tx.block_height
                                                })
    return ResponseObject.error(**tx_miss)


def is_mine_address(project_id, address):
    address = Address.query.filter_by(project_id=project_id, address=address).first()
    if not address:
        return ResponseObject.success(data=False)
    return ResponseObject.success(data=True)


def send_transaction_handle(project_id, action_id, sender, receiver, amount, coin_id, contract):
    """
    该交易暂时只支持约定的 USDT 币种, 其他不支持, coin name 固定为 Ethereum, 其他不受理
    合约暂时也同样不支持自定义, 若合约不是 USDT 合约时, 暂不受理.
    """
    # 获取币种信息
    # if contract:
    coin = Coin.get_coin(coin_id=coin_id, contract=contract)
    # coin = Coin.query.filter_by(name=coin_name, contract=contract)
    # else:
    # 默认使用 USDT, 但币种依然需要校验
    # coin = Coin.get_coin(name=coin_name, symbol='USDT', is_master=0)
    # coin = Coin.get_erc20_usdt_coin()
    if coin is None:
        return ResponseObject.error(**coin_missing)

    if contract is None:
        contract = coin.contract

    # 检查幂等
    tx = ProjectOrder.get_tx_by_action_or_hash(action_id=action_id)
    if tx:
        return ResponseObject.success(data=tx.tx_hash)

    # 获取项目方设置的数据, 当前只有一个项目, 所以暂时不涉及此项, 如果以后我要处理多项目时再根据需求改造.
    # project_coin = ProjectCoin.get_pro_coin_by_pid_cname(project_id, coin_name)
    project_coin = ProjectCoin.get_pc_project_by_pid_cid(project_id, coin_id)
    if not project_coin:
        return False, ResponseObject.error(**sign_rsa_not_found)

    # 校验密码
    is_valid_secret, secret_result = get_secret(project_id, coin_id)
    if not is_valid_secret:
        return secret_result
    secret = secret_result

    is_valid, result, passphrase, rpc = check_passphrase(project_coin, secret)
    if not is_valid:
        return result

    # TODO 这里是硬性限制 USDT 的逻辑, 而且是强制 ERC20
    # if coin_name != 'Ethereum':
    #     return ResponseObject.error(**not_support_coin)
    # if coin.symbol != 'USDT':
    #     return ResponseObject.error(**not_support_coin)

    amount = int(safe_math.multi(amount, safe_math.e_calc(coin.decimal)))

    # TODO 因为上面的限制, 所以下面逻辑优化, 可以不判断一些复杂的东西
    if project_coin.ProjectCoin.gas == '0':
        gas = rpc.get_smart_fee(contract=contract)
    else:
        gas = project_coin.ProjectCoin.gas
    if project_coin.ProjectCoin.gas_price == '0':
        gas_price = rpc.gas_price()
    else:
        gas_price = project_coin.ProjectCoin.gas_price
    if project_coin.ProjectCoin.fee == '0' or project_coin.ProjectCoin.fee is None:
        fee = rpc.get_smart_fee()
    else:
        fee = project_coin.ProjectCoin.fee

    if gas is None:
        return ResponseObject.error(**fee_args_error)
    if gas_price is None:
        return ResponseObject.error(**fee_args_error)

    try:
        tx_hash = rpc.send_transaction(sender=sender, receiver=receiver, value=amount,
                                       passphrase=passphrase, gas=gas,
                                       gas_price=gas_price, fee=fee, contract=contract)
    except JsonRpcError as e:
        error = tx_send_error
        error['msg'] = e.message
        return ResponseObject.error(**error)
    if tx_hash:
        ProjectOrder.add(project_id, action_id, coin.id, tx_hash, amount, sender, receiver, gas,
                         gas_price,
                         contract=contract)
        return ResponseObject.success(data=tx_hash)
    return ResponseObject.error(**tx_send_error)


def set_passphrase(project_id, coin_id, secret):
    project_coin = ProjectCoin.get_pc_project_by_pid_cid(project_id, coin_id)
    if not project_coin:
        return False, ResponseObject.error(**sign_rsa_not_found)

    is_valid, result, passphrase, rpc = check_passphrase(project_coin, secret)
    if not is_valid:
        return result
    crypto = result

    coin_secret_map = {
        coin_id: {
            'secret': secret,
            'crypto': crypto
        }
    }
    if runtime.rsa_secret.get(project_id):
        runtime.rsa_secret[project_id].update(coin_secret_map)
    else:
        runtime.rsa_secret[project_id] = coin_secret_map
    return ResponseObject.success(data=True)


def set_deposit_order_id(project_id, order_id, address):
    """该接口暂时无法使用"""
    ...


def get_coin_list():
    coin_list = Coin.get_all_coin()
    return coin_list


def add_coin_ctl(master_coin_id: id, contract: str):
    contract_coin = Coin.query.filter_by(contract=contract)
    if not contract_coin:
        return ResponseObject.error(**not_support_coin)

    if contract_coin:
        return ResponseObject.error(**coin_token_already_exist)

    master_coin = Coin.query.filter_by(id=master_coin_id, is_master=DBStatusEnum.YES.value)
    if not master_coin:
        return ResponseObject.error(**coin_token_not_already_exist)

    if master_coin.is_support_token == DBStatusEnum.NO.value:
        return ResponseObject.error(**coin_support_token)

    rpc = RpcConfig.get_rpc_by_coin(master_coin_id)
    name, symbol, decimals, total = rpc.get_contract_info(contract)

    if name is None or name == "":
        return ResponseObject.error(**coin_token_error)
    if symbol is None or symbol == "":
        return ResponseObject.error(**coin_token_error)

    saved = Coin.add_coin(master_id=master_coin.id, name=name, symbol=symbol, decimal=decimals,
                          supply=total, is_master=DBStatusEnum.NO.value, bip44=0, contract=contract)

    if saved:
        return ResponseObject.success(data=True)
    return ResponseObject.error(**data_op_fail)


def get_project_info_ctl(project_id):
    """
    | coins.[].coinName | true | String | 币种名称 |
    | coins.[].hotAddress | true | String | 热钱包地址 |
    | coins.[].collectionAddress | true | String | 归集钱包地址 |
    | coins.[].renderAddress | true | String | 补充手续费钱包地址 |
    | coins.[].fee | true | String | 币种手续费 |
    | coins.[].isDeposit | true | Int | 当前是否开启充币 1 是, 0 Null 否 |
    | coins.[].isWithdraw | true | Int | 当前是否开启提币 1 是, 0 Null 否 |
    | coins.[].isCollect | true | Int | 当前是否开启归集 1 是, 0 Null 否 |
    :param project_id:
    :return:
    """
    project_info = Project.query.filter_by(project_id=project_id).first()
    if project_info is None or len(project_info) < 1:
        return ResponseObject.error(**project_miss)

    result_dict = {
        "projectId": project_id,
        "name": "",
        "callbackUrl": "",
        "accessKey": "",
        "publicKey": "",
        "coins": []
    }

    for pjt_col in project_info:
        if not result_dict['name']:
            result_dict['name'] = pjt_col.project.name
        if not result_dict['callbackUrl']:
            result_dict['callbackUrl'] = pjt_col.project.callback_url
        if not result_dict['accessKey']:
            result_dict['accessKey'] = pjt_col.project.access_key
        if not result_dict['publicKey']:
            result_dict['publicKey'] = pjt_col.project.hot_pb
        result_dict['coins'].append(
            {
                "coinId": pjt_col.coin.id,
                "coinName": pjt_col.coin.name,
                "hotAddress": pjt_col.project_coin.hot_address,
                "collectionAddress": pjt_col.project_coin.collect_address,
                "renderAddress": pjt_col.project_coin.fee_address,
                "fee": pjt_col.project_coin.fee,
                "isDeposit": pjt_col.project_coin.is_deposit,
                "isWithdraw": pjt_col.project_coin.is_withdraw,
                "isCollect": pjt_col.project_coin.is_collect
            }
        )

    return ResponseObject.success(data=result_dict)


def update_project_info_ctl(project_id, callback_url):
    project_info = Project.query.filter_by(project_id=project_id).first()
    if project_info is None:
        return ResponseObject.error(**project_miss)
    project_info.callback_url = callback_url
    try:
        project_info.save()
        return ResponseObject.success(data=True)
    except Exception:
        return ResponseObject.error(data=True)


def remove_address_ctl(project_id, coin_id, address):
    """

    :param project_id:
    :param coin_id:
    :param address:
    :return:
    """
    address = Address.get_address_by_pca(coin_id=coin_id, project_id=project_id, address=address)
    address = Address.query.filter_by(coin_id=coin_id,
                                      project_id=project_id,
                                      address=address).first()
    if not address:
        return ResponseObject.error(**data_not_found, data=False)

    address.status = DBStatusEnum.REMOVED.value
    try:
        address.save()
    except Exception as e:
        logger.error("[REMOVE ADDRESS] - 删除地址保存数据库失败: ", address.id, address.address, e)
        return ResponseObject.error(**address_remove_error)
    msg = "删除成功"
    is_success = True
    return ResponseObject.success(data=is_success, msg=msg)


def set_hot_addr_ctl(project_id, coin_id, hot_address):
    """

    :param project_id:
    :param coin_id:
    :param hot_address:
    :return:
    """
    return set_address(project_id, coin_id, 'hot_address', hot_address)


def set_collect_addr_ctl(project_id, coin_id, collect_address):
    """

    :param project_id:
    :param coin_id:
    :param collect_address:
    :return:
    """
    return set_address(project_id, coin_id, 'collect_address', collect_address)


def set_render_addr_ctl(project_id, coin_id, render_address):
    """

    :param project_id:
    :param coin_id:
    :param render_address:
    :return:
    """
    return set_address(project_id, coin_id, 'render_address', render_address)


def set_fee_ctl(project_id, coin_id, gas, gas_price, fee):
    """

    :param project_id:
    :param coin_id:
    :param gas:
    :param gas_price:
    :param fee:
    :return:
    """
    project_coin = ProjectCoin.query.filter_by(project_id=project_id, coin_id=coin_id).first()
    if not project_coin:
        return ResponseObject.error(**data_not_found, data=False)

    if gas is not None and gas:
        project_coin.gas = gas
    if gas_price is not None and gas_price:
        project_coin.gas_price = gas_price
    if fee is not None and fee:
        project_coin.fee = fee
    try:
        project_coin.save()
    except Exception as e:
        logger.error("[SET ADDRESS] - 设置钱包地址保存数据库失败: ", project_coin.id, e)
        return ResponseObject.error(**data_op_error, data=False)
    return ResponseObject.success(data=True)


def turn_status_ctl(project_id, coin_id, is_deposit, is_withdraw, is_collect):
    project_coin = ProjectCoin.query.filter_by(project_id=project_id, coin_id=coin_id).first()
    if not project_coin:
        return ResponseObject.error(**data_not_found, data=False)
    if is_deposit is not None:
        project_coin.is_deposit = is_deposit
    if is_withdraw is not None:
        project_coin.is_withdraw = is_withdraw
    if is_collect is not None:
        project_coin.is_collect = is_collect
    try:
        project_coin.save()
    except Exception as e:
        logger.error("[TURN STATUS] - 更改钱包状态保存数据库失败: ", project_coin.id, e)
        return ResponseObject.error(**data_op_error, data=False)
    return ResponseObject.success(data=True)


def add_project_coin_ctl(project_id, coin_id, hot_address, collect_address, fee_address,
                         gas, gas_price, fee, is_deposit, is_withdraw, is_collect):
    coin = Coin.query.filter_by(id=coin_id).first()
    if not coin:
        return ResponseObject.error(**coin_token_not_already_exist, data=False)
    project_coin = ProjectCoin(project_id=project_id,
                               coin_id=coin.id,
                               hot_address=hot_address,
                               gas=gas,
                               gas_price=gas_price,
                               fee=fee,
                               collect_address=collect_address,
                               fee_address=fee_address,
                               is_deposit=is_deposit,
                               is_withdraw=is_withdraw,
                               is_collect=is_collect)
    try:
        project_coin.save()
    except Exception as e:
        logger.error("[ADD PROJECT COIN] - 增加币种保存数据库失败: ", project_coin.id, e)
        return ResponseObject.error(**data_op_error, data=False)
    return ResponseObject.success(data=True)
