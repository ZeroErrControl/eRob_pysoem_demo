# pysoem EtherCAT Slave Driver Example - CST Mode

This project demonstrates how to use the `pysoem` library to drive and control EtherCAT slave devices in CST (Cyclic Synchronous Torque) mode. The implementation is based on `eRob_CST.cpp` and follows the C++ program flow exactly.

## ⚠️ Important Warnings and Limitations

### Real-time Performance Limitations

**⚠️ CRITICAL: This demo is for reference and quick testing purposes only. Use with caution for development and production.**

**Known Issues:**
- **Poor Real-time Performance**: `pysoem` does not provide real-time guarantees. Python is not a real-time system, and the library runs in user space without real-time scheduling.
- **OP State Drops**: During test case execution, slaves may drop from OP (Operational) state unexpectedly due to:
  - Cycle time jitter and instability
  - Python GIL (Global Interpreter Lock) limitations
  - System scheduling delays
  - Network stack delays
- **Not Suitable for Industrial Applications**: This implementation is **NOT recommended** for production or industrial-grade applications where reliability and real-time performance are critical.

### Recommendations for Production Use

If you need **industrial-grade** EtherCAT master solutions, consider:

1. **IGH EtherCAT Master** (Recommended)
   - Real-time capable EtherCAT master stack
   - Supports real-time kernels (RT-PREEMPT, Xenomai)
   - Widely used in industrial applications
   - Website: http://www.etherlab.org/

2. **Kernel-level EtherCAT Master**
   - Native kernel drivers for better real-time performance
   - Lower latency and jitter
   - Better suited for hard real-time requirements

3. **Commercial EtherCAT Master Solutions**
   - Professional-grade EtherCAT master stacks
   - Full support and documentation
   - Optimized for industrial environments

### Use Cases for This Demo

This demo is suitable for:
- ✅ Learning and understanding EtherCAT communication
- ✅ Quick prototyping and testing
- ✅ Development and debugging
- ✅ Non-critical applications with relaxed timing requirements

