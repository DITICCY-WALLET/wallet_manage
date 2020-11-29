"""
db 表
"""
from datetime import datetime

from coin.driver.driver_base import DriverFactory
from dt import now
from enumer.coin_enum import SendEnum
from flask_sqlalchemy import orm
from httplibs.coinrpc.rpcbase import RpcBase
from sqlalchemy import UniqueConstraint

from exts import db
from enumer.routine import DBStatusEnum


class ApiAuth(db.Model):
    """
    API 权限认证表
    """
    __tablename__ = 'api_auth'
    __table_args__ = (
        # 确保一个项目方只能有一个 key
        UniqueConstraint(
            'access_key',
            'project_id',
            name='uk_access_key_project_id'),
        {'mysql_engine': "INNODB"}
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    access_key = db.Column(db.VARCHAR(128), nullable=False, comment="key", unique=True)
    secret_key = db.Column(db.VARCHAR(128), comment="secret")
    ip = db.Column(db.VARCHAR(128), comment='受限IP地址')
    status = db.Column(db.SmallInteger, default=1, comment='是否启用 1：启用 0：禁用')
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间",
                            default=datetime.now, onupdate=datetime.now)

    def __str__(self):
        return ' -'.join(
            [str(self.id), str(self.access_key), str(self.secret_key),
             str(self.create_time), str(self.update_time)])


class Block(db.Model):
    """区块表"""
    __tablename__ = 'block'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    height = db.Column(db.Integer, nullable=False, comment="块高度", unique=True)
    block_hash = db.Column(db.VARCHAR(128), nullable=False, comment="块hash", unique=True)
    block_time = db.Column(db.DateTime, nullable=False, comment="块时间")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)

    def __str__(self):
        return "{id}-{height}-{block_hash}".format(
            id=self.id, height=self.height, block_hash=self.block_hash)


class Coin(db.Model):
    """
    币种表
    """
    __tablename__ = 'coin'
    __table_args__ = (
        UniqueConstraint(
            'master_id', 'contract', name='uk_master_id_contract'), {
            'mysql_engine': "INNODB"})

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    master_id = db.Column(db.Integer, unique=False, default=0, comment="主链ID")
    name = db.Column(db.String(64), unique=True, comment='币种名称')
    symbol = db.Column(db.String(64), comment='缩写')
    decimal = db.Column(db.SmallInteger, nullable=False, default=0, comment='小数位')
    supply = db.Column(db.BigInteger, comment='发行量')
    is_master = db.Column(db.SmallInteger, default=1, comment='是否主链币 1 是 0 否')
    bip44 = db.Column(db.Integer, default=1, comment='bip44 编码')
    is_support_token = db.Column(db.SmallInteger, nullable=True, default=0,
                                 comment='是否支持代币 1)是 2)否')
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

    transaction = orm.relationship('Transaction',
                                   primaryjoin="Transaction.coin_id==Coin.id",
                                   foreign_keys="Coin.id",
                                   backref="Coin")

    # coin = orm.relationship('Coin',
    #                         primaryjoin="Coin.master_id==Coin.id",
    #                         foreign_keys="Coin.id",
    #                         backref="Coin")

    @staticmethod
    def get_all_coin():
        session = db.session()
        coin_list_sql = r"""
        SELECT c1.id, c1.name as coinName, c1.symbol, c1.is_master as isMaster,
        c1.is_support_ooken, c1.contract, c1.supply, IFNULL(c2.name, c1.name) as masterName,
        c1.decimal from coin as c1 left join coin as c2 on c1.master_id = c2.id;
        """
        coin_list = session.execute(coin_list_sql)
        if coin_list.rowcount <= 0:
            return []
        result = []
        for coin in coin_list:
            result.append({coin_list.cursor.description[k][0]: v for k, v in enumerate(coin)})
        return result

    def __str__(self):
        return "{id}-{master_id}-{name}-{symbol}-{is_contract}".format(
            id=self.id, master_id=self.master_id, name=self.name, symbol=self.symbol,
            is_contract=self.is_contract and True or False)

    @staticmethod
    def get_coin_lj_contract(name, contract):
        session = db.session()
        coin_left_join_contract_sql = r"""
        SELECT c1.id, c1.name as coinName, c2.name, c2.contract from
        coin as c1 left join coin as c2 on c1.master_id = c2.id where c2.name = '{}' 
        and c1.contract = '{}' limit 1
        """.format(name, contract)
        coin = session.execute(coin_left_join_contract_sql)
        return coin

    @staticmethod
    def get_coin_lj_contract_by_id(coin_id, contract):
        session = db.session()
        coin_left_join_contract_sql = r"""
            SELECT c1.id, c1.name as coinName, c2.name, c2.contract from
            coin as c1 left join coin as c2 on c1.master_id = c2.id where c1.id = '{}' 
            and c2.contract = '{}' limit 1
            """.format(coin_id, contract)
        coin = session.execute(coin_left_join_contract_sql)
        return coin

    @staticmethod
    def get_coin(contract=None, symbol=None, name=None, is_master=1, coin_id=None):
        """从数据库中获取某个币种"""
        params = {'is_master': is_master}
        if contract is not None:
            params['contract'] = contract
            params['is_master'] = 0
        if symbol is not None:
            params['symbol'] = symbol
        if name is not None:
            params['name'] = name
        if coin_id is not None:
            params['coin_id'] = coin_id
        coin = Coin.query.filter_by(**params).first()
        if not coin:
            return None
        return coin

    @staticmethod
    def get_coin_by_symbol(contract=None, symbol=None, name=None, is_master=1):
        """根据 symbol 获取币种"""
        params = {'is_master': is_master}
        if contract is not None:
            params['contract'] = contract
            params['is_master'] = 0
        if symbol is not None:
            params['symbol'] = symbol
        if name is not None and symbol is None:
            params['name'] = name
        coin = Coin.query.filter_by(**params).first()
        if not coin:
            return None
        return coin

    @staticmethod
    def get_erc20_usdt_coin():
        """获取 ETH 的 ERC20 USDT"""
        coin = Coin.get_coin_by_symbol(symbol='USDT', is_master=0)
        if not coin:
            return None
        return coin

    @staticmethod
    def add_coin(commit=True, **kwargs):
        """
        添加币种
        :param commit: 是否自动提交
        :param kwargs: Coin 字段
        :return:
        """
        coin = Coin(**kwargs)
        session = db.session()
        saved = session.add(coin)
        if commit:
            session.commit()
            return saved
        return session


