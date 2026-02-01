import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import logging
import re
from data_path import FILE_PATHS, get_full_file_path, get_icon_path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FileEditorWindow:
    def __init__(
            self,
            parent,
            ssh_manager,
            *,
            file_path_resolver=get_full_file_path,
            read_func=None,
            write_func=None,
            window_title="编辑 params.json",
            file_label="params.json"
    ):
        self.parent = parent
        self.ssh_manager = ssh_manager
        self.file_path_resolver = file_path_resolver
        self.read_func = read_func or self.ssh_manager.read_params_file_persistent
        self.write_func = write_func or self.ssh_manager.write_params_file_persistent
        self.window_title = window_title
        self.file_label = file_label
        self.window = None
        self.text_widget = None
        self.search_frame = None
        self.search_entry = None
        self.search_var = None
        self.current_search_matches = []
        self.current_search_index = -1
        self.search_highlight_tag = "search_highlight"
        self.current_search_tag = "current_search"

        # 计算器窗口引用
        self.calculator_window = None

        try:
            self.create_window()
            self.load_file_content()
            logger.info("文件编辑器初始化成功")
        except Exception as e:
            logger.error(f"文件编辑器初始化失败: {e}")
            messagebox.showerror("错误", f"文件编辑器初始化失败:\n{str(e)}")

    def show_calculator(self):
        """显示计算器窗口"""
        try:
            # 如果计算器窗口已经存在，则将其置顶
            if self.calculator_window and self.calculator_window.winfo_exists():
                self.calculator_window.lift()
                self.calculator_window.focus_force()
                return

            # 创建计算器窗口
            self.calculator_window = tk.Toplevel(self.window)
            self.calculator_window.title("TTC 计算器")
            self.calculator_window.geometry("350x400")
            self.calculator_window.resizable(False, False)
            self.calculator_window.transient(self.window)
            self.calculator_window.configure(bg='white')

            # 设置窗口图标
            self.set_window_icon(self.calculator_window)

            # 居中显示
            self.center_calculator_window()

            # 创建计算器内容
            self.create_calculator_content()

            # 绑定窗口关闭事件
            self.calculator_window.protocol("WM_DELETE_WINDOW", self.hide_calculator)

            logger.info("计算器窗口已显示")

        except Exception as e:
            logger.error(f"显示计算器失败: {e}")
            messagebox.showerror("错误", f"显示计算器失败:\n{str(e)}")

    def center_calculator_window(self):
        """计算器窗口居中显示"""
        try:
            self.calculator_window.update_idletasks()
            width = self.calculator_window.winfo_width()
            height = self.calculator_window.winfo_height()

            # 计算相对于主窗口的位置
            main_x = self.window.winfo_x()
            main_y = self.window.winfo_y()
            main_width = self.window.winfo_width()

            x = main_x + main_width + 10  # 在主窗口右侧显示
            y = main_y + (self.window.winfo_height() // 2) - (height // 2)

            self.calculator_window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception as e:
            logger.error(f"计算器窗口居中失败: {e}")

    def create_calculator_content(self):
        """创建计算器内容"""
        try:
            # 计算器标题
            calc_title = tk.Label(self.calculator_window, text="TTC 计算器",
                                  font=("Arial", 14, "bold"), bg='white')
            calc_title.pack(pady=15)

            # 计算器主框架
            calc_main_frame = tk.Frame(self.calculator_window, bg='white')
            calc_main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # 距离输入
            distance_frame = tk.Frame(calc_main_frame, bg='white')
            distance_frame.pack(fill=tk.X, pady=8)

            tk.Label(distance_frame, text="距离 (m):",
                     font=("Arial", 11), bg='white').pack(side=tk.LEFT)

            self.distance_var = tk.StringVar()
            distance_entry = tk.Entry(distance_frame, textvariable=self.distance_var,
                                      width=15, font=("Arial", 11))
            distance_entry.pack(side=tk.RIGHT, padx=10)
            distance_entry.bind('<KeyRelease>', self.calculate_ttc)

            # 速度输入
            speed_frame = tk.Frame(calc_main_frame, bg='white')
            speed_frame.pack(fill=tk.X, pady=8)

            tk.Label(speed_frame, text="速度 (kph):",
                     font=("Arial", 11), bg='white').pack(side=tk.LEFT)

            # 速度下拉选择框
            self.speed_var = tk.StringVar()
            speed_values = ['10', '20', '30', '40', '50', '60', '70', '80', '90', '100', '110', '120']
            speed_combo = ttk.Combobox(speed_frame, textvariable=self.speed_var,
                                       values=speed_values, width=13, state="normal",
                                       font=("Arial", 11))
            speed_combo.pack(side=tk.RIGHT, padx=10)
            speed_combo.bind('<<ComboboxSelected>>', self.calculate_ttc)
            speed_combo.bind('<KeyRelease>', self.calculate_ttc)

            # TTC结果显示
            ttc_frame = tk.Frame(calc_main_frame, bg='white')
            ttc_frame.pack(fill=tk.X, pady=8)

            tk.Label(ttc_frame, text="TTC (s):",
                     font=("Arial", 11), bg='white').pack(side=tk.LEFT)

            self.ttc_var = tk.StringVar()
            ttc_result = tk.Entry(ttc_frame, textvariable=self.ttc_var,
                                  width=15, font=("Arial", 11), state='readonly',
                                  bg='lightgray', fg='black')
            ttc_result.pack(side=tk.RIGHT, padx=10)

            # 分隔线
            separator = ttk.Separator(calc_main_frame, orient='horizontal')
            separator.pack(fill=tk.X, pady=15)

            # 计算器说明
            info_text = (
                "TTC (Time to Collision) 计算公式:\n"
                "TTC = 距离 / (速度 / 3.6)\n\n"
                "其中:\n"
                "- 距离: 米 (m)\n"
                "- 速度: 公里/小时 (kph)\n"
                "- TTC: 秒 (s)"
            )

            info_label = tk.Label(calc_main_frame, text=info_text,
                                  font=("Arial", 10), bg='white', justify=tk.LEFT,
                                  relief=tk.SUNKEN, bd=1, padx=10, pady=10)
            info_label.pack(fill=tk.X, pady=10)

            # 按钮框架
            calc_button_frame = tk.Frame(calc_main_frame, bg='white')
            calc_button_frame.pack(pady=10)

            # 清空按钮
            clear_button = tk.Button(calc_button_frame, text="清空输入",
                                     command=self.clear_calculator,
                                     bg="lightyellow", width=12)
            clear_button.pack(side=tk.LEFT, padx=5)

            # 关闭按钮
            close_button = tk.Button(calc_button_frame, text="关闭",
                                     command=self.hide_calculator,
                                     bg="lightcoral", width=12)
            close_button.pack(side=tk.LEFT, padx=5)

            logger.info("计算器内容创建成功")

        except Exception as e:
            logger.error(f"创建计算器内容失败: {e}")

    def calculate_ttc(self, event=None):
        """计算TTC值"""
        try:
            # 获取输入值
            distance_str = self.distance_var.get().strip()
            speed_str = self.speed_var.get().strip()

            # 检查输入是否有效
            if not distance_str or not speed_str:
                self.ttc_var.set("")
                return

            try:
                distance = float(distance_str)
                speed = float(speed_str)

                # 验证输入范围
                if distance <= 0 or speed <= 0:
                    self.ttc_var.set("输入无效")
                    return

                # 计算TTC: TTC = 距离 / (速度 / 3.6)
                speed_mps = speed / 3.6
                ttc = distance / speed_mps

                # 保留6位小数
                ttc_formatted = f"{ttc:.6f}"
                self.ttc_var.set(ttc_formatted)

                logger.info(f"TTC计算: 距离={distance}m, 速度={speed}kph, TTC={ttc_formatted}s")

            except ValueError:
                self.ttc_var.set("输入错误")

        except Exception as e:
            logger.error(f"计算TTC失败: {e}")
            self.ttc_var.set("计算错误")

    def clear_calculator(self):
        """清空计算器输入"""
        try:
            self.distance_var.set("")
            self.speed_var.set("")
            self.ttc_var.set("")
            logger.info("计算器输入已清空")
        except Exception as e:
            logger.error(f"清空计算器失败: {e}")

    def hide_calculator(self):
        """隐藏计算器"""
        try:
            if self.calculator_window and self.calculator_window.winfo_exists():
                self.calculator_window.destroy()
            self.calculator_window = None
            logger.info("计算器窗口已隐藏")
        except Exception as e:
            logger.error(f"隐藏计算器失败: {e}")

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

    def create_window(self):
        """创建文件编辑窗口"""
        try:
            self.window = tk.Toplevel(self.parent)
            self.window.title(self.window_title)
            self.window.geometry("900x700")
            self.window.configure(bg='white')

            # 设置为弹出模式
            self.window.transient(self.parent)
            self.window.grab_set()

            # 设置窗口居中显示
            self.center_window()

            # 设置窗口图标
            self.set_window_icon(self.window)

            # 创建编辑器组件
            self.create_editor_widgets()

            # 绑定窗口关闭事件
            self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

            logger.info("文件编辑器窗口创建成功")

        except Exception as e:
            logger.error(f"创建文件编辑器窗口失败: {e}")
            raise

    def create_editor_widgets(self):
        """创建文件编辑器组件"""
        try:
            # 标题
            title_label = tk.Label(self.window, text=f"{self.file_label} 编辑器",
                                   font=("Arial", 14, "bold"), bg='white')
            title_label.pack(pady=10)

            # 文件路径显示
            working_dir = self.ssh_manager.get_current_working_directory()
            file_path = self.file_path_resolver(working_dir)

            path_label = tk.Label(self.window,
                                  text=f"文件路径: {file_path}",
                                  font=("Arial", 10), bg='white', fg='gray')
            path_label.pack(pady=5)

            # 搜索框架
            self.create_search_frame()

            # 文本编辑区域
            text_frame = tk.Frame(self.window, bg='white')
            text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)

            # 添加行号
            self.line_numbers = tk.Text(text_frame, width=4, padx=3, takefocus=0,
                                        border=0, background='lightgray', state='disabled')
            self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

            # 主文本编辑框
            self.text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                                         font=("Consolas", 11))
            self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # 配置搜索高亮样式
            self.text_widget.tag_config(self.search_highlight_tag,
                                        background='yellow',
                                        foreground='black')
            self.text_widget.tag_config(self.current_search_tag,
                                        background='orange',
                                        foreground='black')

            # 绑定事件来更新行号
            self.text_widget.bind('<KeyPress>', self.update_line_numbers)
            self.text_widget.bind('<MouseWheel>', self.update_line_numbers)

            # 按钮框架
            button_frame = tk.Frame(self.window, bg='white')
            button_frame.pack(pady=10)

            # 保存按钮
            save_button = tk.Button(button_frame, text="保存",
                                    command=self.save_file,
                                    bg="lightgreen", width=12, height=2)
            save_button.pack(side=tk.LEFT, padx=5)

            # 计算器按钮
            calculator_button = tk.Button(button_frame, text="计算器",
                                          command=self.show_calculator,
                                          bg="lightblue", width=12, height=2)
            calculator_button.pack(side=tk.LEFT, padx=5)

            # 取消按钮
            cancel_button = tk.Button(button_frame, text="取消",
                                      command=self.window.destroy,
                                      bg="lightcoral", width=12, height=2)
            cancel_button.pack(side=tk.LEFT, padx=5)

            # 重新加载按钮
            reload_button = tk.Button(button_frame, text="重新加载",
                                      command=self.load_file_content,
                                      bg="lightcyan", width=12, height=2)
            reload_button.pack(side=tk.LEFT, padx=5)

            # 初始更新行号
            self.update_line_numbers()

            # 绑定快捷键
            self.bind_shortcuts()

        except Exception as e:
            logger.error(f"创建编辑器组件失败: {e}")
            raise

    def create_search_frame(self):
        """创建搜索框架"""
        try:
            self.search_frame = tk.Frame(self.window, bg='white')
            self.search_frame.pack(fill=tk.X, padx=20, pady=5)

            # 搜索标签
            search_label = tk.Label(self.search_frame, text="搜索:",
                                    font=("Arial", 10), bg='white')
            search_label.pack(side=tk.LEFT, padx=(0, 5))

            # 搜索输入框
            self.search_var = tk.StringVar()
            self.search_entry = tk.Entry(self.search_frame,
                                         textvariable=self.search_var,
                                         width=30, font=("Arial", 10))
            self.search_entry.pack(side=tk.LEFT, padx=5)
            self.search_entry.bind('<Return>', lambda e: self.search_text())
            self.search_entry.bind('<KeyRelease>', self.on_search_key_release)

            # 搜索按钮
            search_button = tk.Button(self.search_frame, text="搜索",
                                      command=self.search_text,
                                      bg="lightblue", width=8)
            search_button.pack(side=tk.LEFT, padx=5)

            # 上一个匹配项按钮
            prev_button = tk.Button(self.search_frame, text="上一个",
                                    command=self.previous_match,
                                    bg="lightyellow", width=8)
            prev_button.pack(side=tk.LEFT, padx=5)

            # 下一个匹配项按钮
            next_button = tk.Button(self.search_frame, text="下一个",
                                    command=self.next_match,
                                    bg="lightyellow", width=8)
            next_button.pack(side=tk.LEFT, padx=5)

            # 清除高亮按钮
            clear_button = tk.Button(self.search_frame, text="清除高亮",
                                     command=self.clear_highlights,
                                     bg="lightcoral", width=10)
            clear_button.pack(side=tk.LEFT, padx=5)

            # 匹配信息标签
            self.match_info_var = tk.StringVar()
            self.match_info_var.set("就绪")
            match_info_label = tk.Label(self.search_frame,
                                        textvariable=self.match_info_var,
                                        font=("Arial", 9), bg='white', fg='gray')
            match_info_label.pack(side=tk.LEFT, padx=10)

            logger.info("搜索框架创建成功")

        except Exception as e:
            logger.error(f"创建搜索框架失败: {e}")

    def center_window(self):
        """窗口居中显示"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def on_closing(self):
        """窗口关闭事件"""
        try:
            # 关闭计算器窗口
            if self.calculator_window and self.calculator_window.winfo_exists():
                self.calculator_window.destroy()

            self.window.grab_release()
            self.window.destroy()
            logger.info("文件编辑器窗口已关闭")
        except Exception as e:
            logger.error(f"关闭文件编辑器窗口失败: {e}")
            self.window.destroy()

    def bind_shortcuts(self):
        """绑定快捷键"""
        try:
            # Ctrl+F: 搜索
            self.window.bind('<Control-f>', lambda e: self.focus_search())
            self.window.bind('<Control-F>', lambda e: self.focus_search())

            # F3: 下一个匹配项
            self.window.bind('<F3>', lambda e: self.next_match())

            # Shift+F3: 上一个匹配项
            self.window.bind('<Shift-F3>', lambda e: self.previous_match())

            # Esc: 清除搜索高亮
            self.window.bind('<Escape>', lambda e: self.clear_highlights())

            # Ctrl+S: 保存
            self.window.bind('<Control-s>', lambda e: self.save_file())
            self.window.bind('<Control-S>', lambda e: self.save_file())

            logger.info("快捷键绑定成功")

        except Exception as e:
            logger.error(f"绑定快捷键失败: {e}")

    def focus_search(self):
        """聚焦到搜索框"""
        try:
            if self.search_entry:
                self.search_entry.focus_set()
                self.search_entry.select_range(0, tk.END)
        except Exception as e:
            logger.error(f"聚焦搜索框失败: {e}")

    def on_search_key_release(self, event=None):
        """搜索框按键释放事件 - 实时搜索"""
        try:
            search_text = self.search_var.get().strip()
            if len(search_text) >= 2:
                self.search_text()
            elif len(search_text) == 0:
                self.clear_highlights()
        except Exception as e:
            logger.error(f"实时搜索失败: {e}")

    def search_text(self):
        """搜索文本"""
        try:
            search_text = self.search_var.get().strip()
            if not search_text:
                self.clear_highlights()
                self.match_info_var.set("请输入搜索内容")
                return

            # 清除之前的高亮
            self.clear_highlights()

            # 获取文本内容
            content = self.text_widget.get(1.0, tk.END)
            if not content or content.strip() == "":
                self.match_info_var.set("文档为空")
                return

            # 搜索所有匹配项
            self.current_search_matches = []
            start_index = "1.0"

            while True:
                pos = self.text_widget.search(search_text, start_index,
                                              stopindex=tk.END,
                                              regexp=False,
                                              nocase=True)

                if not pos:
                    break

                end_index = f"{pos}+{len(search_text)}c"
                self.current_search_matches.append((pos, end_index))
                self.text_widget.tag_add(self.search_highlight_tag, pos, end_index)
                start_index = end_index

            # 更新匹配信息
            match_count = len(self.current_search_matches)
            if match_count > 0:
                self.current_search_index = 0
                self.highlight_current_match()
                self.match_info_var.set(f"找到 {match_count} 个匹配项")
                logger.info(f"搜索 '{search_text}' 找到 {match_count} 个匹配项")
            else:
                self.current_search_index = -1
                self.match_info_var.set("未找到匹配项")
                logger.info(f"搜索 '{search_text}' 未找到匹配项")

        except Exception as e:
            logger.error(f"搜索文本失败: {e}")
            self.match_info_var.set(f"搜索失败: {str(e)}")

    def highlight_current_match(self):
        """高亮显示当前匹配项"""
        try:
            if (self.current_search_index < 0 or
                    self.current_search_index >= len(self.current_search_matches)):
                return

            # 清除之前当前匹配的高亮
            self.text_widget.tag_remove(self.current_search_tag, "1.0", tk.END)

            # 高亮当前匹配项
            pos, end_index = self.current_search_matches[self.current_search_index]
            self.text_widget.tag_add(self.current_search_tag, pos, end_index)

            # 滚动到当前匹配项
            self.text_widget.see(pos)

            # 更新匹配信息
            self.match_info_var.set(
                f"匹配项 {self.current_search_index + 1}/{len(self.current_search_matches)}"
            )

        except Exception as e:
            logger.error(f"高亮当前匹配项失败: {e}")

    def next_match(self):
        """跳转到下一个匹配项"""
        try:
            if not self.current_search_matches:
                return

            self.current_search_index = (self.current_search_index + 1) % len(self.current_search_matches)
            self.highlight_current_match()

        except Exception as e:
            logger.error(f"跳转到下一个匹配项失败: {e}")

    def previous_match(self):
        """跳转到上一个匹配项"""
        try:
            if not self.current_search_matches:
                return

            self.current_search_index = (self.current_search_index - 1) % len(self.current_search_matches)
            self.highlight_current_match()

        except Exception as e:
            logger.error(f"跳转到上一个匹配项失败: {e}")

    def clear_highlights(self):
        """清除所有搜索高亮"""
        try:
            self.text_widget.tag_remove(self.search_highlight_tag, "1.0", tk.END)
            self.text_widget.tag_remove(self.current_search_tag, "1.0", tk.END)
            self.current_search_matches = []
            self.current_search_index = -1
            self.match_info_var.set("高亮已清除")

        except Exception as e:
            logger.error(f"清除高亮失败: {e}")

    def update_line_numbers(self, event=None):
        """更新行号显示"""
        try:
            # 获取文本行数
            lines = self.text_widget.get('1.0', tk.END).count('\n')

            # 更新行号文本
            self.line_numbers.config(state='normal')
            self.line_numbers.delete('1.0', tk.END)

            for i in range(1, lines + 1):
                self.line_numbers.insert(tk.END, f'{i}\n')

            self.line_numbers.config(state='disabled')
        except Exception as e:
            logger.error(f"更新行号失败: {e}")

    def load_file_content(self):
        """加载文件内容 - 使用持久连接"""
        try:
            if not self.ssh_manager.is_side_connected():
                messagebox.showerror("错误", "未连接到A/B面")
                self.window.destroy()
                return

            # 显示加载中
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(tk.END, "正在加载文件内容...")
            self.window.update()

            # 使用持久连接读取文件
            success, content = self.read_func()

            if success:
                self.text_widget.delete(1.0, tk.END)
                self.text_widget.insert(tk.END, content)
                self.update_line_numbers()
                self.clear_highlights()
                logger.info("文件内容加载成功")
            else:
                messagebox.showerror("错误", f"加载文件失败: {content}")
                self.text_widget.delete(1.0, tk.END)
                logger.error(f"加载文件失败: {content}")

        except Exception as e:
            logger.error(f"加载文件内容失败: {e}")
            messagebox.showerror("错误", f"加载文件内容失败:\n{str(e)}")

    def save_file(self):
        """保存文件 - 使用持久连接"""
        try:
            content = self.text_widget.get(1.0, tk.END)

            # 使用持久连接写入文件
            success, message = self.write_func(content)

            if success:
                messagebox.showinfo("成功", "文件保存成功！")
                logger.info("文件保存成功")
            else:
                messagebox.showerror("错误", message)
                logger.error(f"文件保存失败: {message}")

        except Exception as e:
            logger.error(f"保存文件操作失败: {e}")
            messagebox.showerror("错误", f"保存文件失败:\n{str(e)}")