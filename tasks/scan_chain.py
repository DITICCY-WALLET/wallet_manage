from datetime import datetime
import uuid
import requests

from blue_print.v1.controller import check_passphrase, get_secret
from coin.resolver.eth_resolver import EthereumResolver

from digit import digit
from digit.digit import hex_to_int
from enumer.coin_enum import SendEnum, TxTypeEnum, TxStatusEnum
from exceptions import SyncError, PasswordError
from models.models import Coin, Address, Transaction, RpcConfig, ProjectCoin, ProjectOrder, SyncConfig, Block, Project
from exts import db
from config import runtime
from config.config import config
from log import logger_attr


@logger_attr
class ScanEthereumChain(object):
    """扫链"""
    COIN_NAME = 'Ethereum'
    SCAN_HEIGHT_NUMBER = 50
    SCAN_DELAY_NUMBER = 12

    def __init__(self):
        self.rpc = None
        self.current_scan_height = None
        self.newest_height = None
        self.highest_height = None

        self.block_info = None
        self.db_sync_info = None
        self.config_id = None

        self._init()

    def _init(self):
        with runtime.app.app_context():
            self.rpc = RpcConfig.get_rpc()
            if self.rpc is None:
                raise SyncError('未找到需要定义的RPC')

            self.block_info = self.rpc.get_block_height()
            self.db_sync_info = SyncConfig.get_sync_info(self.COIN_NAME)
            if not self.db_sync_info:
                raise SyncError('未找到需要定义的RPC')
            self.current_scan_height = self.db_sync_info.SyncConfig.synced_height
            self.config_id = self.db_sync_info.SyncConfig.id

    @classmethod
    def read_address(cls):
        with runtime.app.app_context():
            addresses = Address.get_coin_address_by_coin_name(cls.COIN_NAME)
            for address in addresses:
                runtime.project_address.update({address[0]: {'project_id': address[1],
                                                             'coin_id': address[2],
                                                             'coin_name': address[3],
                                                             }
                                                })

    @classmethod
    def read_coins(cls):
        with runtime.app.app_context():
            coins = Coin.query.all()
            for coin in coins:
                c = coin.contract or coin.name
                runtime.coins[c] = {
                    "coin_id": coin.id,
                    "coin_name": coin.name,
                    "contract": coin.contract,
                    "decimal": coin.decimal,
                    "symbol": coin.symbol
                }

    def scan(self):
        self.block_info = self.rpc.get_block_height()
        self.newest_height = self.block_info.current_height
        self.highest_height = self.block_info.highest_height
        # 延迟扫 SCAN_DELAY_NUMBER 个块
        need_to_height = self.newest_height - self.SCAN_DELAY_NUMBER
        self.logger.info('起始扫块高度：{} 最新高度：{} 需要同步：{}'.format(
            self.current_scan_height,
            self.newest_height,
            need_to_height - self.current_scan_height))
        while self.current_scan_height < need_to_height:
            self.logger.info('当前已扫块高度：{} 最新高度：{} 需要同步：{}  节点最高高度：{}'.format(
                self.current_scan_height, self.newest_height,
                need_to_height - self.current_scan_height,
                self.highest_height))

            for height in range(self.current_scan_height, need_to_height, self.SCAN_HEIGHT_NUMBER):
                # 分批处理, 一次处理 SCAN_HEIGHT_NUMBER 或 剩余要处理的块
                block_batch = min(self.SCAN_HEIGHT_NUMBER, need_to_height - self.current_scan_height)

                blocks = self.rpc.get_block_by_number([digit.int_to_hex(height) for height in
                                                       range(height, height + block_batch)])
                save_tx_count = 0
                with runtime.app.app_context():
                    # 一次处理一批
                    session = db.session()
                    try:
                        for block in blocks:
                            if block is None:
                                return
                            block_height = digit.hex_to_int(block['number'])
                            block_hash = block['hash']
                            block_timestamp = digit.hex_to_int(block['timestamp'])
                            block_time = datetime.fromtimestamp(block_timestamp)

                            session.begin(subtransactions=True)
                            db_block = Block(height=block_height, block_hash=block_hash, block_time=block_time)
                            session.add(db_block)
                            session.commit()

                            for transaction in block.get('transactions', []):
                                tx = EthereumResolver.resolver_transaction(transaction)
                                if tx.sender in runtime.project_address:
                                    # 提现的暂时不要
                                    continue
                                if tx.receiver in runtime.project_address:
                                    receipt_raw_tx = self.rpc.get_transaction_receipt(tx.tx_hash)
                                    if tx.contract:
                                        coin = runtime.coins.get(tx.contract)
                                    else:
                                        coin = runtime.coins.get(self.COIN_NAME)
                                    if coin is None:
                                        continue

                                    if receipt_raw_tx:
                                        receipt_tx = EthereumResolver.resolver_receipt(receipt_raw_tx)
                                    else:
                                        self.logger.error('请求 {} receipt 错误, 重新处理')
                                        raise
                                    tx.status = receipt_tx.status
                                    # session.begin(subtransactions=True)
                                    # db_tx = Transaction(block_id=db_block.id, coin_id=coin['coin_id'],
                                    #                     tx_hash=tx.tx_hash, height=db_block.height,
                                    #                     block_time=block_timestamp,
                                    #                     amount=tx.value, sender=tx.sender, receiver=tx.receiver,
                                    #                     gas=tx.gas, gas_price=tx.gas_price,
                                    #                     is_send=SendEnum.NOT_PUSH.value,
                                    #                     fee=receipt_tx.gas_used * tx.gas_price,
                                    #                     contract=tx.contract, status=receipt_tx.status,
                                    #                     type=TxTypeEnum.DEPOSIT.value)
                                    Transaction.add_transaction_or_update(
                                        block_id=db_block.id, coin_id=coin['coin_id'],
                                        tx_hash=tx.tx_hash, height=db_block.height,
                                        block_time=block_timestamp,
                                        amount=tx.value, sender=tx.sender, receiver=tx.receiver,
                                        gas=tx.gas, gas_price=tx.gas_price,
                                        is_send=SendEnum.NOT_PUSH.value,
                                        fee=receipt_tx.gas_used * tx.gas_price,
                                        contract=tx.contract, status=receipt_tx.status,
                                        type=TxTypeEnum.DEPOSIT.value, session=session, commit=False
                                    )
                                    save_tx_count += 1
                                    # session.add(db_tx)
                                    # session.commit()
                                    # 添加推送信息

                        session.query(SyncConfig).filter(SyncConfig.id == self.config_id).update(
                            {'synced_height': height + block_batch,
                             'highest_height': self.highest_height}
                        )
                        self.current_scan_height = height + block_batch
                        session.commit()
                        self.logger.info("本次同步高度为：{} -- {}, 保存交易： {} 笔".format(height, height + block_batch, save_tx_count))

                    except Exception as e:
                        self.logger.error('同步块出现异常, 事务回滚. {}'.format(e))
                        session.rollback()
                        return
        self.logger.info("扫链结束, 本次同步")


