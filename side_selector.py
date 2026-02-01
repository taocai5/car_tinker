import tkinter as tk
import logging
from data_path import get_icon_path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SideSelector:
    def __init__(self, parent, car_name, a_side_ip, b_side_ip):
        self.parent = parent
        self.car_name = car_name
        self.a_side_ip = a_side_ip
        self.b_side_ip = b_side_ip
        self.selected_side = None
        self.root = None

        try:
            self.create_dialog()
            logger.info("A/B面选择器初始化成功")
        except Exception as e:
            logger.error(f"A/B面选择器初始化失败: {e}")

    def set_window_icon(self, window):
        """设置窗口图标"""
        try:
            icon_path = get_icon_path()
            if icon_path:
                window.iconbitmap(icon_path)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"设置窗口图标失败: {e}")
            return False

    def create_dialog(self):
        """创建A/B面选择对话框"""
        try:
            self.root = tk.Toplevel(self.parent)
            self.root.title("选择连接面")
            self.root.geometry("400x200")
            self.root.resizable(False, False)
            self.root.transient(self.parent)
            self.root.grab_set()

            # 设置窗口图标
            self.set_window_icon(self.root)

            # 居中显示
            self.root.geometry("+%d+%d" % (
                self.parent.winfo_rootx() + 50,
                self.parent.winfo_rooty() + 50
            ))

            # 标题
            title_label = tk.Label(self.root, text=f"选择 {self.car_name} 的连接面",
                                   font=("Arial", 12, "bold"))
            title_label.pack(pady=15)

            # 按钮框架
            button_frame = tk.Frame(self.root)
            button_frame.pack(pady=20)

            # A面按钮
            a_side_button = tk.Button(button_frame, text=f"A面\n{self.a_side_ip}",
                                      command=self.select_a_side,
                                      bg="lightblue", width=15, height=3,
                                      font=("Arial", 10, "bold"))
            a_side_button.pack(side=tk.LEFT, padx=10)

            # B面按钮
            b_side_button = tk.Button(button_frame, text=f"B面\n{self.b_side_ip}",
                                      command=self.select_b_side,
                                      bg="lightgreen", width=15, height=3,
                                      font=("Arial", 10, "bold"))
            b_side_button.pack(side=tk.LEFT, padx=10)

            # 取消按钮
            cancel_button = tk.Button(self.root, text="取消",
                                      command=self.cancel,
                                      bg="lightcoral", width=10)
            cancel_button.pack(pady=10)

            # 绑定回车和ESC键
            self.root.bind('<Return>', lambda e: self.select_a_side())
            self.root.bind('<Escape>', lambda e: self.cancel())

            # 等待对话框关闭
            self.parent.wait_window(self.root)

            logger.info("A/B面选择对话框创建成功")

        except Exception as e:
            logger.error(f"创建A/B面选择对话框失败: {e}")
            raise

    def select_a_side(self):
        """选择A面"""
        try:
            self.selected_side = "A"
            self.root.destroy()
            logger.info("用户选择了A面")
        except Exception as e:
            logger.error(f"选择A面操作失败: {e}")

    def select_b_side(self):
        """选择B面"""
        try:
            self.selected_side = "B"
            self.root.destroy()
            logger.info("用户选择了B面")
        except Exception as e:
            logger.error(f"选择B面操作失败: {e}")

    def cancel(self):
        """取消选择"""
        try:
            self.selected_side = None
            self.root.destroy()
            logger.info("用户取消了选择")
        except Exception as e:
            logger.error(f"取消选择操作失败: {e}")

    def get_selected_side(self):
        """获取选择的面"""
        return self.selected_side