import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import logging
from side_selector import SideSelector
from data_path import (
    FILE_PATHS,
    get_icon_path,
    get_config_path,
    create_default_config,
    get_full_adas_file_path,
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TerminalManagerUI:
    def __init__(self, root, ssh_manager, file_editor_class):
        self.root = root
        self.ssh_manager = ssh_manager
        self.file_editor_class = file_editor_class
        self.terminals = {}
        self.force_direct_var = tk.BooleanVar(value=False)  # 全局强制车机直连开关
        self.car_env_mode = False  # 是否车载直连环境

        self.prompt_env_mode()
        self.load_config()
        self.create_widgets()

    def prompt_env_mode(self):
        """启动前选择环境：车载直连 / 远程跳板"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("选择环境")
            dialog.geometry("320x160")
            dialog.resizable(False, False)
            dialog.grab_set()
            dialog.transient(self.root)

            mode_var = tk.StringVar(value="remote")

            tk.Label(dialog, text="请选择运行环境", font=("Arial", 12, "bold")).pack(pady=10)
            tk.Radiobutton(dialog, text="远程环境（跳板机）", variable=mode_var, value="remote").pack(anchor=tk.W, padx=20, pady=5)
            tk.Radiobutton(dialog, text="车载环境（直连A/B）", variable=mode_var, value="car").pack(anchor=tk.W, padx=20, pady=5)

            def confirm():
                self.car_env_mode = mode_var.get() == "car"
                if self.car_env_mode:
                    self.force_direct_var.set(True)
                dialog.destroy()

            tk.Button(dialog, text="确定", width=10, command=confirm).pack(pady=10)
            self.root.wait_window(dialog)
        except Exception as e:
            logger.error(f"环境选择对话框失败: {e}")
            # 若异常，默认远程模式

    def set_window_icon(self, window):
        """设置窗口图标"""
        try:
            icon_path = get_icon_path()
            if icon_path and os.path.exists(icon_path):
                window.iconbitmap(icon_path)
                return True
            else:
                logger.warning("图标文件不存在，使用默认图标")
                return False
        except Exception as e:
            logger.error(f"设置窗口图标失败: {e}")
            return False

    def load_config(self):
        """加载车型配置"""
        try:
            if self.car_env_mode:
                # 车载环境：使用固定A/B面，跳过跳板机列表
                self.terminals = {
                    "CAR_HEADUNIT_LOCAL": {
                        "connection_type": "direct",
                        "a_side": "192.168.1.6",
                        "b_side": "192.168.1.70",
                        "a_side_username": "root",
                        "b_side_username": "root",
                        "a_side_password": "Huawei12#$",
                        "b_side_password": "Huawei12#$",
                        "working_directory": FILE_PATHS['default_working_directory'],
                        "port": 22,
                    }
                }
                logger.info("车载环境：已加载本地直连配置")
            else:
                config_file = get_config_path()
                logger.info(f"正在读取配置文件: {config_file}")
                
                if os.path.exists(config_file):
                    try:
                        with open(config_file, "r", encoding="utf-8") as f:
                            self.terminals = json.load(f)
                        logger.info(f"成功加载配置文件，共 {len(self.terminals)} 个车型")
                    except json.JSONDecodeError as je:
                        logger.error(f"配置文件JSON格式错误: {je}")
                        self.terminals = {}
                        messagebox.showerror("配置错误", f"配置文件格式错误:\n{je}")
                    except Exception as re:
                        logger.error(f"读取配置文件失败: {re}")
                        self.terminals = {}
                else:
                    logger.warning(f"配置文件 {config_file} 不存在，创建默认配置")
                    if create_default_config():
                        # 重新加载配置
                        try:
                            with open(config_file, "r", encoding="utf-8") as f:
                                self.terminals = json.load(f)
                            logger.info("默认配置文件创建并加载成功")
                        except Exception as e:
                            logger.error(f"加载新创建的配置文件失败: {e}")
                            self.terminals = {}
                    else:
                        self.terminals = {}
                        logger.error("创建默认配置文件失败")

        except Exception as e:
            logger.error(f"加载配置文件主流程失败: {e}")
            self.terminals = {}
            messagebox.showwarning("配置加载失败", f"加载配置文件失败: {str(e)}\n\n将使用空配置运行。")

    def get_ssh_command(self, car_config):
        """根据配置生成SSH命令"""
        try:
            return car_config.get('ssh_command', '')
        except Exception as e:
            logger.error(f"获取SSH命令失败: {e}")
            return ''

    def create_widgets(self):
        """创建界面组件"""
        try:
            self.root.title("车型终端管理器")
            self.root.geometry("1100x600")

            # 设置主窗口图标
            self.set_window_icon(self.root)

            # 标题
            title_label = tk.Label(self.root, text="车型终端连接管理器",
                                   font=("Arial", 16, "bold"))
            title_label.pack(pady=10)

            # 状态显示
            self.status_var = tk.StringVar()
            self.status_var.set("准备就绪 - 选择车型进行连接")
            status_label = tk.Label(self.root, textvariable=self.status_var,
                                    relief=tk.SUNKEN, anchor=tk.W, bg="lightgray")
            status_label.pack(fill=tk.X, side=tk.BOTTOM)

            # 连接信息显示
            self.connection_info_var = tk.StringVar()
            self.connection_info_var.set("未连接")
            connection_info_label = tk.Label(self.root, textvariable=self.connection_info_var,
                                             relief=tk.SUNKEN, anchor=tk.W, bg="white")
            connection_info_label.pack(fill=tk.X, side=tk.BOTTOM)

            # 主内容框架
            main_frame = tk.Frame(self.root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # 左侧列表框架
            list_frame = tk.LabelFrame(main_frame, text="车型列表", padx=10, pady=10)
            list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 搜索框
            search_frame = tk.Frame(list_frame)
            search_frame.pack(fill=tk.X, pady=5)

            tk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
            self.search_var = tk.StringVar()
            search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=30)
            search_entry.pack(side=tk.LEFT, padx=5)
            search_entry.bind("<KeyRelease>", self.filter_terminals)

            # 车型列表
            self.tree = ttk.Treeview(list_frame,
                                     columns=("ssh_command", "a_side", "b_side", "working_directory"),
                                     show="tree headings", height=20)
            self.tree.heading("#0", text="车型名称")
            self.tree.heading("ssh_command", text="SSH命令")
            self.tree.heading("a_side", text="A面地址")
            self.tree.heading("b_side", text="B面地址")
            self.tree.heading("working_directory", text="工作目录")

            self.tree.column("#0", width=180)
            self.tree.column("ssh_command", width=200)
            self.tree.column("a_side", width=100)
            self.tree.column("b_side", width=100)
            self.tree.column("working_directory", width=200)

            # 滚动条
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=scrollbar.set)

            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # 绑定事件
            self.tree.bind("<Double-1>", self.on_item_double_click)

            # 右侧操作框架
            action_frame = tk.LabelFrame(main_frame, text="操作面板", padx=10, pady=10, width=200)
            action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
            action_frame.pack_propagate(False)

            # 直连开关（root@车机）
            force_direct_cb = tk.Checkbutton(
                action_frame,
                text="车机直连 (root)",
                variable=self.force_direct_var,
                onvalue=True,
                offvalue=False,
            )
            force_direct_cb.pack(pady=(0, 5), anchor=tk.W)

            # 连接车辆按钮
            self.connect_vehicle_button = tk.Button(action_frame, text="连接车辆",
                                                    command=self.connect_vehicle,
                                                    bg="lightblue", width=15, height=2)
            self.connect_vehicle_button.pack(pady=5, fill=tk.X)

            # 选择面按钮
            self.select_side_button = tk.Button(action_frame, text="选择A/B面",
                                                command=self.select_side,
                                                bg="lightyellow", width=15, height=2,
                                                state=tk.DISABLED)
            self.select_side_button.pack(pady=5, fill=tk.X)

            # 检查文件按钮
            self.check_file_button = tk.Button(action_frame, text="检查文件",
                                               command=self.check_file,
                                               bg="lightgray", width=15, height=2,
                                               state=tk.DISABLED)
            self.check_file_button.pack(pady=5, fill=tk.X)

            # 挂载文件系统按钮
            self.mount_button = tk.Button(action_frame, text="挂载文件系统",
                                          command=self.mount_filesystem,
                                          bg="lightyellow", width=15, height=2,
                                          state=tk.DISABLED)
            self.mount_button.pack(pady=5, fill=tk.X)

            # 编辑文件按钮
            self.edit_button = tk.Button(action_frame, text="编辑params.json",
                                         command=self.open_file_editor,
                                         bg="lightgreen", width=15, height=2,
                                         state=tk.DISABLED)
            self.edit_button.pack(pady=5, fill=tk.X)

            # 编辑ADAS参数按钮
            self.edit_adas_button = tk.Button(action_frame, text="编辑adas_params.json",
                                              command=self.open_adas_editor,
                                              bg="lightgreen", width=15, height=2,
                                              state=tk.DISABLED)
            self.edit_adas_button.pack(pady=5, fill=tk.X)

            # 断开连接按钮
            self.disconnect_button = tk.Button(action_frame, text="断开连接",
                                               command=self.disconnect,
                                               bg="lightcoral", width=15, height=2,
                                               state=tk.DISABLED)
            self.disconnect_button.pack(pady=5, fill=tk.X)

            # 刷新按钮
            refresh_button = tk.Button(action_frame, text="刷新列表",
                                       command=self.refresh_list,
                                       bg="white", width=15, height=2)
            refresh_button.pack(pady=5, fill=tk.X)

            # 显示工作目录按钮
            show_working_dir_button = tk.Button(action_frame, text="显示工作目录",
                                                command=self.show_working_directory,
                                                bg="lightgoldenrod", width=15, height=2)
            show_working_dir_button.pack(pady=5, fill=tk.X)

            # 车载环境：跳过跳板机步骤，直接允许选A/B
            if self.car_env_mode:
                self.connect_vehicle_button.config(state=tk.DISABLED)
                self.select_side_button.config(state=tk.NORMAL)
                # 预选唯一车型
                self.root.after(0, self.select_first_car)

            # 初始加载数据
            self.refresh_list()
            self.update_connection_info()

            logger.info("UI界面创建成功")

        except Exception as e:
            logger.error(f"创建UI界面失败: {e}")
            messagebox.showerror("UI错误", f"创建用户界面失败:\n{str(e)}")

    def filter_terminals(self, event=None):
        """过滤车型列表"""
        try:
            search_term = self.search_var.get().lower()
            self.refresh_list(search_term)
        except Exception as e:
            logger.error(f"过滤车型列表失败: {e}")

    def select_first_car(self):
        """车载环境下自动选中第一条车型"""
        try:
            items = self.tree.get_children()
            if items:
                self.tree.selection_set(items[0])
        except Exception as e:
            logger.error(f"自动选中车型失败: {e}")

    def refresh_list(self, filter_text=""):
        """刷新车型列表"""
        try:
            self.tree.delete(*self.tree.get_children())

            for name, config in self.terminals.items():
                try:
                    connection_type = config.get('connection_type', 'tunnel')
                    ssh_command = self.get_ssh_command(config)
                    if connection_type == 'direct' and not ssh_command:
                        ssh_command = 'direct'
                    a_side = config.get('a_side', 'N/A')
                    b_side = config.get('b_side', 'N/A')
                    working_directory = config.get('working_directory', '默认目录')

                    if (filter_text in name.lower() or
                            filter_text in ssh_command.lower() or
                            filter_text in a_side.lower() or
                            filter_text in b_side.lower() or
                            filter_text in working_directory.lower()):

                        item = self.tree.insert("", "end", text=name,
                                                values=(ssh_command, a_side, b_side, working_directory))
                        # 车载环境只有一个项，默认选中
                        if self.car_env_mode:
                            self.tree.selection_set(item)
                except Exception as e:
                    logger.error(f"添加车型 {name} 到列表失败: {e}")

            logger.info(f"刷新车型列表完成，共 {len(self.tree.get_children())} 个车型")

        except Exception as e:
            logger.error(f"刷新车型列表失败: {e}")

    def on_item_double_click(self, event):
        """双击连接"""
        try:
            self.connect_vehicle()
        except Exception as e:
            logger.error(f"双击连接失败: {e}")
            messagebox.showerror("操作失败", f"连接车辆失败:\n{str(e)}")

    def get_selected_car(self):
        """获取选中的车型"""
        try:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("警告", "请先选择一个车型")
                return None, None

            item = selected[0]
            car_name = self.tree.item(item, "text")
            config = self.terminals.get(car_name)

            if not config:
                messagebox.showerror("错误", "找不到车型配置")
                return None, None

            return car_name, config
        except Exception as e:
            logger.error(f"获取选中车型失败: {e}")
            messagebox.showerror("错误", f"获取选中车型失败:\n{str(e)}")
            return None, None

    def connect_vehicle(self):
        """连接车辆"""
        try:
            car_name, config = self.get_selected_car()
            if not car_name:
                return

            connection_type = config.get('connection_type', 'tunnel')
            working_directory = config.get('working_directory')

            # 如果全局开启“车机直连”或配置为 direct，则直接 SSH root@车机
            if self.force_direct_var.get() or connection_type == 'direct':
                self.status_var.set(f"正在直连 {car_name} ...")
                self.root.update()

                default_side = config.get('preferred_side', 'A')
                ip = config.get('a_side') if default_side == 'A' else config.get('b_side')
                username = config.get(f'{default_side.lower()}_side_username', 'root')
                password = config.get(f'{default_side.lower()}_side_password')
                port = config.get('port', 22)

                success, message = self.ssh_manager.connect_headunit_direct(
                    car_name, default_side, ip, username, password, port, working_directory
                )
                if success:
                    self.status_var.set(f"已直连到 {car_name} - {default_side}面")
                    self.connect_vehicle_button.config(state=tk.DISABLED)
                    self.select_side_button.config(state=tk.NORMAL)  # 允许切换到另一面
                    self.check_file_button.config(state=tk.NORMAL)
                    self.mount_button.config(state=tk.NORMAL)
                    self.edit_button.config(state=tk.NORMAL)
                    self.edit_adas_button.config(state=tk.NORMAL)
                    self.disconnect_button.config(state=tk.NORMAL)
                    self.update_connection_info()
                    messagebox.showinfo("成功", message)
                    logger.info(f"直连完成: {car_name}, {default_side}面")
                else:
                    self.status_var.set("直连失败")
                    messagebox.showerror("错误", message)
                    logger.error(f"直连失败: {message}")
                return

            # 跳板机模式（原逻辑）
            ssh_command = self.get_ssh_command(config)
            port = config.get('port', 22)

            self.status_var.set(f"正在连接车辆 {car_name}...")
            self.root.update()

            success, message = self.ssh_manager.connect_to_vehicle(car_name, ssh_command, port, working_directory)

            if success:
                self.status_var.set(f"已连接到车辆 {car_name}")
                self.connect_vehicle_button.config(state=tk.DISABLED)
                self.select_side_button.config(state=tk.NORMAL)
                self.disconnect_button.config(state=tk.NORMAL)
                self.update_connection_info()
                messagebox.showinfo("成功", message)
                logger.info(f"成功连接到车辆: {car_name}")
            else:
                self.status_var.set("车辆连接失败")
                messagebox.showerror("错误", message)
                logger.error(f"连接车辆失败: {message}")

        except Exception as e:
            logger.error(f"连接车辆操作失败: {e}")
            messagebox.showerror("错误", f"连接车辆失败:\n{str(e)}")

    def select_side(self):
        """选择A/B面 - 使用隧道连接"""
        try:
            car_name, config = self.get_selected_car()
            if not car_name:
                return

            a_side_ip = config.get('a_side', '192.168.1.6')
            b_side_ip = config.get('b_side', '192.168.1.70')

            # 弹出A/B面选择对话框
            selector = SideSelector(self.root, car_name, a_side_ip, b_side_ip)
            selected_side = selector.get_selected_side()

            if selected_side:
                self.status_var.set(f"正在连接{selected_side}面...")
                self.root.update()

                if selected_side == "A":
                    ip = a_side_ip
                else:
                    ip = b_side_ip

                connection_type = config.get('connection_type', 'tunnel')
                port = config.get('port', 22)

                # 车载环境：确保直连模式已准备
                if self.car_env_mode or self.force_direct_var.get() or connection_type == 'direct':
                    self.ssh_manager.prepare_direct_vehicle(car_name, config.get('working_directory'))

                if self.force_direct_var.get() or connection_type == 'direct':
                    username = config.get(f'{selected_side.lower()}_side_username')
                    password = config.get(f'{selected_side.lower()}_side_password')
                    success, message = self.ssh_manager.connect_to_side_direct(
                        selected_side, ip, username, password, port
                    )
                else:
                    # 使用隧道连接
                    success, message = self.ssh_manager.connect_to_side_tunnel(selected_side, ip, port=port)

                if success:
                    self.status_var.set(f"已连接到{selected_side}面")
                    self.check_file_button.config(state=tk.NORMAL)
                    self.mount_button.config(state=tk.NORMAL)
                    self.edit_button.config(state=tk.NORMAL)
                    self.edit_adas_button.config(state=tk.NORMAL)
                    self.update_connection_info()
                    messagebox.showinfo("成功", message)
                    logger.info(f"成功连接到{selected_side}面: {car_name}")
                else:
                    self.status_var.set(f"{selected_side}面连接失败")
                    messagebox.showerror("错误", message)
                    logger.error(f"连接{selected_side}面失败: {message}")

        except Exception as e:
            logger.error(f"选择A/B面操作失败: {e}")
            messagebox.showerror("错误", f"选择A/B面失败:\n{str(e)}")

    def check_file(self):
        """检查文件是否存在"""
        try:
            success, message = self.ssh_manager.check_file_exists()

            if success:
                messagebox.showinfo("成功", f"文件存在\n工作目录: {self.ssh_manager.get_current_working_directory()}")
                logger.info("文件存在检查成功")
            else:
                messagebox.showwarning("警告", f"文件检查失败: {message}")
                logger.warning(f"文件存在检查失败: {message}")

        except Exception as e:
            logger.error(f"检查文件操作失败: {e}")
            messagebox.showerror("错误", f"检查文件失败:\n{str(e)}")

    def mount_filesystem(self):
        """挂载文件系统"""
        try:
            success, message = self.ssh_manager.mount_filesystem()

            if success:
                messagebox.showinfo("成功", "文件系统挂载成功")
                logger.info("文件系统挂载成功")
            else:
                messagebox.showerror("错误", f"挂载失败: {message}")
                logger.error(f"文件系统挂载失败: {message}")

        except Exception as e:
            logger.error(f"挂载文件系统操作失败: {e}")
            messagebox.showerror("错误", f"挂载文件系统失败:\n{str(e)}")

    def open_file_editor(self):
        """打开文件编辑器"""
        try:
            if not self.ssh_manager.is_side_connected():
                messagebox.showerror("错误", "未连接到A/B面")
                return

            editor = self.file_editor_class(self.root, self.ssh_manager)
            # 设置文件编辑器窗口图标
            self.set_window_icon(editor.window)
            logger.info("文件编辑器已打开")

        except Exception as e:
            logger.error(f"打开文件编辑器失败: {e}")
            messagebox.showerror("错误", f"打开文件编辑器失败:\n{str(e)}")

    def open_adas_editor(self):
        """打开adas_params.json编辑器"""
        try:
            if not self.ssh_manager.is_side_connected():
                messagebox.showerror("错误", "未连接到A/B面")
                return

            editor = self.file_editor_class(
                self.root,
                self.ssh_manager,
                file_path_resolver=get_full_adas_file_path,
                read_func=self.ssh_manager.read_adas_file_persistent,
                write_func=self.ssh_manager.write_adas_file_persistent,
                window_title="编辑 adas_params.json",
                file_label="adas_params.json"
            )
            self.set_window_icon(editor.window)
            logger.info("ADAS 文件编辑器已打开")

        except Exception as e:
            logger.error(f"打开ADAS文件编辑器失败: {e}")
            messagebox.showerror("错误", f"打开ADAS文件编辑器失败:\n{str(e)}")

    def show_working_directory(self):
        """显示当前工作目录"""
        try:
            if self.ssh_manager.is_connected():
                working_dir = self.ssh_manager.get_current_working_directory()
                messagebox.showinfo("工作目录", f"当前工作目录: {working_dir}")
            else:
                messagebox.showwarning("警告", "未连接到车辆")
        except Exception as e:
            logger.error(f"显示工作目录失败: {e}")
            messagebox.showerror("错误", f"显示工作目录失败:\n{str(e)}")

    def disconnect(self):
        """断开连接"""
        try:
            self.ssh_manager.disconnect()
            self.status_var.set("已断开连接")
            self.connect_vehicle_button.config(state=tk.NORMAL)
            self.select_side_button.config(state=tk.DISABLED)
            self.check_file_button.config(state=tk.DISABLED)
            self.mount_button.config(state=tk.DISABLED)
            self.edit_button.config(state=tk.DISABLED)
            self.edit_adas_button.config(state=tk.DISABLED)
            self.disconnect_button.config(state=tk.DISABLED)
            self.update_connection_info()
            logger.info("已断开连接")

        except Exception as e:
            logger.error(f"断开连接失败: {e}")
            messagebox.showerror("错误", f"断开连接失败:\n{str(e)}")

    def update_connection_info(self):
        """更新连接信息显示"""
        try:
            if self.ssh_manager.is_connected():
                car_name = self.ssh_manager.get_current_car_name()
                side = self.ssh_manager.get_current_side()
                working_dir = self.ssh_manager.get_current_working_directory()
                direct_tag = "（直连）" if self.ssh_manager.is_direct_mode() else ""

                if side:
                    info = f"已连接{direct_tag}: {car_name} - {side}面\n工作目录: {working_dir}"
                else:
                    info = f"已连接到车辆{direct_tag}: {car_name}\n工作目录: {working_dir}"
            else:
                info = "未连接"

            self.connection_info_var.set(info)
        except Exception as e:
            logger.error(f"更新连接信息失败: {e}")
            self.connection_info_var.set("连接信息获取失败")