@logger_attr
class DepositEthereumChain(object):
    """
    充值上账
    """
    COIN_NAME = 'Ethereum'

    def __init__(self):
        self.project = {}
        self._init()

    def _init(self):
        with runtime.app.app_context():
            projects = Project.query.all()
            for project in projects:
                self.project.update(
                    {project.id: {
                        "name": project.name,
                        "url": project.callback_url,
                        "access_key": project.access_key,
                        "secret_key": project.secret_key,
                    }
                    })

    def deposit(self):
        self.logger.info("开始上账进程")
        with runtime.app.app_context():
            no_push_txs = Transaction.query.filter(Transaction.is_send == SendEnum.NOT_PUSH.value)
            for tx in no_push_txs:
                receiver = tx.receiver
                project_addr = runtime.project_address.get(receiver)
                if not project_addr:
                    continue
                project = self.project.get(project_addr['project_id'])
                tx_hash = tx.tx_hash
                url = project['url']
                params = {
                    "txHash": tx.tx_hash,
                    "blockHeight": tx.height,
                    "amount": tx.amount,
                    "address": tx.receiver,
                    "orderid": uuid.uuid4().hex
                }
                try:
                    rsp = requests.post(url, params=params)
                except Exception as e:
                    self.logger.error("请求为 {} 上账不成功, 内容 {}, 错误： {}".format(project['name'], params, e))
                    continue
                if rsp.status_code == 200:
                    session = db.session()
                    session.query(Transaction).filter(tx.hash == tx_hash).update(
                        {'is_send': SendEnum.PUSHED.value})
                    session.commit()
        self.logger.info("结束上账进程")


