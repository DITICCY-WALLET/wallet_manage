import os
import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

CONFIG = None
default = 'prod'
base_path = os.path.dirname(__file__)


def read_yaml(yaml_fn=os.path.join(base_path, "config.yml")):
    with open(yaml_fn, 'r', encoding='utf8') as cfg_f:
        data = yaml.load(cfg_f, Loader=Loader)
    if not isinstance(data, dict):
        raise ValueError("配置文件错误")
    active = data.get('active', default)
    active_cfg_file = os.path.join(base_path, 'config-{}.yml'.format(active))
    if os.path.isfile(active_cfg_file):
        with open(active_cfg_file, encoding="utf8") as active_cfg_f:
            active_data = yaml.load(active_cfg_f, Loader=Loader)
        if isinstance(active_data, dict):
            data.update(active_data)
        else:
            print('{} 文件加载失败, 结果为： {}, 不使用该部分配置, 程序继续执行'.format(active_cfg_file, active_data))
    return data


if CONFIG is None:
    CONFIG = read_yaml()

if CONFIG.get('ENV'):
    os.environ.update(CONFIG['ENV'])


class Config(object):
    def __init__(self, config: dict):
        for k, v in config.items():
            setattr(self, k, v)


config = Config(CONFIG)

if __name__ == '__main__':
    print(CONFIG)
    print(dir(config))
    import logging
    from logging.config import dictConfig
    dictConfig(config.LOG_CONF)
    logger = logging.getLogger('flask')
    logger.info('11111')