class Address(db.Model):
    """地址表"""
    __tablename__ = 'address'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coin_id = db.Column(db.Integer, nullable=False, comment="币种ID", index=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目方 ID")
    address = db.Column(
        db.VARCHAR(128),
        unique=True,
        nullable=False,
        comment="地址")
    address_type = db.Column(db.SmallInteger, default=0, comment="地址类型，0充 1提")
    is_send = db.Column(
        db.SmallInteger,
        default=0,
        index=True,
        comment="是否已给予，0否 1是")
    status = db.Column(db.SmallInteger, default=1, comment="是否有效，0否 1是 2)移除")
    create_time = db.Column(
        db.DateTime,
        nullable=False,
        comment="生成时间",
        default=datetime.now)

    coin = orm.relationship('Coin',
                            primaryjoin="Address.coin_id==Coin.id",
                            foreign_keys="Address.coin_id",
                            backref="Address")

    transaction = orm.relationship(
        'Transaction',
        primaryjoin="Address.address==Transaction.receiver",
        foreign_keys="Address.address",
        backref="Address")

    project = orm.relationship('Project',
                               primaryjoin="Address.project_id==Project.id",
                               foreign_keys="Address.project_id",
                               backref="Address")

    def __str__(self):
        return "{id}-{coin_id}-{project_id}-{address}".format(
            id=self.id, coin_id=self.coin_id, project_id=self.project_id, address=self.address)

    @staticmethod
    def add_address(project_id, coin_id, address, address_type=0, is_send=0, *, commit=True):
        """添加地址"""
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
        try:
            for address_dict in addresses:
                address = Address(**address_dict)
                session.add(address)
            if commit:
                session.commit()
                return None
            return session
        except Exception:
            session.rollback()
            return None

    @staticmethod
    def get_coin_address_by_coin_name(coin_name):
        """
        这种方式返回的格式固定为 list<tuple<row>>
        row 取决于 with_entities 里面的字段
        :return address, project_id, coin_id, coin_name
        """
        session = db.session()
        addresses = session.query(Address, Coin).join(
            Address, Address.coin_id == Coin.id).with_entities(
            Address.address, Address.project_id, Address.coin_id, Coin.name
        ).filter(Coin.name == coin_name).all()
        return addresses

    @staticmethod
    def get_address_by_pca(project_id, coin_id, address):
        """根据 Project 与 Coin 和 Address 获取行"""
        session = db.session()
        address = session.query(Address).filter(project_id == project_id,
                                                coin_id == coin_id,
                                                address == address).one()
        return address


class Transaction(db.Model):
    """
    交易表
    """
    __tablename__ = 'tx'
    __table_args__ = (
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
    fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真手续费金额")
    contract = db.Column(db.VARCHAR(128), comment="代币名称或地址")
    status = db.Column(db.SmallInteger, nullable=False, comment="交易是否有效 1）有效 0）无效 2) 未知")
    type = db.Column(db.SmallInteger, nullable=False, comment="交易类型")
    is_send = db.Column(db.SmallInteger, nullable=False, comment="是否推送 0:未推 1:已推 2:不用推")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间",
                            default=datetime.now, onupdate=datetime.now)

    coin = orm.relationship('Coin',
                            primaryjoin="Transaction.coin_id==Coin.id",
                            foreign_keys="Transaction.coin_id",
                            backref="Transaction")

    def __str__(self):
        return "{id}-{tx_hash}-{height}-{status}".format(
            id=self.id, tx_hash=self.tx_hash, height=self.height, status=self.status)

    @classmethod
    def get_tx_coin_tx(cls, **params):
        """获取"""
        session = db.session()
        block_tx = session.query(
            Transaction,
            Coin).join(
            Transaction,
            Transaction.coin_id == Coin.id).filter(
            **params)
        return block_tx

    @classmethod
    def get_tx_coin_by_tx_hash(cls, tx_hash):
        """
        根据tx hash 获取获取交易tx 及 币种信息
        :param tx_hash:
        :return:
        """
        session = db.session()
        txs = session.query(
            Transaction,
            Coin).join(
            Transaction,
            Transaction.coin_id == Coin.id).filter(
            Transaction.tx_hash == tx_hash)
        return txs.first()

    @classmethod
    def add_transaction(cls, coin_id, tx_hash, block_time, sender, receiver, amount, status,
                        tx_type, block_id, height, gas=0, gas_price=0, fee=0,
                        contract=None, *, commit=True):
        """添加交易"""
        session = db.session()

        trx = Transaction(coin_id=coin_id, tx_hash=tx_hash, block_time=block_time,
                          sender=sender, receiver=receiver, amount=amount,
                          status=status, type=tx_type, gas=gas, gas_price=gas_price,
                          fee=fee, contract=contract, block_id=block_id,
                          height=height, is_send=SendEnum.NEEDLESS.value)
        # saved 如果成功情况下是 None
        saved = session.add(trx)
        if commit:
            # 自动提交
            session.commit()
            return saved
        # 返回 session 等待自行处理
        return session

    @classmethod
    def add_transaction_or_update(cls, coin_id, tx_hash, block_time, sender, receiver, amount,
                                  status, tx_type, block_id, height, gas=0, gas_price=0, fee=0,
                                  contract=None, is_send=0, *, commit=True, session=None):
        """添加交易或更新交易"""
        session = session or db.session()

        sql = (
            "insert into {table_name} (coin_id, tx_hash, block_time, sender, receiver, amount, "
            "status, type, gas, gas_price, fee, contract, block_id, height, is_send, "
            "create_time, update_time) "
            "values "
            "({coin_id}, '{tx_hash}', {block_time}, '{sender}', '{receiver}', {amount}, {status}, "
            "{type}, {gas}, {gas_price}, {fee}, {contract}, {block_id}, {height}, {is_send}, "
            "'{create_time}', '{update_time}')"
            "ON DUPLICATE KEY UPDATE block_time=values(block_time), gas=values(gas), "
            "gas_price=values(gas_price), "
            "fee=values(fee), block_id=values(block_id), height=values(height)").format(
            table_name=cls.__tablename__,
            coin_id=coin_id,
            tx_hash=tx_hash,
            block_time=block_time,
            sender=sender,
            receiver=receiver,
            amount=amount,
            status=status,
            type=tx_type,
            gas=gas,
            gas_price=gas_price,
            fee=fee,
            contract="'{}'".format(contract) if contract is not None else 'null',
            block_id=block_id,
            height=height,
            is_send=is_send,
            create_time=now(),
            update_time=now())

        # saved 如果成功情况下是 None
        saved = session.execute(sql)
        if commit:
            # 自动提交
            session.commit()
            return saved
        # 返回 session 等待自行处理
        return session


class RpcConfig(db.Model):
    """
    RPC 节点配置表
    """
    __tablename__ = 'rpc_config'
    __table_args__ = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coin_id = db.Column(db.Integer, unique=False, default=0, comment="主链ID")
    name = db.Column(db.VARCHAR(32), comment="配置币种名称")
    driver = db.Column(db.VARCHAR(64), comment="驱动类型. 当前仅使用 ETHEREUM")
    host = db.Column(db.VARCHAR(256),
                     comment="节点地址, 示例http[s]://[user]:[passwd]@[ip|domain]:[port]")
    status = db.Column(db.SmallInteger, default=1, comment="是否有效，0否 1是")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False,
                            comment="更新时间", default=datetime.now, onupdate=datetime.now)

    def __str__(self):
        return "{id}-{coin_id}-{name}-{driver}-{host}".format(
            id=self.id, coin_id=self.coin_id, name=self.name, driver=self.driver, host=self.host)

    @staticmethod
    def get_rpc_by_coin(coin_id):
        rpc_config = RpcConfig.query.filter_by(coin_id=coin_id).first()
        if not rpc_config:
            return None
        driver = rpc_config.driver
        rpc = DriverFactory(driver, driver.host)
        return rpc

    @staticmethod
    def get_rpc() -> (RpcBase, None):
        """获取rpc, 返回RPC对象"""
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
    callback_url = db.Column(db.VARCHAR(256),
                             comment="回调地址, 示例http[s]://[user]:[passwd]@[ip|domain]:[port]")
    access_key = db.Column(db.VARCHAR(128), comment="回调签名 access_key")
    secret_key = db.Column(db.VARCHAR(128), comment="回调签名 secret_key")
    hot_pb = db.Column(db.TEXT, comment="加密公钥, 给到项目方, 特殊事件使用.")
    hot_pk = db.Column(db.TEXT, comment="加密私钥, 解密 PB.")
    create_time = db.Column(db.DateTime, nullable=False,
                            comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False,
                            comment="更新时间", default=datetime.now, onupdate=datetime.now)

    project_coin = orm.relationship('ProjectCoin',
                                    primaryjoin="Project.id==ProjectCoin.project_id",
                                    foreign_keys="Project.id",
                                    backref="Project")

    def __str__(self):
        return "{id}-{name}-{access_key}-{callback_url}".format(
            id=self.id, name=self.name, access_key=self.access_key, callback_url=self.callback_url)

    @staticmethod
    def get_project_coin_by_id(project_id):
        """
        获得项目方的完整资料
        :param project_id: 项目方 ID
        :return:
        """
        session = db.session()
        project_infos = session.query(
            Project, ProjectCoin, Coin).join(
            ProjectCoin,
            ProjectCoin.project_id == Project.id).join(
            Coin,
            ProjectCoin.coin_id == Coin.id).filter(
            Project.id == project_id)
        return project_infos

    @staticmethod
    def get_project_by_id(project_id):
        session = db.session()