**NOT suitable for:**
- ❌ Production systems
- ❌ Industrial automation requiring real-time guarantees
- ❌ Safety-critical applications
- ❌ High-precision motion control systems

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Program Flow](#program-flow)
- [Main Functions](#main-functions)
- [Troubleshooting](#troubleshooting)
- [Customization](#customization)
- [References](#references)

## Installation

### Prerequisites

- Python 3.6 or higher
- Linux operating system (recommended) or Windows
- EtherCAT network adapter
- Root/Administrator privileges (required for network interface access)

### Install pysoem

Install the `pysoem` library using pip:

```bash
pip install pysoem
```

Or if using conda:

```bash
conda install -c conda-forge pysoem
```

**Note for Linux:**
- You may need to run Python scripts with `sudo` to access network interfaces
- Example: `sudo python3 pysoem_tset.py`

**Note for Windows:**
- It is recommended to install Npcap
- During installation, select "Install Npcap in WinPcap API-compatible Mode"

### Verify Installation

Check if pysoem is installed correctly:

```bash
python3 -c "import pysoem; print('pysoem version:', pysoem.__version__)"
```

## Usage

### Basic Usage

1. **Run the example program**:
   ```bash
   sudo python3 pysoem_tset.py
   ```
   
   Or if using conda environment:
   ```bash
   sudo /home/zeroerr/anaconda3/bin/python pysoem_tset.py

   or run ：
   sudo /home/zeroerr/anaconda3/bin/python pysoem_tset.py

   ```

2. **The program will automatically**:
   - Find available network adapters
   - Select the first valid adapter (excluding loopback)
   - Scan for connected EtherCAT slave devices
   - Configure slaves and perform data mapping
   - Set slaves to enter OP (Operational) state
   - Execute cyclic data exchange in CST mode
   - Safely close the connection

### Program Execution Flow

The program follows these steps (matching `eRob_CST.cpp`):

1. **STEP 1**: Scan slaves - Initialize and scan for EtherCAT slave devices
2. **STEP 2**: Enter PREOP state - Transition slaves to Pre-Operational state
3. **STEP 3**: Configure PDO mapping - Set up RXPDO (0x1600) and TXPDO (0x1A00) for CST mode
4. **STEP 4**: Configure slaves and data mapping - Map process data to IO map
5. **STEP 5**: Enter SAFEOP state - Configure Distributed Clock (DC) and transition to Safe Operational state
6. **STEP 6**: Start data exchange thread - Launch background thread for continuous data exchange
7. **STEP 8**: Enter OP state - Transition slaves to Operational state
8. **STEP 9**: Configure CST mode - Set operation mode to CST (Cyclic Synchronous Torque)
9. **Cyclic Operation**: Execute CST mode cyclic data exchange with state machine control

## Configuration

### Cycle Time Configuration

The EtherCAT cycle time can be configured at the top of `pysoem_tset.py`:

```python
ETHERCAT_CYCLE_TIME_MS = 2.0  # EtherCAT communication cycle (milliseconds), recommended >= 2ms
ETHERCAT_CYCLE_TIME_NS = int(ETHERCAT_CYCLE_TIME_MS * 1_000_000)  # Convert to nanoseconds (for DC Sync0)
```

**Important Notes:**
- ⚠️ **Python is not a real-time system**, recommended cycle time >= 2ms
- ⚠️ **Even with 2ms cycle, OP state drops may occur** due to Python's non-real-time nature
- 1ms cycle may cause:
  - Python scheduler cannot guarantee precise 1ms cycle
  - `time.sleep()` precision is insufficient at 1ms
  - DC synchronization may be unstable
  - Slaves may detect cycle instability and refuse to enter OP
  - **Higher probability of OP state drops**
- If 1ms must be used, recommended:
  - Use real-time kernel (RT kernel)
  - Set thread priority
  - Use more precise timers (e.g., using RT library)
  - **Still may experience OP drops - not guaranteed**

### PDO Configuration

The program configures PDOs for CST mode:

**RXPDO (0x1600)** - Master to Slave:
- Control Word (0x6040:0, 16 bits)
- Target Torque (0x6071:0, 16 bits)
- Mode of Operation (0x6060:0, 8 bits)
- Padding (8 bits)

**TXPDO (0x1A00)** - Slave to Master:
- Status Word (0x6041:0, 16 bits)
- Actual Position (0x6064:0, 32 bits)
- Actual Velocity (0x606C:0, 32 bits)
- Actual Torque (0x6077:0, 16 bits)

### CST Mode Parameters

Default CST mode configuration:
- Operation Mode: 10 (CST - Cyclic Synchronous Torque)
- Maximum Torque Limit: 100
- Torque Slope: 100

These can be modified in the `configure_cst_mode()` function.

## Program Flow

### Detailed Step-by-Step Process

1. **Find Network Adapters**
   ```python
   adapters = find_adapters()
   ```
   - Scans for available network adapters
   - Filters out loopback interface

2. **Open Adapter**
   ```python
   master = pysoem.Master()
   master.open(adapter.name)
   ```
   - Creates EtherCAT master instance
   - Opens the selected network adapter

3. **Scan Slaves (STEP 1)**
   ```python
   master.config_init()  # Scan slaves
   ```
   - Initializes configuration and scans for connected slaves

4. **Enter PREOP State (STEP 2)**
   ```python
   master.state = pysoem.PREOP_STATE
   master.write_state()
   master.state_check(pysoem.PREOP_STATE, timeout=3 * 50000)
   ```
   - Transitions slaves to Pre-Operational state
   - Required for PDO mapping configuration

5. **Configure PDO Mapping (STEP 3)**
   - Configures RXPDO (0x1600) and TXPDO (0x1A00)
   - Sets up PDO assignments (0x1C12, 0x1C13)
   - Must be done in PREOP state

6. **Configure Slaves (STEP 4)**
   ```python
   master.manual_state_change = True
   master.config_map()  # Configure process data mapping
   ```
   - Maps PDOs to IO map
   - Sets manual state change mode

7. **Enter SAFEOP State (STEP 5)**
   ```python
   master.config_dc()  # Configure Distributed Clock
   slave.dc_sync(act=True, sync0_cycle_time=ETHERCAT_CYCLE_TIME_NS, sync0_shift_time=0)
   master.state = pysoem.SAFEOP_STATE
   master.write_state()
   ```
   - Configures Distributed Clock (DC)
   - Sets DC Sync0 for each slave
   - Transitions to Safe Operational state

8. **Start Data Exchange Thread (STEP 6)**
   - Launches background thread for continuous data exchange
   - Thread must run continuously to send periodic Output PDOs
   - Required for slaves to enter OP state

9. **Enter OP State (STEP 8)**
   ```python
   slave.state = pysoem.OP_STATE
   master.write_state()
   master.state_check(pysoem.OP_STATE, timeout=5 * 50000)
   ```
   - Transitions slaves to Operational state
   - Data exchange thread must be running

10. **Configure CST Mode (STEP 9)**
    - Sets operation mode to CST (10)
    - Configures torque limits and slope
    - Verifies mode configuration

11. **Cyclic Operation**
    - Executes state machine for motor control:
      - 0x0080: Fault Reset
      - 0x0006: Shutdown
      - 0x0007: Switch On
      - 0x000F: Enable Operation
    - Continuously sends target torque and receives status

## Main Functions

### Core Functions

- `find_adapters()`: Find available network adapters
- `scan_slaves(master)`: Scan and display all slave devices
- `enter_preop_state(master)`: Transition slaves to PREOP state
- `configure_pdo_mapping(master)`: Configure PDO mapping for CST mode
- `configure_slaves(master)`: Configure slaves and perform data mapping
- `enter_safeop_state(master)`: Configure DC and enter SAFEOP state
- `start_data_exchange_thread(master)`: Start background data exchange thread
- `set_slaves_to_op_state_cst(master)`: Transition slaves to OP state
- `configure_cst_mode(master)`: Configure CST mode parameters
- `cyclic_operation_cst(master, duration=300)`: Execute CST mode cyclic operation

### Utility Functions

- `get_state_name(state_code)`: Convert state code to human-readable name
- `check_slave_al_status(slave)`: Check slave AL status register
- `print_slave_state_machine_info(master, slave_index)`: Print detailed state machine info
- `check_slave_states(master, show_all=False)`: Check and display all slave states
- `check_permissions()`: Check for root privileges

## Troubleshooting

### ⚠️ OP State Drops (Expected Behavior)

**If slaves drop from OP state during operation, this is expected behavior due to pysoem's real-time limitations.**

**Why it happens:**
- Python's non-real-time scheduling causes cycle time jitter
- System load can delay data exchange cycles
- Network stack delays in user space
- Python GIL may block threads

**What to expect:**
- Slaves may periodically drop from OP to SAFEOP or PREOP
- WKC (Working Counter) may show timeouts
- Status checks may show inconsistent states

**This is normal for this demo and indicates the limitations of user-space EtherCAT implementations.**

### Common Issues

1. **"ModuleNotFoundError: No module named 'pysoem'"**
   - **Solution**: Install pysoem using `pip install pysoem` or use conda environment
   - If using conda, ensure you're using the correct Python interpreter

2. **"ConnectionError: could not open interface"**
   - **Solution**: Run with `sudo` (Linux) or Administrator privileges (Windows)
   - Check if network interface is available: `ip link show` (Linux) or `ipconfig` (Windows)
   - Ensure no other program is using the network interface

3. **"No EtherCAT slaves found"**
   - **Solution**: 
     - Check EtherCAT cable connections
     - Ensure slave devices are powered on
     - Verify network adapter is connected to EtherCAT network
     - Check if slaves are properly configured

4. **Slaves not entering OP state or dropping from OP**
   - **Possible causes**:
     - Data exchange thread not running or unstable
     - PDO mapping incorrect
     - DC not properly configured (check 0x1C32:0x01 should be 2)
     - Cycle time too short (try 2ms or 4ms)
     - SM2/SM3 (Sync Manager) state abnormal
     - **⚠️ Python's non-real-time nature causing cycle jitter (expected limitation)**
   - **Solution**:
     - Ensure data exchange thread is running continuously
     - Verify PDO mapping matches slave ESI file
     - Check DC configuration (0x1C32:0x01 = 2)
     - Increase cycle time to 2ms or 4ms (or even 5ms for more stability)
     - Check AL status code for specific errors
     - **Note: OP drops may still occur - this is a limitation of pysoem**

5. **WKC = -1 (Timeout)**
   - **Possible causes**:
     - Network issues
     - Cycle time too short
     - Receive timeout too short
   - **Solution**:
     - Check network cable and connections
     - Increase cycle time
     - Increase receive timeout in `receive_processdata(timeout=5000)`

6. **Motor not enabling**
   - **Possible causes**:
     - Control word sequence incorrect
     - Fault not cleared
     - Mode of operation not set correctly
     - Status word shows fault or switch on disabled
   - **Solution**:
     - Verify control word sequence: 0x0080 → 0x0006 → 0x0007 → 0x000F
     - Check Status Word (0x6041) for fault bits
     - Verify Mode of Operation (0x6060) is set to 10 (CST)
     - Check Error Code (0x603F) for specific errors

### Debugging Tips

1. **Enable detailed logging**: The program already includes detailed state information printing
2. **Check AL status codes**: Use `check_slave_al_status()` to diagnose slave errors
3. **Monitor Status Word**: Check Status Word (0x6041) bits for motor state
4. **Verify PDO data**: Check sent/received PDO data in cyclic operation output
5. **Check DC configuration**: Verify 0x1C32:0x01 = 2 for successful DC activation

## Customization

### Modify Cycle Time

Edit the global variable at the top of `pysoem_tset.py`:

```python
ETHERCAT_CYCLE_TIME_MS = 2.0  # Change to desired cycle time (ms)
```

### Modify CST Mode Parameters

Edit the `configure_cst_mode()` function:

```python
operation_mode = 10  # CST mode
max_torque = 100     # Maximum torque limit
torque_slope = 100   # Torque slope
```

### Modify Target Torque

Edit the `cyclic_operation_cst()` function:

```python
_thread_target_torque = 50  # Set target torque value
```

### Add Custom Data Processing

Modify the `cyclic_operation_cst()` function to add custom logic for processing input/output data:

```python
# Read slave input data
statusword = int.from_bytes(master.slaves[0].input[0:2], 'little')
actual_position = int.from_bytes(master.slaves[0].input[2:6], 'little', signed=True)
actual_velocity = int.from_bytes(master.slaves[0].input[6:10], 'little', signed=True)
actual_torque = int.from_bytes(master.slaves[0].input[10:12], 'little', signed=True)

# Add your custom processing logic here
```

### Select Specific Adapter

Modify the `main()` function to select a specific adapter:

```python
# Instead of adapters[0], select by name or index
selected_adapter = None
for adapter in adapters:
    if adapter.name == 'enp58s0':  # Your adapter name
        selected_adapter = adapter
        break
```

## Slave State Description

- **INIT**: Initialization state - Initial state after power-on
- **PREOP**: Pre-Operational state - PDO mapping can be configured in this state
- **SAFEOP**: Safe Operational state - Process data can be exchanged, but outputs are disabled
- **OP**: Operational state - Full process data exchange enabled, motor can be controlled

## State Machine (CiA 402)

The program implements the CiA 402 state machine for motor control:

1. **Fault Reset (0x0080)**: Clear any existing faults
2. **Shutdown (0x0006)**: Prepare motor for operation
3. **Switch On (0x0007)**: Enable motor power
4. **Enable Operation (0x000F)**: Enable motor operation, ready for torque control

## References

- [pysoem PyPI page](https://pypi.org/project/pysoem/)
- [EtherCAT Technology Group](https://www.ethercat.org/)
- [CiA 402 - CANopen device profile for drives and motion control](https://www.can-cia.org/can-knowledge/canopen/cia402/)
- Reference C++ implementation: `eRob_CST.cpp`

## License

This is an example program for educational and demonstration purposes.

## Disclaimer

**This software is provided "as is" without warranty of any kind. The authors and contributors are not responsible for any damage or loss caused by the use of this software.**

**For production or industrial applications, please use professional-grade EtherCAT master solutions such as IGH EtherCAT Master or kernel-level implementations.**
