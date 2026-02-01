import os
import sys
import subprocess
import shutil
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_exe():
    """编译为EXE文件"""
    try:
        # 检查PyInstaller是否安装
        try:
            import PyInstaller
            logger.info("PyInstaller 已安装")
        except ImportError:
            logger.info("正在安装PyInstaller...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

        # 清理旧的构建目录
        for dir_name in ["build", "dist"]:
            if os.path.exists(dir_name):
                logger.info(f"正在清理 {dir_name} 目录...")
                shutil.rmtree(dir_name)
                
        # 创建构建目录
        if not os.path.exists("build"):
            os.makedirs("build")

        # 检查图标文件是否存在
        icon_path = "ico/yumi.ico"
        if not os.path.exists(icon_path):
            logger.warning(f"图标文件 {icon_path} 不存在，将使用默认图标")
            icon_path = None

        # 检查其他必要文件是否存在
        required_files = ["main.py", "config.json", "data_path.py", "ssh_manager.py", "file_editor.py", "ui.py",
                          "side_selector.py"]
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)

        if missing_files:
            logger.warning(f"以下必要文件缺失: {missing_files}")

        # PyInstaller命令 - 移除了--windowed参数来保留控制台窗口
        cmd = [
            "pyinstaller",
            "--onefile",
            # 移除了 --windowed 参数以保留控制台窗口
            "--name=标定可视化工具",
            "--add-data=config.json;.",
            "--add-data=data_path.py;.",
            "--add-data=ssh_manager.py;.",
            "--add-data=file_editor.py;.",
            "--add-data=ui.py;.",
            "--add-data=side_selector.py;.",
            "--hidden-import=paramiko",
            "--hidden-import=tkinter",
            "--hidden-import=json",
            "--hidden-import=logging",
            "--hidden-import=re",
            "--hidden-import=time",
            "--hidden-import=base64",
            "--hidden-import=hashlib",
        ]

        # 添加图标参数（如果图标存在）
        if icon_path and os.path.exists(icon_path):
            cmd.append(f"--icon={icon_path}")
            cmd.append(f"--add-data={icon_path};ico")
            logger.info(f"使用图标: {icon_path}")
        else:
            logger.info("使用默认图标")

        # 添加其他必要文件
        for file in required_files:
            if file.endswith(".py") and file != "main.py":
                cmd.append(f"--add-data={file};.")

        cmd.append("main.py")

        logger.info("开始编译...")
        logger.info(f"命令: {' '.join(cmd)}")

        # 执行编译命令
        subprocess.check_call(cmd)

        # 复制必要的文件到dist目录
        dist_dir = "dist"
        if os.path.exists(dist_dir):
            # 仅复制配置文件，不复制源代码
            files_to_copy = ["config.json"]
            for file in files_to_copy:
                if os.path.exists(file):
                    shutil.copy2(file, os.path.join(dist_dir, file))
                    logger.info(f"已复制 {file}")
                else:
                    logger.warning(f"文件不存在，无法复制: {file}")

            # 复制图标文件夹
            if os.path.exists("ico"):
                ico_dist_path = os.path.join(dist_dir, "ico")
                if not os.path.exists(ico_dist_path):
                    os.makedirs(ico_dist_path)
                for file in os.listdir("ico"):
                    if file.endswith(".ico"):
                        shutil.copy2(os.path.join("ico", file), ico_dist_path)
                        logger.info(f"已复制图标: {file}")

            # 创建默认配置文件（如果不存在）
            config_dist_path = os.path.join(dist_dir, "config.json")
            if not os.path.exists(config_dist_path):
                logger.warning("配置文件不存在，创建默认配置")
                from data_path import create_default_config
                if create_default_config():
                    shutil.copy2("config.json", config_dist_path)

            logger.info(f"\n编译完成！")
            logger.info(f"EXE文件位置: {os.path.abspath(os.path.join(dist_dir, '标定可视化工具.exe'))}")
            logger.info("\n使用说明:")
            logger.info("1. 运行 '标定可视化工具.exe'")
            logger.info("2. 程序将显示控制台窗口用于调试信息")
            logger.info("3. 可以修改同目录下的 config.json 来添加更多车型")
            logger.info("4. 可以修改同目录下的 data_path.py 来调整路径和密码配置")

        else:
            logger.error("错误: 编译失败，dist目录不存在")

    except subprocess.CalledProcessError as e:
        logger.error(f"编译失败: {e}")
    except Exception as e:
        logger.error(f"发生错误: {e}")


# 简化的日志配置，只输出到控制台
def setup_logging():
    """设置日志配置，完整输出到控制台"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # 只使用控制台处理器
        ]
    )
    # 不移除paramiko的详细日志，保持完整输出
    logging.getLogger("paramiko").setLevel(logging.INFO)


if __name__ == "__main__":
    setup_logging()
    build_exe()