@logger_attr
class ProjectAddressInitMixin(object):
    def _init(self):
        project_addr = runtime.project_address
        for addr, addr_info in project_addr.items():
            if self.project_addresses.get(addr_info['project_id']):
                self.project_addresses[addr_info['project_id']]['address'].append(addr)
            else:
                self.project_addresses[addr_info['project_id']] = {
                    "project_id": addr_info['project_id'],
                    "address": [addr]
                }
        with runtime.app.app_context():
            for pk, project in self.project_addresses.items():
                project_id = project['project_id']
                coin_name = self.COIN_NAME
                project_coin = ProjectCoin.get_pro_coin_by_pid_cname(project_id, coin_name)
                is_valid_secret, secret_result = get_secret(project_id, coin_name)
                if not is_valid_secret:
                    self.logger.error("归集程序未设置密码..")
                    raise PasswordError("归集程序未设置密码..")
                secret = secret_result
                is_valid, result, passphrase, rpc = check_passphrase(project_coin, secret)
                self.rpc = rpc
                self.project_addresses[project_id]['passphrase'] = passphrase


@logger_attr
class CollectionEthereumChain(ProjectAddressInitMixin):
    """
    归集
    """
    COIN_NAME = 'Ethereum'
    BALANCE_QUERY_NUMBER = 100

    def __init__(self):
        self.project_addresses = {}
        self.rpc = None

        self._init()

    def collection(self):
        self.logger.info('开始归集进程')
        for pid, p in self.project_addresses.items():
            project_address = p['address']
            for ck, coin in runtime.coins.items():
                contract = coin['contract']
                offset, count = 0, self.BALANCE_QUERY_NUMBER
                for s in range(0, len(project_address), count):
                    addresses = project_address[offset:count]
                    balances = self.rpc.get_balance(addresses, contract)
                    balances_sum = sum([digit.hex_to_int(balance) for balance in balances if balance])
                    if not balances_sum:
                        self.logger.info("本 {} 个地址不需要归集".format(len(addresses)))
                        continue
                    for idx, balance in enumerate(balances):
                        balance_int = hex_to_int(balance)
                        if not balance_int:
                            continue
                        if hasattr(config, 'GAS'):
                            gas = config.GAS
                        else:
                            gas = self.rpc.get_smart_fee(contract=contract)

                        if hasattr(config, 'GAS_PRICE'):
                            gas_price = config.GAS_PRICE
                        else:
                            gas_price = self.rpc.gas_price()

                        if gas is None:
                            self.logger.info("未找到合适 gas . {}".format(gas))
                            continue
                        if gas_price is None:
                            self.logger.info("未找到合适 gas_price . {}".format(gas_price))
                            continue

                        gas, gas_price = hex_to_int(gas), hex_to_int(gas_price)
                        fee = gas * gas_price
                        if coin['symbol'] == 'ETH':
                            send_value = max(balance_int - max(int(config.COLLECTION_MIN_ETH * 1e18), fee), 0)
                        else:
                            send_value = balance_int

                        if send_value <= 0:
                            self.logger.info("地址 {} 需要归集金额低于 0".format(addresses[idx]))
                            continue

                        tx_hash = self.rpc.send_transaction(
                            sender=addresses[idx], receiver=config.COLLECTION_ADDRESS,
                            value=send_value, passphrase=p['passphrase'],
                            gas=gas, gas_price=gas_price, contract=contract)
                        with runtime.app.app_context():
                            saved = Transaction.add_transaction(
                                coin_id=coin['coin_id'], tx_hash=tx_hash, block_time=datetime.now().timestamp(),
                                sender=addresses[idx], receiver=config.COLLECTION_ADDRESS, amount=send_value,
                                status=TxStatusEnum.UNKNOWN.value, type=TxTypeEnum.COLLECTION.value,
                                block_id=-1, height=-1, gas=gas, gas_price=gas_price,
                                contract=contract)

                    offset += count
        self.logger.info("结束归集进程")


