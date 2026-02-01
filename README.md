标定可视化/
├── main.py                 # 主程序入口
├── ssh_manager.py          # SSH连接管理类
├── file_editor.py          # 文件编辑窗口
├── ui.py                   # 主界面UI
├── side_selector.py        # A/B面选择对话框
├── data_path.py            # 路径和密码配置（集中管理）
├── config.json             # 车型SSH配置（包含工作目录）
├── build_exe.py            # 编译脚本
├── requirements.txt        # 依赖包
└── test/                   # 测试目录
    ├── temp.py             # 测试代码
    └── test_params.json    # 测试文件

## 车机直连模式（root@192.168.1.x）

如果需要像 `ssh root@192.168.1.6` 一样直接连车机：
- 在 `config.json` 增加或使用 `connection_type: "direct"` 的车型，例如已有示例 `CAR_HEADUNIT_DIRECT`。
- 默认工作目录调整为 `/opt/usr/app/1/gea/runtime_service/planning_exec/res/conf`，挂载命令使用 `mount -o remount,rw /opt/usr/app/1/gea`。
- 启动程序后，先点击“连接车辆”（直连模式只做车型选择），再选择 A/B 面，程序会直接用配置的 root 账户连接。
- 文件编辑、挂载与保存都会走直连的持久会话。
- 这里是初始版本，保留跳板机连接和直连模式，用以修改标定参数