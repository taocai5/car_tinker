import paramiko
import json
import os
import sys
import logging
import time
from tkinter import messagebox, simpledialog
from data_path import (
    SSH_CONFIG,
    FILE_PATHS,
    SIDE_CONFIG,
    MOUNT_CONFIG,
    get_full_file_path,
    get_full_adas_file_path,
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SSHManager:
    def __init__(self):
        self.ssh_client = None
        self.side_ssh_client = None
        self.side_channel = None
        self.connected = False
        self.side_connected = False
        self.direct_mode = False  # 是否处于车机直连模式
        self.current_host = None
        self.current_car_name = None
        self.current_side = None
        self.current_side_ip = None
        self.current_side_username = None
        self.current_working_directory = FILE_PATHS['default_working_directory']

    # ========= 基础工具 =========
    def _new_ssh_client(self):
        """创建配置好的SSHClient"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    def _connect_with_password(self, client, host, port, username, password, sock=None):
        """统一的SSH连接封装，便于直连/隧道复用"""
        connect_kwargs = {
            'hostname': host,
            'port': port,
            'username': username,
            'timeout': SSH_CONFIG.get('timeout', 10),
            'auth_timeout': SSH_CONFIG.get('auth_timeout', 15),
            'banner_timeout': SSH_CONFIG.get('banner_timeout', 15),
            'allow_agent': False,
            'look_for_keys': False,
        }
        if password:
            connect_kwargs['password'] = password
        if sock:
            connect_kwargs['sock'] = sock

        client.connect(**connect_kwargs)
        return client

    # ========= 远端文件工具 =========
    def _remote_file_exists(self, file_path):
        """检查远端文件是否存在"""
        try:
            cmd = f"test -f '{file_path}' && echo OK || echo NO"
            success, result = self.execute_side_command_persistent(cmd)
            if success and "OK" in result:
                return True
            return False
        except Exception:
            return False

    def _resolve_with_fallback(self, primary_path):
        """
        读取/写入时的路径选择：
        - 优先 primary（默认 planning_exec）
        - 若 primary 不存在且 secondary 存在（control_exec），则使用 secondary
        - 若两者都存在，仍用 primary
        """
        try:
            secondary_path = primary_path.replace("/planning_exec/", "/control_exec/")

            primary_exists = self._remote_file_exists(primary_path)
            secondary_exists = False
            if not primary_exists:
                secondary_exists = self._remote_file_exists(secondary_path)

            if primary_exists:
                chosen = primary_path
            elif secondary_exists:
                chosen = secondary_path
            else:
                chosen = primary_path  # 都不存在则落回默认路径，后续写入会创建

            if chosen != primary_path:
                logger.info(f"文件不存在于默认路径，使用备选路径: {chosen}")
            return chosen
        except Exception as e:
            logger.error(f"路径回退选择失败，使用默认路径: {e}")
            return primary_path

    def mount_filesystem(self):
        """挂载文件系统为可写"""
        try:
            # 统一使用配置中的挂载命令（车机环境默认 remount,rw）
            mount_command = MOUNT_CONFIG.get('mount_command', "mount -o remount,rw /opt/usr/app/1/gea")
            logger.info(f"执行挂载命令: {mount_command}")
            success, result = self.execute_side_command_persistent(mount_command)

            if success:
                logger.info("文件系统挂载成功")
                return True, "文件系统挂载成功"
            else:
                error_msg = f"文件系统挂载失败: {result}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"挂载文件系统失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def set_working_directory(self, working_directory):
        """设置工作目录"""
        try:
            if working_directory:
                self.current_working_directory = working_directory
            else:
                self.current_working_directory = FILE_PATHS['default_working_directory']
            logger.info(f"设置工作目录: {self.current_working_directory}")
        except Exception as e:
            logger.error(f"设置工作目录失败: {e}")
            self.current_working_directory = FILE_PATHS['default_working_directory']

    def parse_ssh_command(self, ssh_command):
        """解析SSH命令格式：支持多种格式"""
        try:
            # 移除开头的'ssh '如果存在
            if ssh_command.startswith('ssh '):
                ssh_command = ssh_command[4:].strip()

            logger.info(f"原始SSH命令: {ssh_command}")

            # 对于 ifly@ifly.bestunee54100155@172.30.32.222 这种格式
            if ssh_command.count('@') >= 2:
                # 找到最后一个@的位置
                last_at_index = ssh_command.rfind('@')
                username = ssh_command[:last_at_index]  # ifly@ifly.bestunee54100155
                host = ssh_command[last_at_index + 1:]  # 172.30.32.222
                logger.info(f"跳板机格式解析: 用户名={username}, 主机={host}")
            elif '@' in ssh_command:
                # 标准格式：username@host
                parts = ssh_command.split('@')
                username = parts[0]
                host = parts[1]
                logger.info(f"标准格式解析: 用户名={username}, 主机={host}")
            else:
                # 直接是主机名或IP
                host = ssh_command
                username = SSH_CONFIG['default_username']
                logger.info(f"直接格式解析: 用户名={username}, 主机={host}")

            # 验证主机格式
            if not host or len(host) < 3:
                logger.error(f"主机格式无效: {host}")
                return None, None

            logger.info(f"最终解析结果: 主机={host}, 用户名={username}")
            return host, username

        except Exception as e:
            logger.error(f"解析SSH命令失败: {e}")
            return None, None

    def _test_connection(self, ssh_client):
        """测试连接是否真正有效"""
        try:
            stdin, stdout, stderr = ssh_client.exec_command('echo "connection_test"', timeout=5)
            output = stdout.read().decode('utf-8').strip()
            return output == "connection_test"
        except:
            return False

    def connect_to_vehicle(self, car_name, ssh_command, port=SSH_CONFIG['default_port'], working_directory=None):
        """连接到车辆（跳板机）"""
        try:
            # 进入跳板机模式
            self.direct_mode = False

            # 设置工作目录
            self.set_working_directory(working_directory)

            # 解析SSH命令
            host, username = self.parse_ssh_command(ssh_command)

            if not host:
                return False, "SSH命令格式错误"

            logger.info(f"开始连接: {username}@{host}:{port}")

            self.ssh_client = self._new_ssh_client()

            # 优先尝试默认密码，失败后提示用户输入
            default_password = SSH_CONFIG.get('default_password', 'auto')

            def try_once(pwd):
                self._connect_with_password(self.ssh_client, host, port, username, pwd)
                if not self._test_connection(self.ssh_client):
                    raise Exception("连接测试失败")

            try:
                logger.info(f"第一步: 尝试使用默认密码 '{default_password}' 连接")
                try_once(default_password)
                logger.info("✓ 使用默认密码连接成功")
            except paramiko.AuthenticationException:
                logger.warning("默认密码认证失败，请求用户输入密码")
                try:
                    password = simpledialog.askstring(
                        "密码输入",
                        f"默认密码认证失败\n请输入 {username}@{host} 的密码:",
                        show='*'
                    )
                    if not password:
                        return False, "用户取消输入密码"

                    logger.info("第二步: 尝试使用用户输入密码连接")
                    try_once(password)
                    logger.info("✓ 使用用户输入密码连接成功")
                except paramiko.AuthenticationException as user_auth_error:
                    error_msg = f"密码认证失败: {str(user_auth_error)}"
                    logger.error(error_msg)
                    return False, error_msg
                except Exception as user_connect_error:
                    error_msg = f"连接失败: {str(user_connect_error)}"
                    logger.error(error_msg)
                    return False, user_connect_error
            except Exception as connect_error:
                error_msg = f"连接失败: {str(connect_error)}"
                logger.error(error_msg)
                return False, error_msg

            self.connected = True
            self.current_host = host
            self.current_car_name = car_name

            logger.info(f"✓ 成功连接到车辆 {car_name} ({username}@{host})")
            return True, f"成功连接到车辆 {car_name} ({username}@{host})"

        except Exception as e:
            error_msg = f"连接错误: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def prepare_direct_vehicle(self, car_name, working_directory=None):
        """准备直连车机模式（不经过跳板机）"""
        try:
            self.disconnect()  # 清理旧连接
            self.direct_mode = True
            self.connected = True  # 视为已选择车辆，等待侧连
            self.current_car_name = car_name
            self.set_working_directory(working_directory)
            logger.info(f"启用直连模式，车辆: {car_name}，工作目录: {self.current_working_directory}")
            return True, f"已选择车辆 {car_name}（直连模式）"
        except Exception as e:
            error_msg = f"直连模式初始化失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def connect_to_side_direct(self, side, ip, username=None, password=None, port=SSH_CONFIG['default_port']):
        """直接连接到A/B面（车机环境，无跳板机）"""
        try:
            if not self.direct_mode:
                return False, "当前配置不是直连模式"

            # 使用配置或默认的用户名密码
            username = username or SIDE_CONFIG.get(f'{side.lower()}_side_username', 'root')
            password = password or SIDE_CONFIG.get(f'{side.lower()}_side_password', None)

            logger.info(f"直连{side}面: {username}@{ip}:{port}")

            # 关闭旧的侧连接
            if self.side_ssh_client:
                self.side_ssh_client.close()

            self.side_ssh_client = self._new_ssh_client()
            self._connect_with_password(self.side_ssh_client, ip, port, username, password)

            self.current_side = side
            self.current_side_ip = ip
            self.current_side_username = username
            self.current_host = ip
            self.side_connected = True

            logger.info(f"✓ 直连{side}面成功: {username}@{ip}")
            return True, f"成功直连{side}面 ({username}@{ip})"

        except Exception as e:
            error_msg = f"直连{side}面失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def connect_headunit_direct(self, car_name, side, ip, username=None, password=None,
                                port=SSH_CONFIG['default_port'], working_directory=None):
        """
        一步完成车机直连（等价于 ssh root@192.168.1.x）
        - 设置直连模式
        - 直接连到指定面（默认A面）
        """
        try:
            self.disconnect()  # 清理旧连接
            self.direct_mode = True
            self.connected = True
            self.current_car_name = car_name
            self.set_working_directory(working_directory)

            # 直接连指定面
            return self.connect_to_side_direct(side, ip, username, password, port)
        except Exception as e:
            error_msg = f"直连车机失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def connect_to_side_tunnel(self, side, ip, username=None, password=None, port=SSH_CONFIG['default_port']):
        """使用SSH隧道连接到A/B面"""
        try:
            if not self.connected:
                return False, "请先连接到车辆"

            # 设置默认用户名
            if not username:
                username = SIDE_CONFIG[f'{side.lower()}_side_username']

            logger.info(f"通过SSH隧道连接{side}面: {username}@{ip}")

            # 在跳板机上建立到A/B面的SSH隧道
            transport = self.ssh_client.get_transport()

            # 创建到目标主机的通道
            self.side_channel = transport.open_channel(
                'direct-tcpip',
                (ip, port),
                ('', 0)
            )

            # 创建新的SSH客户端用于A/B面连接
            self.side_ssh_client = self._new_ssh_client()

            try:
                # 通过隧道连接A/B面，先尝试默认密码
                side_password = SIDE_CONFIG.get(f'{side.lower()}_side_password', "Huawei12#$")
                self._connect_with_password(self.side_ssh_client, ip, port, username, side_password, sock=self.side_channel)
                logger.info(f"✓ 使用SSH隧道成功连接到{side}面")

            except paramiko.AuthenticationException:
                # 如果默认密码失败，请求用户输入密码
                logger.warning(f"默认密码连接{side}面失败，请求用户输入密码")
                try:
                    user_password = simpledialog.askstring(
                        "密码输入",
                        f"默认密码连接{side}面失败\n请输入 {side}面 ({username}@{ip}) 的密码:",
                        show='*'
                    )
                    if not user_password:
                        return False, "用户取消输入密码"

                    # 使用用户输入的密码重新连接
                    self._connect_with_password(self.side_ssh_client, ip, port, username, user_password, sock=self.side_channel)
                    logger.info(f"✓ 使用用户输入密码成功连接到{side}面")

                except Exception as user_connect_error:
                    error_msg = f"用户密码连接{side}面失败: {str(user_connect_error)}"
                    logger.error(error_msg)
                    return False, error_msg

            self.current_side = side
            self.current_side_ip = ip
            self.current_side_username = username
            self.side_connected = True

            return True, f"成功连接到{side}面 ({username}@{ip})"

        except Exception as e:
            error_msg = f"SSH隧道连接{side}面异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def execute_side_command_persistent(self, command):
        """在持久连接的A/B面上执行命令"""
        try:
            if not self.side_connected or not self.side_ssh_client:
                return False, "A/B面持久连接未建立"

            stdin, stdout, stderr = self.side_ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')

            if error and "Permission denied" not in error:
                logger.warning(f"A/B面命令执行有错误输出: {error}")
                return False, error

            logger.info(f"A/B面命令执行成功: {command}")
            return True, output

        except Exception as e:
            error_msg = f"A/B面命令执行错误: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def read_params_file_persistent(self):
        """使用持久连接读取文件"""
        try:
            logger.info("开始读取文件...")

            # 挂载文件系统
            mount_command = "mount -o rw,remount /opt/usr/app/1/gea"
            logger.info(f"执行挂载命令: {mount_command}")
            mount_success, mount_result = self.execute_side_command_persistent(mount_command)

            if mount_success:
                logger.info("文件系统挂载成功")
            else:
                logger.warning(f"文件系统挂载失败: {mount_result}")

            # 读取文件内容
            file_path = get_full_file_path(self.current_working_directory)
            read_command = f"cat {file_path}"
            logger.info(f"执行命令: {read_command}")
            read_success, read_result = self.execute_side_command_persistent(read_command)

            if read_success:
                # 清理SSH警告信息
                cleaned_content = self._clean_ssh_warnings(read_result)
                logger.info(f"成功读取文件，内容长度: {len(cleaned_content)}")
                return True, cleaned_content
            else:
                error_msg = f"读取文件失败: {read_result}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"读取文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _clean_ssh_warnings(self, content):
        """清理SSH警告信息 - 精确识别JSON边界"""
        try:
            if not content:
                return content

            logger.info(f"原始内容长度: {len(content)}")

            # 方法1: 直接定位JSON对象
            json_start = content.find('{')
            json_end = content.rfind('}')

            if json_start != -1 and json_end != -1 and json_end > json_start:
                # 提取完整的JSON对象
                json_content = content[json_start:json_end + 1]

                # 验证JSON格式
                try:
                    parsed_json = json.loads(json_content)
                    logger.info("成功提取并验证JSON内容")
                    return json_content
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON验证失败: {e}")

            # 方法2: 按行处理，精确识别SSH警告
            lines = content.split('\n')
            cleaned_lines = []

            # 精确的SSH警告模式
            ssh_warnings = [
                "Warning: Permanently added",
                "Authorized users only. All activities may be monitored and recorded.",
                "Last login:",
                "Welcome to"
            ]

            for line in lines:
                line_stripped = line.strip()
                is_ssh_warning = False

                # 精确匹配SSH警告
                for warning in ssh_warnings:
                    if warning in line_stripped:
                        is_ssh_warning = True
                        break

                if not is_ssh_warning:
                    cleaned_lines.append(line)

            cleaned_content = '\n'.join(cleaned_lines).strip()

            # 最终验证
            if cleaned_content and cleaned_content.endswith('}'):
                try:
                    json.loads(cleaned_content)
                    logger.info("最终清理成功")
                    return cleaned_content
                except json.JSONDecodeError:
                    pass

            logger.warning("所有清理方法都失败，返回原始内容")
            return content

        except Exception as e:
            logger.error(f"清理SSH警告失败: {e}")
            return content

    def check_file_exists(self):
        """检查params.json文件是否存在 - 修复路径问题"""
        try:
            logger.info("检查文件是否存在...")

            # 使用单个命令来检查文件
            primary_path = get_full_file_path(self.current_working_directory)
            file_path = self._resolve_with_fallback(primary_path)
            logger.info(f"检查文件路径: {file_path}")

            test_command = f"test -f '{file_path}' && echo 'FILE_EXISTS' || echo 'FILE_NOT_FOUND'"
            test_success, test_result = self.execute_side_command_persistent(test_command)

            if test_success and "FILE_EXISTS" in test_result:
                logger.info("文件存在")
                return True, f"文件存在: {file_path}"
            else:
                error_msg = f"文件不存在: {file_path}"
                logger.warning(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"检查文件存在失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def read_params_file_persistent(self):
        """使用持久连接读取文件 - 修复路径问题"""
        try:
            logger.info("开始读取文件...")

            # 挂载文件系统
            mount_command = MOUNT_CONFIG.get('mount_command', "mount -o remount,rw /opt/usr/app/1/gea")
            logger.info(f"执行挂载命令: {mount_command}")
            mount_success, mount_result = self.execute_side_command_persistent(mount_command)

            if mount_success:
                logger.info("文件系统挂载成功")
            else:
                logger.warning(f"文件系统挂载失败: {mount_result}")

            # 读取文件内容
            primary_path = get_full_file_path(self.current_working_directory)
            file_path = self._resolve_with_fallback(primary_path)
            logger.info(f"读取文件路径: {file_path}")

            read_command = f"cat '{file_path}'"  # 添加引号处理路径
            logger.info(f"执行命令: {read_command}")
            read_success, read_result = self.execute_side_command_persistent(read_command)

            if read_success:
                # 清理SSH警告信息
                cleaned_content = self._clean_ssh_warnings(read_result)
                logger.info(f"成功读取文件，内容长度: {len(cleaned_content)}")
                return True, cleaned_content
            else:
                error_msg = f"读取文件失败: {read_result}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"读取文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def read_adas_file_persistent(self):
        """读取 adas_params.json"""
        try:
            logger.info("开始读取ADAS文件...")

            mount_command = MOUNT_CONFIG.get('mount_command', "mount -o remount,rw /opt/usr/app/1/gea")
            logger.info(f"执行挂载命令: {mount_command}")
            self.execute_side_command_persistent(mount_command)

            primary_path = get_full_adas_file_path(self.current_working_directory)
            file_path = self._resolve_with_fallback(primary_path)
            logger.info(f"读取文件路径: {file_path}")
            read_command = f"cat '{file_path}'"
            read_success, read_result = self.execute_side_command_persistent(read_command)

            if read_success:
                cleaned_content = self._clean_ssh_warnings(read_result)
                logger.info(f"成功读取ADAS文件，内容长度: {len(cleaned_content)}")
                return True, cleaned_content
            else:
                error_msg = f"读取ADAS文件失败: {read_result}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"读取ADAS文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def write_params_file_persistent(self, content):
        """使用持久连接写入文件 - 修复路径问题"""
        try:
            logger.info("开始保存文件...")
            logger.info(f"内容长度: {len(content)} 字符")

            # 验证JSON格式
            try:
                json.loads(content)
                logger.info("JSON格式验证通过")
            except json.JSONDecodeError as e:
                error_msg = f"JSON格式错误: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

            primary_path = get_full_file_path(self.current_working_directory)
            file_path = self._resolve_with_fallback(primary_path)
            logger.info(f"目标文件路径: {file_path}")

            # 挂载文件系统
            mount_command = MOUNT_CONFIG.get('mount_command', "mount -o remount,rw /opt/usr/app/1/gea")
            logger.info(f"执行挂载命令: {mount_command}")
            mount_success, mount_result = self.execute_side_command_persistent(mount_command)

            if not mount_success:
                error_msg = f"文件系统挂载失败: {mount_result}"
                logger.error(error_msg)
                return False, error_msg

            # 使用base64写入
            temp_file = f"/tmp/params_temp_{int(time.time())}.json"
            import base64
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')

            write_command = f"echo '{encoded_content}' | base64 -d > '{temp_file}' && chmod 644 '{temp_file}' && mv '{temp_file}' '{file_path}' && sync"
            logger.info(f"执行写入命令")
            write_success, write_result = self.execute_side_command_persistent(write_command)

            if write_success:
                # 验证写入结果
                verify_command = f"cat '{file_path}' | wc -c"
                verify_success, verify_result = self.execute_side_command_persistent(verify_command)

                if verify_success:
                    try:
                        file_size = int(verify_result.strip())
                        if file_size == len(content):
                            logger.info("✓ 文件写入验证成功")
                            return True, "文件保存成功"
                        else:
                            logger.warning(f"文件大小不匹配: 期望{len(content)}，实际{file_size}")
                    except:
                        pass

                return True, "文件保存成功"
            else:
                error_msg = f"文件写入失败: {write_result}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"写入文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def write_adas_file_persistent(self, content):
        """写入 adas_params.json"""
        try:
            logger.info("开始保存ADAS文件...")
            logger.info(f"内容长度: {len(content)} 字符")

            try:
                json.loads(content)
                logger.info("ADAS JSON格式验证通过")
            except json.JSONDecodeError as e:
                error_msg = f"ADAS JSON格式错误: {str(e)}"
                logger.error(error_msg)
                return False, error_msg

            primary_path = get_full_adas_file_path(self.current_working_directory)
            file_path = self._resolve_with_fallback(primary_path)
            logger.info(f"目标文件路径: {file_path}")

            mount_command = MOUNT_CONFIG.get('mount_command', "mount -o remount,rw /opt/usr/app/1/gea")
            logger.info(f"执行挂载命令: {mount_command}")
            mount_success, mount_result = self.execute_side_command_persistent(mount_command)

            if not mount_success:
                error_msg = f"文件系统挂载失败: {mount_result}"
                logger.error(error_msg)
                return False, error_msg

            temp_file = f"/tmp/adas_params_temp_{int(time.time())}.json"
            import base64
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')

            write_command = (
                f"echo '{encoded_content}' | base64 -d > '{temp_file}' && "
                f"chmod 644 '{temp_file}' && mv '{temp_file}' '{file_path}' && sync"
            )
            logger.info("执行写入命令")
            write_success, write_result = self.execute_side_command_persistent(write_command)

            if write_success:
                verify_command = f"cat '{file_path}' | wc -c"
                verify_success, verify_result = self.execute_side_command_persistent(verify_command)
                if verify_success:
                    try:
                        file_size = int(verify_result.strip())
                        if file_size == len(content):
                            logger.info("✓ ADAS文件写入验证成功")
                            return True, "文件保存成功"
                        else:
                            logger.warning(f"ADAS文件大小不匹配: 期望{len(content)}，实际{file_size}")
                    except:
                        pass
                return True, "文件保存成功"
            else:
                error_msg = f"文件写入失败: {write_result}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"写入ADAS文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def execute_command(self, command):
        """执行SSH命令"""
        try:
            # 真实命令执行
            if not self.connected:
                return False, "未连接到SSH服务器"

            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')

            if error and "Permission denied" not in error:
                logger.warning(f"命令执行有错误输出: {error}")
                return False, error

            logger.info(f"命令执行成功: {command}")
            return True, output

        except Exception as e:
            error_msg = f"命令执行错误: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def debug_connection(self):
        """调试连接状态"""
        try:
            logger.info("=== 连接状态调试 ===")
            logger.info(f"连接到车辆: {self.connected}")
            logger.info(f"当前车型: {self.current_car_name}")
            logger.info(f"当前主机: {self.current_host}")
            logger.info(f"当前面: {self.current_side}")
            logger.info(f"A/B面IP: {self.current_side_ip}")
            logger.info(f"A/B面用户名: {self.current_side_username}")
            logger.info(f"工作目录: {self.current_working_directory}")

            # 测试跳板机连接
            if self.connected:
                logger.info("测试跳板机连接...")
                success, result = self.execute_command("pwd && whoami")
                if success:
                    logger.info(f"跳板机连接正常: {result}")
                else:
                    logger.error(f"跳板机连接异常: {result}")

            # 测试A/B面连接
            if self.side_connected:
                logger.info(f"测试{self.current_side}面连接...")
                success, result = self.execute_side_command_persistent("pwd && whoami && ls -la")
                if success:
                    logger.info(f"{self.current_side}面连接正常: {result}")
                else:
                    logger.error(f"{self.current_side}面连接异常: {result}")

            logger.info("=== 调试结束 ===")
            return True

        except Exception as e:
            logger.error(f"调试连接状态失败: {e}")
            return False

    def disconnect(self):
        """断开SSH连接"""
        try:
            if self.side_ssh_client:
                self.side_ssh_client.close()
                self.side_connected = False

            if self.ssh_client:
                self.ssh_client.close()

            self.connected = False
            self.direct_mode = False
            self.current_host = None
            self.current_car_name = None
            self.current_side = None
            self.current_side_ip = None
            self.current_side_username = None
            self.current_working_directory = FILE_PATHS['default_working_directory']
            logger.info("SSH连接已断开")
        except Exception as e:
            logger.error(f"断开SSH连接失败: {e}")

    def is_connected(self):
        """检查是否已连接到车辆"""
        return self.connected

    def is_side_connected(self):
        """检查是否已连接到A/B面"""
        return self.side_connected

    def is_direct_mode(self):
        """是否处于车机直连模式"""
        return self.direct_mode

    def get_current_car_name(self):
        """获取当前连接的车型名称"""
        return self.current_car_name

    def get_current_side(self):
        """获取当前连接的面"""
        return self.current_side

    def get_current_working_directory(self):
        """获取当前工作目录"""
        return self.current_working_directory