class ProjectCoin(db.Model):
    """项目方支持的币种"""
    __tablename__ = 'project_coin'
    __table_args__ = (
        UniqueConstraint(
            'project_id', 'coin_id', name='uk_project_id_coin_id'), {
            'mysql_engine': "INNODB"})

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    coin_id = db.Column(db.Integer, nullable=False, comment="主链币 ID")
    hot_address = db.Column(db.VARCHAR(128), nullable=False, comment="热钱包地址")
    hot_secret = db.Column(db.VARCHAR(128), nullable=False, comment="热钱包密钥, 保留字段, 未使用")
    gas = db.Column(db.VARCHAR(64), nullable=False, default='150000',
                    comment="gas, 默认150000, 0为自动处理")
    gas_price = db.Column(db.VARCHAR(64), nullable=False, default=str(20 * 1000 * 1000 * 1000),
                          comment="gasPrice, 默认20G, 0为自动处理")
    fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真实手续费")
    collect_address = db.Column(db.VARCHAR(128), default=None, comment="冷钱包地址")
    fee_address = db.Column(db.VARCHAR(128), default=None, comment="手续费钱包地址")
    is_deposit = db.Column(db.SmallInteger, nullable=False, default=DBStatusEnum.YES.value,
                           comment="是否充值 0:否 1:是")
    is_withdraw = db.Column(db.SmallInteger, nullable=False, default=DBStatusEnum.YES.value,
                            comment="是否提现 0:否 1:是")
    is_collect = db.Column(db.SmallInteger, nullable=False, default=DBStatusEnum.YES.value,
                           comment="是否归集 0:否 1:是")
    last_collection_time = db.Column(db.DateTime, default=None,
                                     comment="最后归集时间", onupdate=datetime.now)
    create_time = db.Column(db.DateTime, nullable=False,
                            comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False,
                            comment="更新时间", default=datetime.now, onupdate=datetime.now)

    project = orm.relationship('Project',
                               primaryjoin="ProjectCoin.project_id==Project.id",
                               foreign_keys="ProjectCoin.project_id",
                               backref="ProjectCoin")

    coin = orm.relationship('Coin',
                            primaryjoin="ProjectCoin.project_id==Coin.id",
                            foreign_keys="ProjectCoin.project_id",
                            backref="ProjectCoin")

    def __str__(self):
        return "{id}-{project_id}".format(id=self.id, project_id=self.project_id)

    @staticmethod
    def get_pro_coin_by_pid_cname(project_id, coin_name):
        """根据币种名称及项目方ID 获取项目方支持币种"""
        session = db.session()
        project_coin = session.query(
            ProjectCoin,
            Coin).join(
            Coin,
            ProjectCoin.coin_id == Coin.id).filter(
            ProjectCoin.project_id == project_id,
            Coin.name == coin_name)
        return project_coin.first()

    @staticmethod
    def get_pc_project_by_pid_cid(project_id, coin_id):
        """根据币种名称及项目方ID 获取项目方支持币种"""
        session = db.session()
        project_coin = session.query(
            Project,
            ProjectCoin,
            ).join(
            Project,
            ProjectCoin.project_id == Project.id).filter(
            ProjectCoin.project_id == project_id,
            ProjectCoin.coin_id == coin_id)
        return project_coin.first()

    @staticmethod
    def get_pc_by_pid_cid(project_id, coin_id):
        """根据PID 与 CID 查询单个币种"""
        session = db.session()
        project_coin = session.query(
            ProjectCoin).filter(
            ProjectCoin.id == project_id, ProjectCoin.coin_id == coin_id).one()
        return project_coin.first()

    # @staticmethod
    # def get_pro


