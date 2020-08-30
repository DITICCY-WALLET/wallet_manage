from datetime import datetime

from sqlalchemy import UniqueConstraint

from coin.driver.driver_base import DriverFactory
from exts import db
from flask_sqlalchemy import orm

from httplibs.coinrpc.rpcbase import RpcBase


class ApiAuth(db.Model):
    __tablename__ = 'api_auth'
    __table_args__ = (
        # 确保一个项目方只能有一个 key
        UniqueConstraint('access_key', 'project_id', name='uk_access_key_project_id'),
        {'mysql_engine': "INNODB"}
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    access_key = db.Column(db.VARCHAR(128), nullable=False, comment="key", unique=True)
    secret_key = db.Column(db.VARCHAR(128), comment="secret")
    ip = db.Column(db.VARCHAR(128), comment='受限IP地址')
    status = db.Column(db.SmallInteger, default=1, comment='是否启用 1：启用 0：禁用')
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    def __str__(self):
        return ' -'.join(
            [str(self.id), str(self.access_key), str(self.secret_key), str(self.create_time), str(self.update_time)])


class Block(db.Model):
    __tablename__ = 'block'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    height = db.Column(db.Integer, nullable=False, comment="块高度", unique=True)
    block_hash = db.Column(db.VARCHAR(128), nullable=False, comment="块hash", unique=True)
    block_time = db.Column(db.DateTime, nullable=False, comment="块时间")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)


class Coin(db.Model):
    __tablename__ = 'coin'
    __table_args__ = (
        UniqueConstraint('master_id', 'contract', name='uk_master_id_contract'),
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    master_id = db.Column(db.Integer, unique=False, default=0, comment="主链ID")
    name = db.Column(db.String(64), unique=True, comment='币种名称')
    symbol = db.Column(db.String(64), comment='缩写')
    decimal = db.Column(db.SmallInteger, nullable=False, default=0, comment='小数位')
    supply = db.Column(db.BigInteger, comment='发行量')
    is_master = db.Column(db.SmallInteger, default=1, comment='是否主链币 1 是 0 否')
    bip44 = db.Column(db.Integer, default=1, comment='bip44 编码')
    contract = db.Column(db.VARCHAR(128), comment="代币名称", unique=True)
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)

    sync_config = orm.relationship('SyncConfig',
                                   primaryjoin="SyncConfig.coin_id==Coin.id",
                                   foreign_keys="Coin.id",
                                   backref="Coin")

    address = orm.relationship('Address',
                               primaryjoin="Address.coin_id==Coin.id",
                               foreign_keys="Coin.id",
                               backref="Coin")

    @staticmethod
    def get_coin(contract=None, symbol=None, name=None, is_master=1):
        params = {'is_master': is_master}
        if contract is not None:
            params['contract'] = contract
            params['is_master'] = 0
        if symbol is not None:
            params['symbol'] = symbol
        if name is not None:
            params['name'] = name
        coin = Coin.query.filter_by(**params).first()
        if not coin:
            return None
        return coin

    @staticmethod
    def get_erc20_usdt_coin():
        """获取 ETH 的 ERC20 USDT"""
        coin = Coin.get_coin(symbol='USDT', name="Ethereum", is_master=0)
        if not coin:
            return None
        return coin


