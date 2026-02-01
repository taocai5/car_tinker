import tkinter as tk
import sys
import os
import logging
from ssh_manager import SSHManager
from file_editor import FileEditorWindow
from ui import TerminalManagerUI
from data_path import get_icon_path, create_default_config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    try:
        # 创建主窗口
        root = tk.Tk()

        # 设置窗口标题
        root.title("车型终端管理器")

        # 设置窗口图标
        try:
            icon_path = get_icon_path()
            if icon_path and os.path.exists(icon_path):
                root.iconbitmap(icon_path)
                logger.info(f"已设置窗口图标: {icon_path}")
            else:
                logger.warning("图标文件不存在，使用默认图标")
        except Exception as e:
            logger.error(f"设置图标失败: {e}")

        # 检查配置文件是否存在，如果不存在则创建默认配置
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if not os.path.exists(config_path):
            logger.warning("配置文件不存在，创建默认配置")
            create_default_config()

        # 初始化SSH管理器
        ssh_manager = SSHManager()

        # 创建UI
        app = TerminalManagerUI(root, ssh_manager, FileEditorWindow)

        # 设置窗口关闭事件
        def on_closing():
            try:
                if ssh_manager.is_connected():
                    ssh_manager.disconnect()
                root.destroy()
            except Exception as e:
                logger.error(f"关闭窗口时出错: {e}")
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        # 启动主循环
        logger.info("应用程序启动成功")
        root.mainloop()

    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        # 显示错误对话框
        error_root = tk.Tk()
        error_root.withdraw()  # 隐藏主窗口
        from tkinter import messagebox
        messagebox.showerror("启动错误", f"应用程序启动失败:\n{str(e)}\n\n请检查文件完整性并重新启动。")
        error_root.destroy()


if __name__ == "__main__":
    main()