class ProjectOrder(db.Model):
    """项目方订单"""
    __tablename__ = 'project_order'
    __table_args = (
        {'mysql_engine': "INNODB"}
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    project_id = db.Column(db.Integer, nullable=False, comment="项目 ID")
    action_id = db.Column(db.VARCHAR(128), nullable=False,
                          unique=True, comment="执行ID, 唯一编码, 控制幂等")
    coin_id = db.Column(db.Integer, nullable=False, comment="币种表关联键", index=True)
    tx_hash = db.Column(db.VARCHAR(128), nullable=False, comment="交易hash", unique=True)
    amount = db.Column(db.VARCHAR(64), nullable=False, comment="交易金额")
    sender = db.Column(db.VARCHAR(128), nullable=False, comment="发送人")
    receiver = db.Column(db.VARCHAR(128), nullable=False, comment="接收人")
    gas = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额,ETH使用")
    gas_price = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额,ETH使用")
    fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真实使用手续费")
    contract = db.Column(db.VARCHAR(128), comment="代币名称或地址")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间",
                            default=datetime.now, onupdate=datetime.now)

    def __str__(self):
        return "{id}-{project_id}-{tx_hash}".format(
            id=self.id, project_id=self.project_id, tx_hash=self.tx_hash)

    @classmethod
    def get_tx_by_action_or_hash(cls, action_id=None, tx_hash=None):
        """根据action id 或 tx_hash 获取交易"""
        params = {}
        if action_id:
            params['action_id'] = action_id
        if tx_hash:
            params['tx_hash'] = tx_hash

        trx = ProjectOrder.query.filter_by(**params).first()
        return trx

    @classmethod
    def add(cls, project_id, action_id, coin_id, tx_hash, amount,
            sender, receiver, gas=0, gas_price=0, fee=0, contract=None):
        """添加项目方发送交易"""
        session = db.session()
        trx = ProjectOrder(
            project_id=project_id,
            action_id=action_id,
            coin_id=coin_id,
            tx_hash=tx_hash,
            amount=amount,
            sender=sender,
            receiver=receiver,
            gas=gas,
            gas_price=gas_price,
            fee=fee,
            contract=contract)
        tx_saved = session.add(trx)
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
    is_send = db.Column(db.SmallInteger, nullable=False, comment="是否推送 0:未推 1:已推 2:不用推")
    # tx_hash = db.Column(db.VARCHAR(128), nullable=False, comment="交易hash", unique=True)
    # amount = db.Column(db.VARCHAR(64), nullable=False, comment="交易金额")
    # sender = db.Column(db.VARCHAR(128), nullable=False, comment="发送人")
    # receiver = db.Column(db.VARCHAR(128), nullable=False, comment="接收人")
    # gas = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额， ETH使用")
    # gas_price = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="手续费金额, ETH使用")
    # fee = db.Column(db.VARCHAR(64), nullable=False, default=0, comment="真实手续费")
    # contract = db.Column(db.VARCHAR(128), comment="代币名称或地址")
    create_time = db.Column(db.DateTime, nullable=False, comment="创建时间", default=datetime.now)
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间",
                            default=datetime.now, onupdate=datetime.now)

    def __str__(self):
        return "{id}-{project_id}-{is_send}".format(
            id=self.id, project_id=self.project_id, is_send=self.is_send)


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
    update_time = db.Column(db.DateTime, nullable=False, comment="更新时间",
                            default=datetime.now, onupdate=datetime.now)

    coin = orm.relationship('Coin',
                            primaryjoin="SyncConfig.coin_id==Coin.id",
                            foreign_keys="SyncConfig.coin_id",
                            backref="SyncConfig")

    def __str__(self):
        return "{id}-{coin_id}-{synced_height}-{highest_height}".format(
            id=self.id, coin_id=self.coin_id, synced_height=self.synced_height,
            highest_height=self.highest_height)

    @staticmethod
    def get_sync_info(coin_name):
        """获取同步信息"""
        session = db.session()
        coin_sync = session.query(
            SyncConfig,
            Coin).join(
            SyncConfig,
            SyncConfig.coin_id == Coin.id).filter(
            Coin.name == coin_name).first()
        return coin_sync