class Address(db.Model):
    __tablename__ = 'address'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coin_id = db.Column(db.Integer, nullable=False, comment="币种ID", unique=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目方 ID")
    address = db.Column(db.VARCHAR(128), unique=True, nullable=False, comment="地址")
    address_type = db.Column(db.SmallInteger, default=0, comment="地址类型，0充 1提")
    is_send = db.Column(db.SmallInteger, default=0, index=True, comment="是否已给予，0否 1是")
    status = db.Column(db.SmallInteger, default=1, comment="是否有效，0否 1是")
    create_time = db.Column(db.DateTime, nullable=False, comment="生成时间", default=datetime.now)

    coin = orm.relationship('Coin',
                            primaryjoin="Address.coin_id==Coin.id",
                            foreign_keys="Address.coin_id",
                            backref="Address")

    transaction = orm.relationship('Transaction',
                                   primaryjoin="Address.address==Transaction.receiver",
                                   foreign_keys="Address.address",
                                   backref="Address")

    project = orm.relationship('Project',
                               primaryjoin="Address.project_id==Project.id",
                               foreign_keys="Address.project_id",
                               backref="Address")

    @staticmethod
    def add_address(project_id, coin_id, address, address_type=0, is_send=0, *, commit=True):
        address = Address(project_id=project_id, coin_id=coin_id, address=address,
                          address_type=address_type, is_send=is_send)
        session = db.session()
        saved = session.add(address)
        if commit:
            session.commit()
            return saved
        return session

    @staticmethod
    def add_addresses(addresses: list, *, commit=True):
        """
        添加多个地址进入数据库, 字段仅是将 address中的拆解, 其他都一样,
        :param addresses: lidt<dict>, [{project_id, coin_id, address, address_type, is_send}]
        :param commit:
        :return:
        """
        session = db.session()
        for address_dict in addresses:
            address = Address(**address_dict)
            session.add(address)
        if commit:
            return None
        return session

    @staticmethod
    def get_coin_address_by_coin_name(coin_name):
        """
        这种方式返回的格式固定为 list<tuple<row>>
        row 取决于 with_entities 里面的字段
        :return address, project_id, coin_id, coin_name
        """
        session = db.session()
        addresses = session.query(Address, Coin).join(
            Address, Address.coin_id == Coin.id).with_entities(Address.address, Address.project_id, Address.coin_id,
                                                               Coin.name).filter(Coin.name == coin_name).all()
        return addresses


class Transaction(db.Model):
    __tablename__ = 'tx'
    __table_args__ = (
        UniqueConstraint('block_id', 'coin_id', name='uk_block_id_coin_id'),
        UniqueConstraint('tx_hash', 'coin_id', name='uk_tx_hash_coin_id'),
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    block_id = db.Column(db.Integer, nullable=False, comment="块表关联键", index=True)
    coin_id = db.Column(db.Integer, nullable=False, comment="币种表关联键", index=True)
    tx_hash = db.Column(db.VARCHAR(128), nullable=False, comment="交易hash")
    height = db.Column(db.Integer, nullable=False, comment="交易所在高度", index=True)
    block_time = db.Column(db.Integer, nullable=False, comment="交易时间戳")
    amount = db.Column(db.VARCHAR(64), nullable=False, comment="交易金额")
    sender = db.Column(db.VARCHAR(128), nullable=False, comment="发送人")
    receiver = db.Column(db.VARCHAR(128), nullable=False, comment="接收人")
    gas = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额， ETH使用")
    gas_price = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额, ETH使用")
    fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真手续费金额, ETH为 gas * gas_price")
    contract = db.Column(db.VARCHAR(128), comment="代币名称或地址")
    status = db.Column(db.SmallInteger, nullable=False, comment="交易是否有效 1）有效 0）无效 2) 未知")
    type = db.Column(db.SmallInteger, nullable=False, comment="交易类型")
    is_send = db.Column(db.SmallInteger, nullable=False, comment="是否推送 0) 未推 1) 已推 2) 不用推")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    coin = orm.relationship('Coin',
                            primaryjoin="Transaction.coin_id==Coin.id",
                            foreign_keys="Transaction.coin_id",
                            backref="Transaction")

    @classmethod
    def get_tx_coin_tx(cls, **params):
        session = db.session()
        block_tx = session.query(Transaction, Coin).join(Transaction.coin_id == Coin.id).filter(**params)
        return block_tx

    @classmethod
    def get_tx_coin_by_tx_hash(cls, tx_hash):
        return cls.get_tx_coin_tx(tx_hash=tx_hash).first()

    @classmethod
    def add_transaction(cls, coin_id, tx_hash, block_time, sender, receiver, amount, status, type,
                        block_id, height, gas=0, gas_price=0, fee=0,
                        contract=None, *, commit=True):
        session = db.session()

        tx = Transaction(coin_id=coin_id, tx_hash=tx_hash, block_time=block_time, sender=sender, receiver=receiver,
                         amount=amount, status=status, type=type, gas=gas, gas_price=gas_price, fee=fee,
                         contract=contract, block_id=block_id, height=height)
        # saved 如果成功情况下是 None
        saved = session.add(tx)
        if commit:
            # 自动提交
            session.commit()
            return saved
        # 返回 session 等待自行处理
        return session


class RpcConfig(db.Model):
    __tablename__ = 'rpc_config'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coin_id = db.Column(db.Integer, unique=False, default=0, comment="主链ID")
    name = db.Column(db.VARCHAR(32), comment="配置币种名称")
    driver = db.Column(db.VARCHAR(64), comment="驱动类型. 当前仅使用 ETHEREUM")
    host = db.Column(db.VARCHAR(256), comment="节点地址, 请写完整 http[s]://[user]:[passwd]@[ip|domain]:[port]")
    status = db.Column(db.SmallInteger, default=1, comment="是否有效，0否 1是")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    @staticmethod
    def get_rpc() -> RpcBase:
        rpc_config = RpcConfig.query.filter_by(driver='Ethereum', status=1).first()
        if not rpc_config:
            return None
        driver = rpc_config.driver
        host = rpc_config.host
        rpc = DriverFactory(driver, host)
        return rpc


class Project(db.Model):
    """项目方"""
    __tablename__ = 'project'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.VARCHAR(32), comment="项目名称")
    callback_url = db.Column(db.VARCHAR(256), comment="回调地址, 请写完整 http[s]://[user]:[passwd]@[ip|domain]:[port]")
    access_key = db.Column(db.VARCHAR(128), comment="回调签名 access_key")
    secret_key = db.Column(db.VARCHAR(128), comment="回调签名 secret_key")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    project_coin = orm.relationship('ProjectCoin',
                                    primaryjoin="Project.id==ProjectCoin.project_id",
                                    foreign_keys="Project.id",
                                    backref="Project")


class ProjectCoin(db.Model):
    """项目方支持的币种"""
    __tablename__ = 'project_coin'
    __table_args__ = (
        UniqueConstraint('project_id', 'coin_id', name='uk_project_id_coin_id'),
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    coin_id = db.Column(db.Integer, nullable=False, comment="主链币 ID")
    hot_address = db.Column(db.VARCHAR(128), nullable=False, comment="热钱包地址")
    hot_secret = db.Column(db.VARCHAR(128), nullable=False, comment="热钱包密钥, 保留字段, 未使用")
    hot_pb = db.Column(db.TEXT, comment="热钱包公钥")
    hot_pk = db.Column(db.TEXT, comment="热钱包私钥")
    gas = db.Column(db.VARCHAR(64), nullable=False, default='150000',
                    comment="gas， ETH使用, 如果不给出确定性的, 则使用150000, 如果为0则表示使用使用系统判断")
    gas_price = db.Column(db.VARCHAR(64), nullable=False, default=str(20 * 1000 * 1000 * 1000),
                          comment="gasPrice, 如果不给出, 则默认按20G, 如果为0则表示使用使用系统判断")
    fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真手续费金额, ETH为 gas * gas_price")
    cold_address = db.Column(db.VARCHAR(128), nullable=False, comment="冷钱包地址")
    last_collection_time = db.Column(db.DateTime, default=None, comment="最后归集时间", onupdate=datetime.now)
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    project = orm.relationship('Project',
                               primaryjoin="ProjectCoin.project_id==Project.id",
                               foreign_keys="ProjectCoin.project_id",
                               backref="ProjectCoin")

    coin = orm.relationship('Coin',
                            primaryjoin="ProjectCoin.project_id==Coin.id",
                            foreign_keys="ProjectCoin.project_id",
                            backref="ProjectCoin")

    @staticmethod
    def get_pro_coin_by_pid_cname(project_id, coin_name):
        session = db.session()
        project_coin = session.query(ProjectCoin, Coin).join(Coin, ProjectCoin.coin_id == Coin.id).filter(
            ProjectCoin.project_id == project_id, Coin.name == coin_name)
        return project_coin.first()


class ProjectOrder(db.Model):
    """项目方订单"""
    __tablename__ = 'project_order'
    __table_args = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    action_id = db.Column(db.VARCHAR(128), nullable=False, unique=True, comment="执行ID, 唯一编码, 控制幂等")
    coin_id = db.Column(db.Integer, nullable=False, comment="币种表关联键", index=True)
    tx_hash = db.Column(db.VARCHAR(128), nullable=False, comment="交易hash", unique=True)
    amount = db.Column(db.VARCHAR(64), nullable=False, comment="交易金额")
    sender = db.Column(db.VARCHAR(128), nullable=False, comment="发送人")
    receiver = db.Column(db.VARCHAR(128), nullable=False, comment="接收人")
    gas = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额， ETH使用")
    gas_price = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额, ETH使用")
    fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真手续费金额, ETH为 gas * gas_price")
    contract = db.Column(db.VARCHAR(128), comment="代币名称或地址")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    @classmethod
    def get_tx_by_action_or_hash(cls, action_id=None, tx_hash=None):
        params = {}
        if action_id:
            params['action_id'] = action_id
        if tx_hash:
            params['tx_hash'] = tx_hash

        tx = ProjectOrder.query.filter_by(**params).first()
        return tx

    @classmethod
    def add(cls, project_id, action_id, coin_id, tx_hash, amount, sender, receiver, gas=0, gas_price=0, fee=0,
            contract=None):
        session = db.session()
        tx = ProjectOrder(project_id=project_id, action_id=action_id, coin_id=coin_id, tx_hash=tx_hash,
                          amount=amount, sender=sender, receiver=receiver, gas=gas, gas_price=gas_price,
                          fee=fee, contract=contract)
        tx_saved = session.add(tx)
        session.commit()
        return tx_saved


class ProjectDeposit(db.Model):
    """项目方订单"""
    __tablename__ = 'project_deposit'
    __table_args = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    tx_id = db.Column(db.Integer, nullable=False, comment="币种ID", index=True)
    order_id = db.Column(db.VARCHAR(128), nullable=False, index=True, comment="充值订单号")
    address = db.Column(db.VARCHAR(128), nullable=False, comment="订单绑定地址")
    is_send = db.Column(db.SmallInteger, nullable=False, comment="是否推送 0) 未推 1) 已推 2) 不用推")
    # tx_hash = db.Column(db.VARCHAR(128), nullable=False, comment="交易hash", unique=True)
    # amount = db.Column(db.VARCHAR(64), nullable=False, comment="交易金额")
    # sender = db.Column(db.VARCHAR(128), nullable=False, comment="发送人")
    # receiver = db.Column(db.VARCHAR(128), nullable=False, comment="接收人")
    # gas = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额， ETH使用")
    # gas_price = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额, ETH使用")
    # fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真手续费金额, ETH为 gas * gas_price")
    # contract = db.Column(db.VARCHAR(128), comment="代币名称或地址")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    def not_match_tx(self):
        ...


class SyncConfig(db.Model):
    """项目方支持的币种"""
    __tablename__ = 'sync_config'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    coin_id = db.Column(db.Integer, nullable=False, comment="主链币 ID", index=True)
    synced_height = db.Column(db.Integer, nullable=False, comment="已同步高度")
    highest_height = db.Column(db.Integer, nullable=False, comment="最新高度")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间", default=datetime.now, onupdate=datetime.now)

    coin = orm.relationship('Coin',
                            primaryjoin="SyncConfig.coin_id==Coin.id",
                            foreign_keys="SyncConfig.coin_id",
                            backref="SyncConfig")

    @staticmethod
    def get_sync_info(coin_name):
        session = db.session()
        coin_sync = session.query(SyncConfig, Coin).join(SyncConfig, SyncConfig.coin_id == Coin.id).filter(
            Coin.name == coin_name).first()
        return coin_sync


if __name__ == '__main__':
    from flask import Flask
    from exts import db
    from config.config import config
    import datetime

    app = Flask(__name__)
    app.config.from_object(config)

    db.init_app(app)
    app.app_context().push()

    # db.create_all()

    # result = Transaction.add_transaction(1, 'tx_hash3', 123211, 'sender', 'receiver', 100, 1, 1, 3, 3)
    # print(result)
    # session = db.session()

    # result = Transaction.query.with_entities(Transaction.tx_hash).all()
    # print(result)

    # addresses_result = Address.get_coin_address_by_coin_name('Ethereum')
    # print(addresses_result)
    # print(addresses_result)

    # sync = SyncConfig.get_sync_info('Ethereum')
    # sync.update({'synced_height': 100, 'highest_height': 100})
    #
    # print(sync)

    # ***************** 全部
    # block = Block.query.all()
    # print(block)

    # *************** 交易
    # height = 1
    # session = db.session()
    # session.begin(subtransactions=True)
    # block = Block(height=height, block_hash='0x{}'.format(height), block_time=datetime.datetime.now())
    # print('block:', block)
    # block_ss = session.add(block)
    # session.commit()
    # tx = Transaction(block_id=block.id, coin_id=1, tx_hash='tx_hash' + block.block_hash, height=block.height,
    #                  block_time=111, amount='111',
    #                  sender='sender', receiver='receiver', gas='111', gas_price='111', fee='0', contract='111',
    #                  status=1,
    #                  type=1)
    # session.add(tx)
    # print('block ss', block_ss)
    # session.commit()
    #
    # print(block)
    # print(tx)
