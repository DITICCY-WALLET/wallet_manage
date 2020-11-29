from httplibs.response import ResponseObject
from models.models import ProjectCoin
from log import logger
from code_status import *


def set_address(project_id, coin_id, attr, address):
    attrs = ("hot_address", "collect_address", "fee_address")
    if attr not in attrs:
        return ResponseObject.error(**address_set_error, data=False)
    project_coin = ProjectCoin.query.filter_by(project_id=project_id, coin_id=coin_id).first()
    if project_coin is None:
        return ResponseObject.error(**data_not_found)
    # 动态设置
    setattr(project_coin, attr, address)
    try:
        project_coin.save()
    except Exception as e:
        logger.error("[SET ADDRESS] - 设置钱包地址保存数据库失败: ", project_coin.id, attr,
                     project_coin.hot_address, e)
        return ResponseObject.error(**address_set_error, data=False)
    msg = "修改成功"
    is_success = True
    return ResponseObject.success(data=is_success, msg=msg)