if __name__ == '__main__':
    pass
    # from flask import Flask

    # from config.config import config

    # app = Flask(__name__)
    # app.config.from_object(config)
    #
    # db.init_app(app)
    # app.app_context().push()
    #
    # db.create_all()
    #
    # result = Transaction.add_transaction(1, 'tx_hash3', 123211, 'sender',
    #                                      'receiver', 100, 1, 1, 3, 3)
    # print(result)
    # session = db.session()
    #
    # result = Transaction.query.with_entities(Transaction.tx_hash).all()
    # print(result)
    #
    # addresses_result = Address.get_coin_address_by_coin_name('Ethereum')
    # print(addresses_result)
    # print(addresses_result)
    #
    # sync = SyncConfig.get_sync_info('Ethereum')
    # sync.update({'synced_height': 100, 'highest_height': 100})
    #
    # print(sync)
    #
    # # ***************** 全部
    # block = Block.query.all()
    # print(block)
    #
    # # *************** 交易
    # height = 1
    # session = db.session()
    # session.begin(subtransactions=True)
    # block = Block(height=height, block_hash='0x{}'.format(height),
    #               block_time=datetime.now())
    # print('block:', block)
    # block_ss = session.add(block)
    # session.commit()
    # tx = Transaction(block_id=block.id, coin_id=1, tx_hash='tx_hash' + block.block_hash,
    #                  height=block.height, block_time=111, amount='111',
    #                  sender='sender', receiver='receiver', gas='111', gas_price='111',
    #                  fee='0', contract='111', status=1, type=1)
    # session.add(tx)
    # print('block ss', block_ss)
    # session.commit()
    #
    # print(block)
    # print(tx)
