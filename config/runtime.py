from config.config import CONFIG

"""
此处结构为：
{
    project_id: {
        coin_name: {
            'secret': secret,
            'crypto': rsa_crypto_obj
        }
    }
}
"""
rsa_secret = {}

# 暂时以此解决上下文问题
app = None

"""
此处结构为：
{
    address: {
        "project_id": project_id,
        "coin_id": coin_id,
        "coin_name": coin_name
    }
}
"""
project_address = {}

"""
此处结构为：
{
    coin_name or contract:{
        "coin_id": coin_id
        "coin_name": coin_name,
        "contract": contract,
        "decimal": decimal,
        "symbol": symbol
    }
}
"""
coins = {}

"""
此处结构为：
{
    project_id: {
        "name": name,
        "url": callback_url,
        "access_key": access_key,
        "secret_key": secret_key,
    }
}
"""
project = {}

