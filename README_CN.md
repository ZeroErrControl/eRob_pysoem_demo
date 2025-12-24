# pysoem EtherCAT 从站驱动示例 - CST 模式

本项目演示如何使用 `pysoem` 库在 CST（循环同步扭矩）模式下驱动和控制 EtherCAT 从站设备。实现基于 `eRob_CST.cpp`，完全按照 C++ 程序流程。

## ⚠️ 重要警告和限制

### 实时性能限制

**⚠️ 重要提示：本演示程序仅供参考和快速测试使用。开发和生产环境请谨慎使用。**

**已知问题：**
- **实时性能差**：`pysoem` 不提供实时性保证。Python 不是实时系统，该库在用户空间运行，没有实时调度。
- **OP 状态掉线**：在测试案例运行过程中，从站可能会意外地从 OP（操作）状态掉线，原因包括：
  - 周期时间抖动和不稳定
  - Python GIL（全局解释器锁）限制
  - 系统调度延迟
  - 网络栈延迟
- **不适用于工业应用**：此实现**不推荐**用于对可靠性和实时性能要求严格的生产或工业级应用。

### 生产环境推荐方案

如果您需要**工业级** EtherCAT 主站解决方案，请考虑：

1. **IGH EtherCAT Master**（推荐）
   - 支持实时性的 EtherCAT 主站栈
   - 支持实时内核（RT-PREEMPT、Xenomai）
   - 广泛用于工业应用
   - 网站：http://www.etherlab.org/

2. **内核级 EtherCAT 主站**
   - 原生内核驱动程序，实时性能更好
   - 延迟和抖动更低
   - 更适合硬实时要求

3. **商业 EtherCAT 主站解决方案**
   - 专业级 EtherCAT 主站栈
   - 完整的技术支持和文档
   - 针对工业环境优化

### 本演示的适用场景

本演示适用于：
- ✅ 学习和理解 EtherCAT 通信
- ✅ 快速原型设计和测试
- ✅ 开发和调试
- ✅ 对时序要求不严格的非关键应用

**不适用于：**
- ❌ 生产系统
- ❌ 需要实时性保证的工业自动化
- ❌ 安全关键应用
- ❌ 高精度运动控制系统

## 目录

