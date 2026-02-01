# data_path.py
import os
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SSH配置
SSH_CONFIG = {
    'default_username': 'ifly',
    'default_password': 'auto',
    'default_port': 22,
    # 连接相关的通用超时配置
    'timeout': 10,
    'auth_timeout': 15,
    'banner_timeout': 15
}

# 文件路径配置
FILE_PATHS = {
    # 车机环境默认目录（planning_exec）
    'default_working_directory': '/opt/usr/app/1/gea/runtime_service/planning_exec/res/conf',
    # ADAS参数文件固定目录
    'adas_working_directory': '/opt/usr/app/1/gea/runtime_service/planning_exec/res/conf',
    'params_file': 'params.json',  # 保持为 params.json
    'adas_params_file': 'adas_params.json',
    'config_file': 'config.json',
    'icon_file': 'ico/yumi.ico'
}

# A/B面配置
SIDE_CONFIG = {
    'a_side_username': 'root',
    'b_side_username': 'root',
    'a_side_password': 'Huawei12#$',
    'b_side_password': 'Huawei12#$'
}

# 挂载配置
MOUNT_CONFIG = {
    # 车机环境使用的挂载命令
    'mount_command': 'mount -o remount,rw /opt/usr/app/1/gea'
}


def get_full_file_path(working_directory):
    """获取完整文件路径 - 修复路径拼接问题"""
    try:
        # 确保路径正确拼接
        if working_directory.endswith('/'):
            full_path = working_directory + FILE_PATHS['params_file']
        else:
            full_path = working_directory + '/' + FILE_PATHS['params_file']

        logger.info(f"构建文件路径: {full_path}")
        return full_path

    except Exception as e:
        logger.error(f"构建文件路径失败: {e}")
        # 回退到默认拼接方式
        return os.path.join(working_directory, FILE_PATHS['params_file'])


def get_full_adas_file_path(working_directory=None):
    """获取ADAS参数文件完整路径 - 使用固定配置路径"""
    try:
        # 使用配置中的固定路径，不依赖working_directory参数
        adas_dir = FILE_PATHS['adas_working_directory']
        if adas_dir.endswith('/'):
            full_path = adas_dir + FILE_PATHS['adas_params_file']
        else:
            full_path = adas_dir + '/' + FILE_PATHS['adas_params_file']

        logger.info(f"构建ADAS文件路径: {full_path}")
        return full_path
    except Exception as e:
        logger.error(f"构建ADAS文件路径失败: {e}")
        # 回退到默认拼接方式
        adas_dir = FILE_PATHS.get('adas_working_directory', '/opt/usr/app/1/gea/runtime_service/planning_exec/res/conf')
        return os.path.join(adas_dir, FILE_PATHS['adas_params_file'])


def get_config_path():
    """获取配置文件路径 - 兼容exe打包环境"""
    try:
        import sys
        # 判断是否为打包环境
        if getattr(sys, 'frozen', False):
            # exe运行环境：使用exe所在目录
            base_dir = os.path.dirname(sys.executable)
        else:
            # 脚本运行环境：使用脚本所在目录
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        config_path = os.path.join(base_dir, FILE_PATHS['config_file'])
        logger.info(f"定位配置文件路径: {config_path}")
        return config_path
        
    except Exception as e:
        logger.error(f"获取配置文件路径异常: {e}")
        return FILE_PATHS['config_file']


def get_icon_path():
    """获取图标文件路径"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, FILE_PATHS['icon_file'])
        if os.path.exists(icon_path):
            logger.info(f"找到图标文件: {icon_path}")
            return icon_path
        else:
            logger.warning(f"图标文件不存在: {icon_path}")
            return None
    except Exception as e:
        logger.error(f"获取图标路径失败: {e}")
        return None


def create_default_config():
    """创建默认配置文件"""
    try:
        config_path = get_config_path()
        default_config = {
            "示例车型直连": {
                "connection_type": "direct",  # 直连车机
                "a_side": "192.168.1.6",
                "b_side": "192.168.1.70",
                "a_side_username": "root",
                "b_side_username": "root",
                "a_side_password": "Huawei12#$",
                "b_side_password": "Huawei12#$",
                "working_directory": FILE_PATHS['default_working_directory'],
                "port": 22
            }
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)

        logger.info(f"默认配置文件已创建: {config_path}")
        return True

    except Exception as e:
        logger.error(f"创建默认配置文件失败: {e}")
        return False