@logger_attr
class RenderFee(ProjectAddressInitMixin):
    """
    补充手续费
    """
    COIN_NAME = 'Ethereum'
    BALANCE_QUERY_NUMBER = 100

    def __init__(self):
        self.project_addresses = {}
        self.rpc = None

        self._init()

    def render(self):
        self.logger.info('开始补充手续费进程')
        for pid, p in self.project_addresses.items():
            project_address = p['address']
            for ck, coin in runtime.coins.items():
                if coin['coin_name'] == self.COIN_NAME:
                    self.logger.warning('币种名称为: {}, 不需要补充手续费!'.format(coin['coin_name']))
                    continue
                contract = coin['contract']
                offset, count = 0, self.BALANCE_QUERY_NUMBER
                for s in range(0, len(project_address), count):
                    addresses = project_address[offset:count]
                    balances = self.rpc.get_balance(addresses, contract)
                    balances_sum = sum([digit.hex_to_int(balance) for balance in balances if balance])
                    if not balances_sum:
                        self.logger.info("本 {} 个地址无额外, 不需要补充手续费".format(len(addresses)))
                        continue
                    for idx, balance in enumerate(balances):
                        balance_int = hex_to_int(balance)
                        if not balance_int:
                            continue
                        balance_eth_int = hex_to_int(self.rpc.get_balance(address=addresses[idx]))

                        if hasattr(config, 'GAS'):
                            gas = config.GAS
                        else:
                            gas = self.rpc.get_smart_fee(contract=contract)
                        if hasattr(config, 'GAS_PRICE'):
                            gas_price = config.GAS_PRICE
                        else:
                            gas_price = self.rpc.gas_price()
                        if gas is None:
                            self.logger.info("未找到合适 gas . {}".format(gas))
                            continue
                        if gas_price is None:
                            self.logger.info("未找到合适 gas_price . {}".format(gas_price))
                            continue
                        gas, gas_price = hex_to_int(gas), hex_to_int(gas_price)
                        fee = gas * gas_price

                        if balance_eth_int > fee:
                            self.logger.info("地址: {} 手续费足够, 不需要补充手续费".format(addresses[idx]))
                            continue

                        render_amount = int(config.COLLECTION_MIN_ETH * 1e18)

                        tx_hash = self.rpc.send_transaction(
                            sender=config.RENDER_ADDRESS, receiver=addresses[idx],
                            value=render_amount, passphrase=p['passphrase'],
                            gas=gas, gas_price=gas_price, contract=contract)
                        if not tx_hash:
                            self.logger.error("给地址: {} 补充手续费失败".format(addresses[idx]))
                            continue
                        self.logger.info("给地址: {} 补充手续费成功".format(addresses[idx]))
                        with runtime.app.app_context():
                            saved = Transaction.add_transaction(
                                coin_id=coin['coin_id'], tx_hash=tx_hash, block_time=datetime.now().timestamp(),
                                sender=config.RENDER_ADDRESS, receiver=addresses[idx], amount=render_amount,
                                status=TxStatusEnum.UNKNOWN.value, type=TxTypeEnum.RENDER.value,
                                block_id=-1, height=-1, gas=gas, gas_price=gas_price,
                                contract=contract)
        self.logger.info('结束补充手续费进程')


def run_sync():
    eth_chain = ScanEthereumChain()
    eth_chain.scan()


def notify_project():
    eth_notify = DepositEthereumChain()
    eth_notify.deposit()


def collection_eth():
    eth_collect = CollectionEthereumChain()
    eth_collect.collection()


def render_eth():
    eth_render = RenderFee()
    eth_render.render()