- [安装](#安装)
- [使用方法](#使用方法)
- [配置](#配置)
- [程序流程](#程序流程)
- [主要函数](#主要函数)
- [故障排除](#故障排除)
- [自定义使用](#自定义使用)
- [参考资料](#参考资料)

## 安装

### 系统要求

- Python 3.6 或更高版本
- Linux 操作系统（推荐）或 Windows
- EtherCAT 网络适配器
- Root/管理员权限（访问网络接口需要）

### 安装 pysoem

使用 pip 安装 `pysoem` 库：

```bash
pip install pysoem
```

或使用 conda：

```bash
conda install -c conda-forge pysoem
```

**Linux 注意事项：**
- 可能需要使用 `sudo` 运行 Python 脚本以访问网络接口
- 示例：`sudo python3 pysoem_tset.py`

**Windows 注意事项：**
- 建议安装 Npcap
- 安装过程中选择"在 WinPcap API 兼容模式下安装 Npcap"

### 验证安装

检查 pysoem 是否正确安装：

```bash
python3 -c "import pysoem; print('pysoem version:', pysoem.__version__)"
```

## 使用方法

### 基本使用

1. **运行示例程序**：
   ```bash
   sudo python3 pysoem_tset.py
   ```
   
   或使用 conda 环境：
   ```bash
   sudo /home/zeroerr/anaconda3/bin/python pysoem_tset.py
   ```

2. **程序将自动执行**：
   - 查找可用的网络适配器
   - 选择第一个有效适配器（排除回环接口）
   - 扫描连接的 EtherCAT 从站设备
   - 配置从站并进行数据映射
   - 设置从站进入 OP（操作）状态
   - 执行 CST 模式下的循环数据交换
   - 安全关闭连接

### 程序执行流程

程序遵循以下步骤（匹配 `eRob_CST.cpp`）：

1. **STEP 1**：扫描从站 - 初始化并扫描 EtherCAT 从站设备
2. **STEP 2**：进入 PREOP 状态 - 将从站转换到预操作状态
3. **STEP 3**：配置 PDO 映射 - 为 CST 模式设置 RXPDO (0x1600) 和 TXPDO (0x1A00)
4. **STEP 4**：配置从站和数据映射 - 将过程数据映射到 IO 映射
5. **STEP 5**：进入 SAFEOP 状态 - 配置分布式时钟（DC）并转换到安全操作状态
6. **STEP 6**：启动数据交换线程 - 启动后台线程进行连续数据交换
7. **STEP 8**：进入 OP 状态 - 将从站转换到操作状态
8. **STEP 9**：配置 CST 模式 - 设置操作模式为 CST（循环同步扭矩）
9. **循环操作**：执行带状态机控制的 CST 模式循环数据交换

## 配置

### 周期时间配置

EtherCAT 周期时间可以在 `pysoem_tset.py` 文件顶部配置：

```python
ETHERCAT_CYCLE_TIME_MS = 2.0  # EtherCAT 通讯周期（毫秒），建议 >= 2ms
ETHERCAT_CYCLE_TIME_NS = int(ETHERCAT_CYCLE_TIME_MS * 1_000_000)  # 转换为纳秒（用于 DC Sync0）
```

**重要提示：**
- ⚠️ **Python 不是实时系统**，建议周期时间 >= 2ms
- ⚠️ **即使使用 2ms 周期，仍可能出现 OP 状态掉线**，这是 Python 非实时特性的限制
- 1ms 周期可能导致：
  - Python 调度器无法保证精确的 1ms 周期
  - `time.sleep()` 在 1ms 时精度不足
  - DC 同步可能不稳定
  - 从站可能检测到周期不稳定并拒绝进入 OP
  - **OP 状态掉线的概率更高**
- 如果必须使用 1ms，建议：
  - 使用实时内核（RT 内核）
  - 设置线程优先级
  - 使用更精确的定时器（例如使用 RT 库）
  - **仍可能出现 OP 掉线 - 不保证稳定**

### PDO 配置

程序为 CST 模式配置 PDO：

**RXPDO (0x1600)** - 主站到从站：
- 控制字 (0x6040:0, 16 位)
- 目标扭矩 (0x6071:0, 16 位)
- 操作模式 (0x6060:0, 8 位)
- 填充 (8 位)

**TXPDO (0x1A00)** - 从站到主站：
- 状态字 (0x6041:0, 16 位)
- 实际位置 (0x6064:0, 32 位)
- 实际速度 (0x606C:0, 32 位)
- 实际扭矩 (0x6077:0, 16 位)

### CST 模式参数

默认 CST 模式配置：
- 操作模式：10（CST - 循环同步扭矩）
- 最大扭矩限制：100
- 扭矩斜率：100

这些可以在 `configure_cst_mode()` 函数中修改。

## 程序流程

### 详细步骤说明

1. **查找网络适配器**
   ```python
   adapters = find_adapters()
   ```
   - 扫描可用的网络适配器
   - 过滤掉回环接口

2. **打开适配器**
   ```python
   master = pysoem.Master()
   master.open(adapter.name)
   ```
   - 创建 EtherCAT 主站实例
   - 打开选定的网络适配器

3. **扫描从站（STEP 1）**
   ```python
   master.config_init()  # 扫描从站
   ```
   - 初始化配置并扫描连接的从站

4. **进入 PREOP 状态（STEP 2）**
   ```python
   master.state = pysoem.PREOP_STATE
   master.write_state()
   master.state_check(pysoem.PREOP_STATE, timeout=3 * 50000)
   ```
   - 将从站转换到预操作状态
   - PDO 映射配置需要此状态

5. **配置 PDO 映射（STEP 3）**
   - 配置 RXPDO (0x1600) 和 TXPDO (0x1A00)
   - 设置 PDO 分配（0x1C12, 0x1C13）
   - 必须在 PREOP 状态下完成

6. **配置从站（STEP 4）**
   ```python
   master.manual_state_change = True
   master.config_map()  # 配置过程数据映射
   ```
   - 将 PDO 映射到 IO 映射
   - 设置手动状态转换模式

7. **进入 SAFEOP 状态（STEP 5）**
   ```python
   master.config_dc()  # 配置分布式时钟
   slave.dc_sync(act=True, sync0_cycle_time=ETHERCAT_CYCLE_TIME_NS, sync0_shift_time=0)
   master.state = pysoem.SAFEOP_STATE
   master.write_state()
   ```
   - 配置分布式时钟（DC）
   - 为每个从站设置 DC Sync0
   - 转换到安全操作状态

8. **启动数据交换线程（STEP 6）**
   - 启动后台线程进行连续数据交换
   - 线程必须持续运行以发送周期性输出 PDO
   - 从站进入 OP 状态需要此条件

9. **进入 OP 状态（STEP 8）**
   ```python
   slave.state = pysoem.OP_STATE
   master.write_state()
   master.state_check(pysoem.OP_STATE, timeout=5 * 50000)
   ```
   - 将从站转换到操作状态
   - 数据交换线程必须正在运行

10. **配置 CST 模式（STEP 9）**
    - 设置操作模式为 CST (10)
    - 配置扭矩限制和斜率
    - 验证模式配置

11. **循环操作**
    - 执行电机控制状态机：
      - 0x0080：故障复位
      - 0x0006：关闭
      - 0x0007：开启
      - 0x000F：使能操作
    - 持续发送目标扭矩并接收状态

## 主要函数

### 核心函数

- `find_adapters()`：查找可用的网络适配器
- `scan_slaves(master)`：扫描并显示所有从站设备
- `enter_preop_state(master)`：将从站转换到 PREOP 状态
- `configure_pdo_mapping(master)`：为 CST 模式配置 PDO 映射
- `configure_slaves(master)`：配置从站并执行数据映射
- `enter_safeop_state(master)`：配置 DC 并进入 SAFEOP 状态
- `start_data_exchange_thread(master)`：启动后台数据交换线程
- `set_slaves_to_op_state_cst(master)`：将从站转换到 OP 状态
- `configure_cst_mode(master)`：配置 CST 模式参数
- `cyclic_operation_cst(master, duration=300)`：执行 CST 模式循环操作

### 工具函数

- `get_state_name(state_code)`：将状态码转换为可读名称
- `check_slave_al_status(slave)`：检查从站 AL 状态寄存器
- `print_slave_state_machine_info(master, slave_index)`：打印详细的状态机信息
- `check_slave_states(master, show_all=False)`：检查并显示所有从站状态
- `check_permissions()`：检查 root 权限

## 故障排除

### ⚠️ OP 状态掉线（预期行为）

**如果从站在运行过程中从 OP 状态掉线，这是 pysoem 实时性限制导致的预期行为。**

**为什么会发生：**
- Python 的非实时调度导致周期时间抖动
- 系统负载可能延迟数据交换周期
- 用户空间网络栈延迟
- Python GIL 可能阻塞线程

**预期情况：**
- 从站可能周期性地从 OP 掉到 SAFEOP 或 PREOP
- WKC（工作计数器）可能显示超时
- 状态检查可能显示不一致的状态

**这对本演示来说是正常的，表明用户空间 EtherCAT 实现的限制。**

### 常见问题

1. **"ModuleNotFoundError: No module named 'pysoem'"**
   - **解决方案**：使用 `pip install pysoem` 安装 pysoem 或使用 conda 环境
   - 如果使用 conda，确保使用正确的 Python 解释器

2. **"ConnectionError: could not open interface"**
   - **解决方案**：使用 `sudo`（Linux）或管理员权限（Windows）运行
   - 检查网络接口是否可用：`ip link show`（Linux）或 `ipconfig`（Windows）
   - 确保没有其他程序正在使用网络接口

3. **"未找到 EtherCAT 从站"**
   - **解决方案**：
     - 检查 EtherCAT 线缆连接
     - 确保从站设备已上电
     - 验证网络适配器已连接到 EtherCAT 网络
     - 检查从站是否正确配置

4. **从站无法进入 OP 状态或从 OP 掉线**
   - **可能原因**：
     - 数据交换线程未运行或不稳定
     - PDO 映射不正确
     - DC 未正确配置（检查 0x1C32:0x01 应为 2）
     - 周期时间太短（尝试 2ms 或 4ms）
     - SM2/SM3（同步管理器）状态异常
     - **⚠️ Python 的非实时特性导致周期抖动（预期限制）**
   - **解决方案**：
     - 确保数据交换线程持续运行
     - 验证 PDO 映射与从站 ESI 文件匹配
     - 检查 DC 配置（0x1C32:0x01 = 2）
     - 将周期时间增加到 2ms 或 4ms（或甚至 5ms 以提高稳定性）
     - 检查 AL 状态码以查找特定错误
     - **注意：仍可能出现 OP 掉线 - 这是 pysoem 的限制**

5. **WKC = -1（超时）**
   - **可能原因**：
     - 网络问题
     - 周期时间太短
     - 接收超时太短
   - **解决方案**：
     - 检查网络线缆和连接
     - 增加周期时间
     - 增加 `receive_processdata(timeout=5000)` 中的接收超时

6. **电机无法使能**
   - **可能原因**：
     - 控制字序列不正确
     - 故障未清除
     - 操作模式未正确设置
     - 状态字显示故障或开关禁用
   - **解决方案**：
     - 验证控制字序列：0x0080 → 0x0006 → 0x0007 → 0x000F
     - 检查状态字 (0x6041) 的故障位
     - 验证操作模式 (0x6060) 设置为 10（CST）
     - 检查错误代码 (0x603F) 以查找特定错误

### 调试技巧

1. **启用详细日志**：程序已包含详细的状态信息打印
2. **检查 AL 状态码**：使用 `check_slave_al_status()` 诊断从站错误
3. **监控状态字**：检查状态字 (0x6041) 位以了解电机状态
4. **验证 PDO 数据**：检查循环操作输出中的发送/接收 PDO 数据
5. **检查 DC 配置**：验证 0x1C32:0x01 = 2 以确保 DC 成功激活

## 自定义使用

### 修改周期时间

编辑 `pysoem_tset.py` 文件顶部的全局变量：

```python
ETHERCAT_CYCLE_TIME_MS = 2.0  # 更改为所需的周期时间（毫秒）
```

### 修改 CST 模式参数

编辑 `configure_cst_mode()` 函数：

```python
operation_mode = 10  # CST 模式
max_torque = 100     # 最大扭矩限制
torque_slope = 100   # 扭矩斜率
```

### 修改目标扭矩

编辑 `cyclic_operation_cst()` 函数：

```python
_thread_target_torque = 50  # 设置目标扭矩值
```

### 添加自定义数据处理

修改 `cyclic_operation_cst()` 函数以添加处理输入/输出数据的自定义逻辑：

```python
# 读取从站输入数据
statusword = int.from_bytes(master.slaves[0].input[0:2], 'little')
actual_position = int.from_bytes(master.slaves[0].input[2:6], 'little', signed=True)
actual_velocity = int.from_bytes(master.slaves[0].input[6:10], 'little', signed=True)
actual_torque = int.from_bytes(master.slaves[0].input[10:12], 'little', signed=True)

# 在此处添加您的自定义处理逻辑
```

### 选择特定适配器

修改 `main()` 函数以选择特定适配器：

```python
# 不选择 adapters[0]，而是按名称或索引选择
selected_adapter = None
for adapter in adapters:
    if adapter.name == 'enp58s0':  # 您的适配器名称
        selected_adapter = adapter
        break
```

## 从站状态说明

- **INIT**：初始化状态 - 上电后的初始状态
- **PREOP**：预操作状态 - 可以在此状态下配置 PDO 映射
- **SAFEOP**：安全操作状态 - 可以交换过程数据，但输出被禁用
- **OP**：操作状态 - 完全启用过程数据交换，可以控制电机

## 状态机（CiA 402）

程序实现 CiA 402 状态机用于电机控制：

1. **故障复位 (0x0080)**：清除任何现有故障
2. **关闭 (0x0006)**：准备电机运行
3. **开启 (0x0007)**：使能电机电源
4. **使能操作 (0x000F)**：使能电机操作，准备进行扭矩控制

## 参考资料

- [pysoem PyPI 页面](https://pypi.org/project/pysoem/)
- [EtherCAT 技术组织](https://www.ethercat.org/)
- [CiA 402 - CANopen 驱动器和运动控制设备配置文件](https://www.can-cia.org/can-knowledge/canopen/cia402/)
- 参考 C++ 实现：`eRob_CST.cpp`

## 免责声明

**本软件按"原样"提供，不提供任何形式的保证。作者和贡献者不对使用本软件造成的任何损害或损失负责。**

**对于生产或工业应用，请使用专业级 EtherCAT 主站解决方案，如 IGH EtherCAT Master 或内核级实现。**

