from flask import Flask
from exts import db
from config.config import config
from key.generate_key import generate_rsa_key, generate_ack
from models.models import *
app = Flask(__name__)
app.config.from_object(config)

db.init_app(app)
app.app_context().push()

db.create_all()

session = db.session()

sign_key = generate_ack()
rsa_key = generate_rsa_key()

# session.begin(subtransactions=True)
# 币种相关
# 添加 ETH
eth_coin = Coin()
eth_coin.id = 1
eth_coin.name = "Ethereum"
eth_coin.symbol = "ETH"
eth_coin.decimal = 18
eth_coin.supply = 20000000
eth_coin.is_master = 1
eth_coin.bip44 = 100
session.add(eth_coin)

# 添加 USDT
usdt_coin = Coin()
usdt_coin.id = 2
usdt_coin.master_id = 1
usdt_coin.name = "Tether USD"
usdt_coin.symbol = "USDT"
usdt_coin.decimal = 6
usdt_coin.supply = 20000000
usdt_coin.is_master = 0
usdt_coin.bip44 = 100
usdt_coin.contract = "0xbed2d19d9551f6666c31ce2a72eb4533262d5dab"
session.add(usdt_coin)


# 项目相关
# 添加项目
project = Project()
project.id = 1
project.name = "Lucky"
project.callback_url = "http://www.bcfssdlfjsdd.com/upayret/payret"
project.access_key = sign_key['access_key']
project.secret_key = sign_key['secret_key']
session.add(project)

# 添加项目支持币种
# 只按主链算, 只要主链支持, 就都算支持了
pc = ProjectCoin()
pc.id = 1
pc.project_id = project.id
pc.coin_id = eth_coin.id
pc.hot_address = "0xaeb184f8872191d9995c713d7e424a68fdb4e5b1"
pc.hot_secret = "保留.."
pc.hot_pb = rsa_key['public_key']
pc.hot_pk = rsa_key['private_key']
pc.cold_address = "待更新"
pc.fee_address = "0x69ebf7a64a8ce92d07afe7ba810933dce18e75dd"

session.add(pc)

# RPC
## RPC
rpc = RpcConfig()
rpc.id = 1
rpc.coin_id = 1
rpc.name = "Ethereum"
rpc.driver = "Ethereum"
rpc.host = "http://127.0.0.1:8545"
rpc.status = 1

session.add(rpc)

# SYNC
sync = SyncConfig()
sync.id = 1
sync.coin_id = 1
sync.synced_height = 1
sync.highest_height = 1

session.add(sync)
session.commit()





