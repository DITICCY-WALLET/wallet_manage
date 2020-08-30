import logging
from logging.config import dictConfig
from datetime import datetime
import uuid
import requests

from blue_print.v1.controller import check_passphrase, get_secret
from coin.resolver.eth_resolver import EthereumResolver

from digit import digit
from enumer.coin_enum import SendEnum, TxTypeEum, TxStatus
from exceptions import SyncError
from models.models import Coin, Address, Transaction, RpcConfig, ProjectCoin, ProjectOrder, SyncConfig, Block, Project
from exts import db
from config import runtime
from config.config import config

dictConfig(config.LOG_CONF)
logger = logging.getLogger('flask')


class ScanEthereumChain(object):
    COIN_NAME = 'Ethereum'
    SCAN_HEIGHT_NUMBER = 50
    SCAN_DELAY_NUMBER = 20

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
        while self.current_scan_height <= need_to_height:
            logger.info('当前已扫块高度：{} 最新高度：{} 需要同步：{}  节点最高高度：{}'.format(
                self.current_scan_height, self.newest_height,
                need_to_height - self.current_scan_height,
                self.highest_height))

            # 分批处理, 一次处理 SCAN_HEIGHT_NUMBER 个块
            for height in range(self.current_scan_height + 1, need_to_height, self.SCAN_HEIGHT_NUMBER):
                blocks = self.rpc.get_block_by_number([digit.int_to_hex(height) for height in
                                                       range(height, height + self.SCAN_HEIGHT_NUMBER)])
                with runtime.app.app_context():
                    # 一次处理一批
                    session = db.session()
                    try:
                        for block in blocks:
                            block_height = digit.hex_to_int(block['number'])
                            block_hash = block['hash']
                            block_timestamp = digit.hex_to_int(block['timestamp'])
                            block_time = datetime.fromtimestamp(block_timestamp)

                            session.begin(subtransactions=True)
                            db_block = Block(height=block_height, block_hash=block_hash, block_time=block_time)
                            session.add(db_block)
                            session.commit()

                            for transaction in block.get('transactions', []):
                                sender = transaction['from']
                                receiver = transaction['to']
                                if sender in runtime.project_address:
                                    # 提现的暂时不要
                                    continue
                                if receiver in runtime.project_address:
                                    tx = EthereumResolver.resolver_transaction(transaction)
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
                                        logger.error('请求 {} receipt 错误, 重新处理')
                                        raise
                                    tx.status = receipt_tx.status
                                    # session.begin(subtransactions=True)
                                    db_tx = Transaction(block_id=block.id, coin_id=coin['coin_id'],
                                                        tx_hash=tx.tx_hash, height=block.height,
                                                        block_time=block_timestamp,
                                                        amount=tx.value, sender=tx.sender, receiver=tx.receiver,
                                                        gas=tx.gas, gas_price=tx.gas_price, is_send=SendEnum.NOT_PUSH,
                                                        fee=receipt_tx.gas_used * tx.gas_price,
                                                        contract=tx.contract, status=receipt_tx.status,
                                                        type=TxTypeEum.DEPOSIT)
                                    session.add(db_tx)
                                    # session.commit()
                                    # 添加推送信息

                        session.query(SyncConfig).filter(SyncConfig.id == self.config_id).update(
                            {'synced_height': height + self.SCAN_HEIGHT_NUMBER,
                             'highest_height': self.highest_height}
                        )
                        session.commit()

                    except Exception as e:
                        logger.error('同步块出现异常, 事务回滚. {}'.format(e))
                        session.rollback()
                        return


class DepositEthereumChain(object):
    COIN_NAME = 'Ethereum'

    def __init__(self):
        self.project = {}

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
        no_push_txs = Transaction.query.filter(is_send=SendEnum.NOT_PUSH)
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
                logger.error("请求为 {} 上账不成功, 内容 {}, 错误： {}".format(project['name'], params, e))
                continue
            if rsp.status_code == 200:
                with runtime.app.app_context():
                    session = db.session()
                    session.query(Transaction).filter(tx.hash == tx_hash).update(
                        {'is_send': SendEnum.PUSHED})
                    session.commit()


class CollectionEthereumChain(object):
    COIN_NAME = 'Ethereum'
    BALANCE_QUERY_NUMBER = 100

    def __init__(self):
        self.project_addresses = {}
        self.rpc = None

        self._init()

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
            for project in self.project_addresses:
                project_id = project['project_id']
                coin_name = self.COIN_NAME
                project_coin = ProjectCoin.get_pro_coin_by_pid_cname(project_id, coin_name)
                is_valid_secret, secret_result = get_secret(project_id, coin_name)
                if not is_valid_secret:
                    continue
                secret = secret_result
                is_valid, result, passphrase, rpc = check_passphrase(project_coin, secret)
                self.rpc = rpc
                self.project_addresses[project_id]['passphrase'] = passphrase

    def collection(self):
        for p in self.project_addresses:
            project_address = p['address']
            for coin in runtime.coins:
                contract = coin['contract']
                offset, count = 0, self.BALANCE_QUERY_NUMBER
                for s in range(0, len(p['address']), count):
                    addresses = project_address[offset, count]
                    balances = self.rpc.get_balance(addresses, contract)
                    balances_sum = sum([digit.hex_to_int(balance) for balance in balances if balance])
                    if not balances_sum:
                        logger.info("本 {} 个地址不需要归集".format(len(addresses)))
                        continue
                    for idx, balance in enumerate(balances):
                        if balance:
                            if not hasattr(config, 'GAS'):
                                gas = config.GAS
                            else:
                                gas = self.rpc.get_smart_fee(contract=contract)

                            if not hasattr(config, 'GAS_PRICE'):
                                gas_price = config.GAS_PRICE
                            else:
                                gas_price = self.rpc.gas_price()

                            if gas is None:
                                logger.info("未找到合适 gas . {}".format(gas))
                                continue
                            if gas_price is None:
                                logger.info("未找到合适 gas_price . {}".format(gas_price))
                                continue

                            tx_hash = self.rpc.send_transaction(sender=addresses[idx], receiver=config.COLLECTION_ADDRESS,
                                                      value=balance, passphrase=p['passphrase'],
                                                      gas=gas, gas_price=gas_price, contract=contract)
                            with runtime.app.app_context():
                                saved = Transaction.add_transaction(
                                    coin_id=coin['coin_id'], tx_hash=tx_hash, block_time=datetime.now(),
                                    sender=addresses[idx], receiver=config.COLLECTION_ADDRESS, amount=balance,
                                    status=TxStatus.UNKNOWN, type=TxTypeEum.COLLECTION,
                                    block_id=-1, height=-1, gas=gas, gas_price=gas_price,
                                    contract=contract)

                    offset += count


def run_sync():
    eth_chain = ScanEthereumChain()
    eth_chain.scan()


def notify_project():
    eth_notify = DepositEthereumChain()
    eth_notify.deposit()


def collection_eth():
    eth_collect = CollectionEthereumChain()
    eth_collect.collection()
