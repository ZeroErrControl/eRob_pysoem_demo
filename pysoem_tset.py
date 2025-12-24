#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pysoem EtherCAT Slave Driver Example - CST Mode
Reference implementation based on eRob_CST.cpp, following the C++ program flow exactly
Demonstrates how to use the pysoem library to drive and control EtherCAT slave devices in CST (Cyclic Synchronous Torque) mode
"""

import sys
import time
import os
import threading

# Check if pysoem is available
try:
    import pysoem
except ModuleNotFoundError:
    print("Error: pysoem module not found")
    print("Please install using: pip install pysoem")
    print("Or run this script with Python from conda environment")
    print("\nTip: If using conda environment, use 'python3' instead of '/bin/python3'")
    sys.exit(1)


def get_state_name(state_code):
    """Convert state code to human-readable state name"""
    state_names = {
        pysoem.INIT_STATE: "INIT (Initialization)",
        pysoem.PREOP_STATE: "PREOP (Pre-Operational)",
        pysoem.SAFEOP_STATE: "SAFEOP (Safe Operational)",
        pysoem.OP_STATE: "OP (Operational)",
        pysoem.BOOT_STATE: "BOOT (Boot)",
    }
    # State codes are usually 1, 2, 4, 8, but sometimes there are combined values
    if state_code in state_names:
        return state_names[state_code]
    # Check if it's a combined state
    state_parts = []
    if state_code & pysoem.INIT_STATE:
        state_parts.append("INIT")
    if state_code & pysoem.PREOP_STATE:
        state_parts.append("PREOP")
    if state_code & pysoem.SAFEOP_STATE:
        state_parts.append("SAFEOP")
    if state_code & pysoem.OP_STATE:
        state_parts.append("OP")
    if state_code & pysoem.BOOT_STATE:
        state_parts.append("BOOT")
    if state_parts:
        return f"Combined State ({'+'.join(state_parts)}, value={state_code})"
    return f"Unknown State ({state_code})"


def check_slave_al_status(slave):
    """Check the slave's AL (Application Layer) status register to get error information"""
    try:
        al_status = slave.al_status
        if al_status != 0:
            # AL status code meanings
            al_status_meanings = {
                0x0001: "Initialization Error",
                0x0002: "Not Initialized",
                0x0003: "Initializing",
                0x0004: "Operation Ready",
                0x0011: "No Free Run",
                0x0012: "Synchronization Error",
                0x0013: "Watchdog Error",
                0x0014: "Version Error",
                0x0015: "Device Type Mismatch",
                0x0016: "ID Error",
                0x0017: "PDI Error",
                0x0018: "Initialization Error",
                0x0019: "Not Initialized",
                0x001A: "Initializing",
                0x001B: "Operation Ready",
            }
            meaning = al_status_meanings.get(al_status, f"Unknown Error Code")
            return f"AL Status: 0x{al_status:04X} ({meaning})"
        return "AL Status: Normal (0x0000)"
    except:
        return "Unable to read AL status"


def print_slave_state_machine_info(master, slave_index):
    """Print detailed state machine information for the slave"""
    slave = master.slaves[slave_index]
    
    print(f"\n========== Slave {slave_index} ({slave.name}) Detailed State Machine Information ==========")
    
    # 1. EtherCAT State
    master.read_state()
    ec_state = slave.state
    print(f"EtherCAT State: {get_state_name(ec_state)} (value: 0x{ec_state:02X})")
    
    # 2. AL Status Code
    try:
        al_status = slave.al_status
        print(f"AL 状态码: 0x{al_status:04X}")
        al_info = check_slave_al_status(slave)
        print(f"  {al_info}")
    except:
        print("AL 状态码: 无法读取")
    
    # 3. Status Word (0x6041)
    try:
        status_word_data = slave.sdo_read(0x6041, 0x00, 2)
        if status_word_data:
            status_word = int.from_bytes(status_word_data, 'little')
            print(f"Status Word (0x6041): 0x{status_word:04X} ({status_word})")
            print(f"  Bit 0 (Ready to switch on): {bool(status_word & 0x0001)}")
            print(f"  Bit 1 (Switched on): {bool(status_word & 0x0002)}")
            print(f"  Bit 2 (Operation enabled): {bool(status_word & 0x0004)}")
            print(f"  Bit 3 (Fault): {bool(status_word & 0x0008)}")
            print(f"  Bit 4 (Voltage enabled): {bool(status_word & 0x0010)}")
            print(f"  Bit 5 (Quick stop): {bool(status_word & 0x0020)}")
            print(f"  Bit 6 (Switch on disabled): {bool(status_word & 0x0040)}")
            print(f"  Bit 7 (Warning): {bool(status_word & 0x0080)}")
            print(f"  Bit 8 (Manufacturer specific): {bool(status_word & 0x0100)}")
            print(f"  Bit 9 (Remote): {bool(status_word & 0x0200)}")
            print(f"  Bit 10 (Target reached): {bool(status_word & 0x0400)}")
            print(f"  Bit 11 (Internal limit active): {bool(status_word & 0x0800)}")
    except Exception as e:
        print(f"Status Word (0x6041): Unable to read ({e})")
    
    # 4. Control Word (0x6040)
    try:
        control_word_data = slave.sdo_read(0x6040, 0x00, 2)
        if control_word_data:
            control_word = int.from_bytes(control_word_data, 'little')
            print(f"Control Word (0x6040): 0x{control_word:04X} ({control_word})")
    except Exception as e:
        print(f"Control Word (0x6040): Unable to read ({e})")
    
    # 5. Error Code (0x603F)
    try:
        error_code_data = slave.sdo_read(0x603F, 0x00, 2)
        if error_code_data:
            error_code = int.from_bytes(error_code_data, 'little')
            print(f"Error Code (0x603F): 0x{error_code:04X}")
            if error_code != 0:
                print(f"  ⚠ Slave has error!")
    except Exception as e:
        print(f"Error Code (0x603F): Unable to read ({e})")
    
    # 6. Mode of Operation Display (0x6061)
    try:
        mode_display_data = slave.sdo_read(0x6061, 0x00, 1)
        if mode_display_data:
            mode_display = int.from_bytes(mode_display_data, 'little')
            print(f"Mode of Operation Display (0x6061): {mode_display}")
            mode_names = {
                1: "Profile Position",
                3: "Profile Velocity",
                4: "Profile Torque",
                6: "Homing",
                7: "Interpolated Position",
                8: "Cyclic Synchronous Position (CSP)",
                9: "Cyclic Synchronous Velocity (CSV)",
                10: "Cyclic Synchronous Torque (CST)"
            }
            print(f"  Mode Name: {mode_names.get(mode_display, 'Unknown Mode')}")
    except Exception as e:
        print(f"Mode of Operation Display (0x6061): Unable to read ({e})")
    
    # 7. Mode of Operation (0x6060)
    try:
        mode_data = slave.sdo_read(0x6060, 0x00, 1)
        if mode_data:
            mode = int.from_bytes(mode_data, 'little')
            print(f"Mode of Operation (0x6060): {mode}")
    except Exception as e:
        print(f"Mode of Operation (0x6060): Unable to read ({e})")
    
    # 8. Input/Output Byte Count
    try:
        input_bytes = len(slave.input) if hasattr(slave, 'input') and slave.input else 0
        output_bytes = len(slave.output) if hasattr(slave, 'output') and slave.output else 0
        print(f"Input Bytes: {input_bytes}")
        print(f"Output Bytes: {output_bytes}")
    except:
        print("Input/Output Bytes: Unable to read")
    
    print("=" * 60)


def check_slave_states(master, show_all=False):
    """Check and display the state of all slaves"""
    # Read current state of all slaves
    master.read_state()
    
    print("\nSlave State Check:")
    all_in_op = True
    
    for i, slave in enumerate(master.slaves):
        current_state = slave.state
        state_name = get_state_name(current_state)
        
        if show_all or current_state != pysoem.OP_STATE:
            print(f"  Slave {i} ({slave.name}): {state_name}")
        
        if current_state != pysoem.OP_STATE:
            all_in_op = False
    
    # Check master state
    master_state = master.state
    master_state_name = get_state_name(master_state)
    print(f"  Master State: {master_state_name}")
    
    return all_in_op


def check_permissions():
    """Check if there are sufficient permissions to access the network interface"""
    if os.geteuid() != 0:
        print("Warning: Not running with root privileges")
        print("EtherCAT communication typically requires root privileges to open network interface")
        print("\nRecommended ways to run:")
        print("  sudo python3 pysoem_tset.py")
        print("  or")
        print("  sudo /home/zeroerr/anaconda3/bin/python pysoem_tset.py")
        print("\nContinuing to try running...")
        return False
    return True


def find_adapters():
    """Find available network adapters"""
    print("Searching for network adapters...")
    adapters = pysoem.find_adapters()
    
    if not adapters:
        print("No network adapters found!")
        return None
    
    # Filter out loopback interface
    valid_adapters = [adapter for adapter in adapters if adapter.name != 'lo']
    
    print(f"Found {len(adapters)} network adapters:")
    for i, adapter in enumerate(adapters):
        marker = " (skipped)" if adapter.name == 'lo' else ""
        print(f"  [{i}] {adapter.name} - {adapter.desc}{marker}")
    
    # Return valid adapters (excluding loopback)
    return valid_adapters if valid_adapters else adapters


def scan_slaves(master):
    """Scan and display all slave devices (Reference: C++ program eRob_CST.cpp STEP 1)"""
    print("\n__________STEP 1: Scan Slaves__________")
    
    # Configure initialization, scan slaves
    if master.config_init() > 0:
        print(f"Found {len(master.slaves)} slave devices")
        print("___________________________________________")
        
        return True
    else:
        print("Error: No EtherCAT slaves found!")
        print("___________________________________________")
        return False


def enter_preop_state(master):
    """Enter PREOP state (Reference: C++ program eRob_CST.cpp STEP 2)"""
    print("\n__________STEP 2: Switch to PREOP State__________")
    
    # Check if slaves are ready for mapping (Reference: C++ ec_readstate())
    master.read_state()
    
    # Check state of each slave (Reference: C++ for(int i = 1; i <= ec_slavecount; i++))
    for i, slave in enumerate(master.slaves):
        if slave.state != pysoem.PREOP_STATE:
            # If slave is not in PRE-OP state, print state information (Reference: C++)
            al_info = check_slave_al_status(slave)
            print(f"Slave {i} State=0x{slave.state:02x}, {al_info}")
            print(f"\nRequest slave {i} to enter INIT state")
            try:
                # Set slave state to INIT (Reference: C++ ec_slave[i].state = EC_STATE_INIT)
                slave.state = pysoem.INIT_STATE
                master.write_state()
                time.sleep(0.1)
                print("___________________________________________")
            except Exception as e:
                print(f"  ⚠ Switch failed: {e}")
                print("___________________________________________")
        else:
            # If slave is in PRE-OP state, set master state and write (Reference: C++)
            # C++: ec_slave[0].state = EC_STATE_PRE_OP; ec_writestate(0);
            master.state = pysoem.PREOP_STATE
            master.write_state()
            
            # Wait for all slaves to reach PRE-OP state (Reference: C++ ec_statecheck)
            result_state = master.state_check(pysoem.PREOP_STATE, timeout=3 * 50000)  # 3 * EC_TIMEOUTSTATE
            if result_state == pysoem.PREOP_STATE:
                print(f"State switched to PREOP: {pysoem.PREOP_STATE}")
                print("___________________________________________")
                return True
            else:
                print("State cannot switch to PREOP in STEP 2")
                return False
    
    # If all slaves are not in PREOP, try to switch to PREOP (Reference: C++ logic)
    # Note: C++ program continues execution after setting INIT if slave is not in PREOP
    # Actually, after config_init(), slaves should be in PREOP state
    # If not, we need to actively switch to PREOP
    master.read_state()
    all_preop = True
    for i, slave in enumerate(master.slaves):
        if slave.state != pysoem.PREOP_STATE:
            all_preop = False
            break
    
    if not all_preop:
        # Try to switch to PREOP
        print("\nAttempting to switch all slaves to PREOP state...")
        master.state = pysoem.PREOP_STATE
        master.write_state()
        time.sleep(0.2)
        
        # Wait for state transition
        result_state = master.state_check(pysoem.PREOP_STATE, timeout=3 * 50000)
        master.read_state()
        
        if result_state == pysoem.PREOP_STATE:
            print(f"✓ State switched to PREOP: {pysoem.PREOP_STATE}")
            print("___________________________________________")
            return True
        else:
            print("⚠ Warning: Unable to switch all slaves to PREOP state")
            # Display current state
            for i, slave in enumerate(master.slaves):
                print(f"  Slave {i} State: {get_state_name(slave.state)}")
            return False
    
    return True


def check_pdo_exists(slave, pdo_index):
    """Check if PDO exists"""
    try:
        # Try to read the first sub-index of the PDO
        data = slave.sdo_read(pdo_index, 0x00, 1)
        return True
    except:
        return False


def configure_pdo_mapping(master):
    """Configure PDO mapping (Reference: C++ program eRob_CST.cpp STEP 3)
    Configure RXPDO (0x1600) and TXPDO (0x1A00) - CST mode
    Note: Must be configured in PREOP state
    """
    print("\n__________STEP 3: Configure PDO Mapping (CST Mode)__________")
    
    # Ensure slaves are in PREOP state (PDO mapping must be configured in PREOP state)
    master.read_state()
    all_preop = True
    for i, slave in enumerate(master.slaves):
        if slave.state != pysoem.PREOP_STATE:
            print(f"⚠ Slave {i} not in PREOP state, current state: {get_state_name(slave.state)}")
            all_preop = False
            # Try to switch to PREOP
            try:
                slave.state = pysoem.PREOP_STATE
                master.write_state()
                time.sleep(0.2)
                master.read_state()
                if slave.state == pysoem.PREOP_STATE:
                    print(f"  ✓ Slave {i} switched to PREOP state")
                    all_preop = True
                else:
                    print(f"  ✗ Slave {i} cannot enter PREOP state")
            except Exception as e:
                print(f"  ✗ State switch failed: {e}")
    
    if not all_preop:
        print("⚠ Warning: Some slaves are not in PREOP state, PDO mapping may fail")
        return False
    
    retval = 0  # Return value accumulator
    
    for i, slave in enumerate(master.slaves):
        try:
            print(f"\nConfiguring RXPDO (0x1600) for slave {i} ({slave.name})...")
            
            # Reference C++: Clear 0x1600 mapping
            zero_map = 0
            try:
                slave.sdo_write(0x1600, 0x00, zero_map.to_bytes(1, 'little'))
                time.sleep(0.05)
            except Exception as e:
                print(f"  ⚠ Failed to clear 0x1600: {e}")
            
            # Configure 0x1600 PDO mapping (Reference: C++ structure)
            # Control Word (0x6040:0, 16 bits) -> 0x60400010
            map_object = 0x60400010
            try:
                slave.sdo_write(0x1600, 0x01, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Control Word (0x6040:0, 16 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Control Word: {e}")
                retval -= 1
            
            # Target Torque (0x6071:0, 16 bits) -> 0x60710010
            map_object = 0x60710010
            try:
                slave.sdo_write(0x1600, 0x02, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Target Torque (0x6071:0, 16 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Target Torque: {e}")
                retval -= 1
            
            # Mode of Operation (0x6060:0, 8 bits) -> 0x60600008
            map_object = 0x60600008
            try:
                slave.sdo_write(0x1600, 0x03, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Mode of Operation (0x6060:0, 8 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Mode of Operation: {e}")
                retval -= 1
            
            # Padding (8 bits) -> 0x00000008
            map_object = 0x00000008
            try:
                slave.sdo_write(0x1600, 0x04, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Padding (8 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Padding: {e}")
                retval -= 1
            
            # Set mapping object count (Reference: C++ map_count = 4)
            map_count = 4
            try:
                slave.sdo_write(0x1600, 0x00, map_count.to_bytes(1, 'little'))
                time.sleep(0.05)
                print(f"  ✓ RXPDO 0x1600 mapping count set to {map_count}")
            except Exception as e:
                print(f"  ⚠ Failed to set mapping count: {e}")
                retval -= 1
            
            # Configure RXPDO assignment (0x1C12)
            clear_val = 0x0000
            try:
                slave.sdo_write(0x1C12, 0x00, clear_val.to_bytes(2, 'little'))
                time.sleep(0.05)
            except Exception as e:
                print(f"  ⚠ Failed to clear 0x1C12: {e}")
            
            map_1c12 = 0x1600
            try:
                slave.sdo_write(0x1C12, 0x01, map_1c12.to_bytes(2, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Configured RXPDO assignment: 0x1600")
            except Exception as e:
                print(f"  ⚠ Failed to configure RXPDO assignment: {e}")
                retval -= 1
            
            map_1c12 = 0x0001
            try:
                slave.sdo_write(0x1C12, 0x00, map_1c12.to_bytes(2, 'little'))
                time.sleep(0.05)
                print(f"  ✓ RXPDO assignment count set to 1")
            except Exception as e:
                print(f"  ⚠ Failed to set RXPDO assignment count: {e}")
                retval -= 1
            
            # Configure TXPDO (0x1A00)
            print(f"\nConfiguring TXPDO (0x1A00) for slave {i} ({slave.name})...")
            
            # Clear 0x1A00 mapping
            clear_val = 0x0000
            try:
                slave.sdo_write(0x1A00, 0x00, clear_val.to_bytes(2, 'little'))
                time.sleep(0.05)
            except Exception as e:
                print(f"  ⚠ Failed to clear 0x1A00: {e}")
            
            # Status Word (0x6041:0, 16 bits) -> 0x60410010
            map_object = 0x60410010
            try:
                slave.sdo_write(0x1A00, 0x01, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Status Word (0x6041:0, 16 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Status Word: {e}")
                retval -= 1
            
            # Actual Position (0x6064:0, 32 bits) -> 0x60640020
            map_object = 0x60640020
            try:
                slave.sdo_write(0x1A00, 0x02, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Actual Position (0x6064:0, 32 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Actual Position: {e}")
                retval -= 1
            
            # Actual Velocity (0x606C:0, 32 bits) -> 0x606C0020
            map_object = 0x606C0020
            try:
                slave.sdo_write(0x1A00, 0x03, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Actual Velocity (0x606C:0, 32 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Actual Velocity: {e}")
                retval -= 1
            
            # Actual Torque (0x6077:0, 16 bits) -> 0x60770010
            map_object = 0x60770010
            try:
                slave.sdo_write(0x1A00, 0x04, map_object.to_bytes(4, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Added Actual Torque (0x6077:0, 16 bits)")
            except Exception as e:
                print(f"  ⚠ Failed to add Actual Torque: {e}")
                retval -= 1
            
            # Set mapping object count (Reference: C++ map_count = 4)
            map_count = 4
            try:
                slave.sdo_write(0x1A00, 0x00, map_count.to_bytes(1, 'little'))
                time.sleep(0.05)
                print(f"  ✓ TXPDO 0x1A00 mapping count set to {map_count}")
            except Exception as e:
                print(f"  ⚠ Failed to set mapping count: {e}")
                retval -= 1
            
            # Configure TXPDO assignment (0x1C13)
            clear_val = 0x0000
            try:
                slave.sdo_write(0x1C13, 0x00, clear_val.to_bytes(2, 'little'))
                time.sleep(0.05)
            except Exception as e:
                print(f"  ⚠ Failed to clear 0x1C13: {e}")
            
            map_1c13 = 0x1A00
            try:
                slave.sdo_write(0x1C13, 0x01, map_1c13.to_bytes(2, 'little'))
                time.sleep(0.05)
                print(f"  ✓ Configured TXPDO assignment: 0x1A00")
            except Exception as e:
                print(f"  ⚠ Failed to configure TXPDO assignment: {e}")
                retval -= 1
            
            map_1c13 = 0x0001
            try:
                slave.sdo_write(0x1C13, 0x00, map_1c13.to_bytes(2, 'little'))
                time.sleep(0.05)
                print(f"  ✓ TXPDO assignment count set to 1")
            except Exception as e:
                print(f"  ⚠ Failed to set TXPDO assignment count: {e}")
                retval -= 1
            
            # Configure torque-related parameters (Reference: C++)
            try:
                positive_torque_limit = 0
                negative_torque_limit = 0
                slave.sdo_write(0x60E0, 0x00, positive_torque_limit.to_bytes(2, 'little', signed=True))
                slave.sdo_write(0x60E1, 0x00, negative_torque_limit.to_bytes(2, 'little', signed=True))
                time.sleep(0.05)
                print(f"  ✓ Configured torque limit parameters")
            except Exception as e:
                print(f"  ⚠ Failed to configure torque limit parameters: {e}")
            
        except Exception as e:
            print(f"  ⚠ PDO mapping configuration failed for slave {i}: {e}")
            import traceback
            traceback.print_exc()
            retval -= 1
    
    print(f"\nPDO mapping configuration result: {retval}")
    if retval < 0:
        print("⚠ Warning: PDO mapping configuration has errors")
        return False
    
    print("✓ PDO mapping configuration completed")
    return True




def configure_slaves(master):
    """Configure slaves and perform data mapping (Reference: C++ program eRob_CST.cpp STEP 4)"""
    print("\n__________STEP 4: Configure Slaves and Perform Data Mapping__________")
    
    # 设置手动状态转换（禁用自动状态转换）- 参考 C++ 的 ecx_context.manualstatechange = 1
    master.manual_state_change = True
    time.sleep(1.0)  # 参考 C++ 的 osal_usleep(1e6)
    
    # 打印从站信息（参考 C++）
    master.read_state()
    for i, slave in enumerate(master.slaves):
        print(f"Name: {slave.name}")
        print(f"Slave {i}: Type {slave.id}, Address 0x{i:02x}, State Machine actual {slave.state}, required {pysoem.INIT_STATE}")
        print("___________________________________________")
    
    # 确保从站在 PREOP 状态（config_map 需要在 PREOP 状态）
    master.read_state()
    all_preop = True
    for i, slave in enumerate(master.slaves):
        if slave.state != pysoem.PREOP_STATE:
            print(f"⚠ Slave {i} not in PREOP state, current state: {get_state_name(slave.state)}")
            all_preop = False
            # Try to switch to PREOP
            try:
                slave.state = pysoem.PREOP_STATE
                master.write_state()
                time.sleep(0.2)
                master.read_state()
                if slave.state == pysoem.PREOP_STATE:
                    print(f"  ✓ Slave {i} switched to PREOP state")
                    all_preop = True
            except Exception as e:
                print(f"  ✗ Switch failed: {e}")
    
    if not all_preop:
        print("⚠ Warning: Some slaves are not in PREOP state, config_map may fail")
        return False
    
    # Configure process data mapping - Reference C++ ec_config_map(&IOmap)
    print("\nMapping PDO to IO map (Reference: C++ ec_config_map)...")
    try:
        io_map_size = master.config_map()
        print(f"✓ IO map size: {io_map_size} bytes")
    except Exception as e:
        print(f"⚠ Warning: config_map failed: {e}")
        print("  Attempting to use default PDO mapping...")
        # If custom PDO mapping fails, try using default mapping
        # First clear custom mapping, then use default mapping
        try:
            for i, slave in enumerate(master.slaves):
                # Clear custom mapping
                try:
                    slave.sdo_write(0x1C12, 0x00, (0).to_bytes(2, 'little'))
                    slave.sdo_write(0x1C13, 0x00, (0).to_bytes(2, 'little'))
                    time.sleep(0.05)
                except:
                    pass
            
            # Reinitialize to use default mapping
            master.config_init()
            time.sleep(0.2)
            
            # Ensure slaves are in PREOP state (should be in PREOP after config_init)
            master.read_state()
            for i, slave in enumerate(master.slaves):
                if slave.state != pysoem.PREOP_STATE:
                    print(f"  Slave {i} not in PREOP state, attempting to switch back to PREOP...")
                    try:
                        slave.state = pysoem.PREOP_STATE
                        master.write_state()
                        time.sleep(0.2)
                        master.read_state()
                    except:
                        pass
            
            # Try mapping again
            io_map_size = master.config_map()
            print(f"✓ Successfully used default PDO mapping, IO map size: {io_map_size} bytes")
        except Exception as e2:
            print(f"✗ Error: Unable to configure PDO mapping: {e2}")
            # Even if failed, try to ensure slaves are in PREOP state
            try:
                master.read_state()
                for i, slave in enumerate(master.slaves):
                    if slave.state != pysoem.PREOP_STATE:
                        print(f"  Attempting to switch slave {i} back to PREOP state...")
                        slave.state = pysoem.PREOP_STATE
                        master.write_state()
                        time.sleep(0.2)
                        master.read_state()
            except:
                pass
            raise
    
    # Display input/output information after configuration
    for i, slave in enumerate(master.slaves):
        try:
            input_bytes = len(slave.input) if hasattr(slave, 'input') and slave.input else 0
            output_bytes = len(slave.output) if hasattr(slave, 'output') and slave.output else 0
            if input_bytes > 0 or output_bytes > 0:
                print(f"Slave {i} ({slave.name}): Input={input_bytes} bytes, Output={output_bytes} bytes")
        except:
            pass
    
    print("✓ STEP 4 completed")
    return True


def enter_safeop_state(master):
    """Enter SAFEOP state (Reference: C++ program STEP 5)"""
    print("\n__________STEP 5: State Transition to SAFEOP__________")
    
    # Ensure all slaves are in PREOP state (Reference: C++ program check)
    master.read_state()
    for i, slave in enumerate(master.slaves):
        if slave.state != pysoem.PREOP_STATE:
            print(f"⚠ Slave {i} not in PREOP state, current state: {get_state_name(slave.state)}")
            al_info = check_slave_al_status(slave)
            print(f"  {al_info}")
            # If not in PREOP, cannot continue
            return False
    
    # Configure Distributed Clock (Reference: C++ ec_configdc()) - Must be done before entering SAFEOP
    # Correct order: config_map -> config_dc -> set dc_sync for each slave
    print("\nConfiguring Distributed Clock DC (Reference: C++ ec_configdc())...")
    try:
        dc_result = master.config_dc()
        print(f"  DC configuration result: {dc_result}")
        if dc_result:
            print("    ✓ DC configuration successful")
        else:
            print("    ⚠ DC configuration returned False, may have issues")
        time.sleep(0.2)
    except Exception as e:
        print(f"  ⚠ DC configuration failed (may not be supported): {e}")
        import traceback
        traceback.print_exc()
        time.sleep(0.2)

    # After config_dc, set dc_sync (Sync0) for each slave
    # Use unified cycle configuration
    print(f"\nConfiguring DC Sync0 for each slave (cycle: {ETHERCAT_CYCLE_TIME_NS} ns = {ETHERCAT_CYCLE_TIME_MS} ms)...")
    for i, slave in enumerate(master.slaves):
        try:
            slave.dc_sync(act=True, sync0_cycle_time=ETHERCAT_CYCLE_TIME_NS, sync0_shift_time=0)
            print(f"  Slave {i} ({slave.name}): DC Sync0 configured (cycle: {ETHERCAT_CYCLE_TIME_NS} ns = {ETHERCAT_CYCLE_TIME_MS} ms)")
        except Exception as e:
            print(f"  ⚠ Failed to configure DC Sync0 for slave {i}: {e}")
    
    # Request switch to SAFEOP state (Reference: C++ program)
    print("\nRequesting switch to SAFEOP state...")
    # Reference C++: ec_slave[0].state = EC_STATE_SAFE_OP; ec_writestate(0);
    # Note: In C++, only ec_slave[0].state is set, then ec_writestate(0) applies to all slaves
    master.state = pysoem.SAFEOP_STATE
    # Don't set each slave.state separately, let master.state affect all slaves
    master.write_state()
    
    # Wait for state transition (Reference: C++ ec_statecheck(0, EC_STATE_SAFE_OP, EC_TIMEOUTSTATE * 4))
    result_state = master.state_check(pysoem.SAFEOP_STATE, timeout=4 * 50000)  # 4 * EC_TIMEOUTSTATE
    
    if result_state == pysoem.SAFEOP_STATE:
        print("✓ Successfully switched to SAFEOP state")
    else:
        print("⚠ Warning: Unable to switch to SAFEOP state")
        check_slave_states(master, show_all=True)
        return False
    
    # Calculate expected working counter (Reference: C++)
    # expectedWKC = (ec_group[0].outputsWKC * 2) + ec_group[0].inputsWKC
    # Note: In pysoem, expected_wkc should already be automatically calculated
    print(f"Calculated working counter: {master.expected_wkc}")
    
    # Read and display basic state information of slaves (Reference: C++)
    master.read_state()
    for i, slave in enumerate(master.slaves):
        print(f"Slave {i}")
        print(f"  State: 0x{slave.state:02x}")
        print(f"  AL Status Code: 0x{slave.al_status:04x}")
        if hasattr(slave, 'pdelay'):
            print(f"  Delay: {slave.pdelay}")
        if hasattr(slave, 'hasdc'):
            print(f"  DC Supported: {slave.hasdc}")
        if hasattr(slave, 'DCactive'):
            print(f"  DC Active: {slave.DCactive}")
    
    # Read DC synchronization configuration (Reference: C++ read 0x1C32)
    # Key: The value of 0x1C32:0x01 must be 2 to indicate successful DC configuration
    print("\nReading DC synchronization configuration (0x1C32)...")
    dc_config_ok = True
    for i, slave in enumerate(master.slaves):
        try:
            # Read DC Control (0x1C32:0x01) - This is the key value!
            dc_control_data = slave.sdo_read(0x1C32, 0x01, 2)
            if dc_control_data:
                dc_control = int.from_bytes(dc_control_data, 'little')
                print(f"Slave {i} DC Configuration:")
                print(f"  DC Control (0x1C32:0x01): 0x{dc_control:04x} ({dc_control})")
                if dc_control == 2:
                    print(f"    ✓ DC activated (correct)")
                elif dc_control == 1:
                    print(f"    ⚠ DC enabled but not activated (needs check)")
                    dc_config_ok = False
                else:
                    print(f"    ✗ DC not correctly configured (expected: 2, actual: {dc_control})")
                    dc_config_ok = False
                
                # Read Cycle Time (0x1C32:0x02)
                cycle_time_data = slave.sdo_read(0x1C32, 0x02, 4)
                if cycle_time_data:
                    cycle_time = int.from_bytes(cycle_time_data, 'little', signed=True)
                    print(f"  Cycle Time (0x1C32:0x02): {cycle_time} ns")
        except Exception as e:
            print(f"  Failed to read DC configuration for slave {i}: {e}")
            dc_config_ok = False
    
    if not dc_config_ok:
        print("\n⚠ Warning: DC configuration may have issues, value of 0x1C32:0x01 is not 2")
        print("  This may prevent slaves from entering OP state")
        print("  Please check:")
        print("    1. Whether slaves support DC")
        print("    2. Whether both dc_sync() and config_dc() were successfully called")
        print("    3. Whether slaves are in PREOP state")
    
    # Print detailed state machine information
    print("\n========== Detailed State Machine Information in SAFEOP State ==========")
    for i in range(len(master.slaves)):
        print_slave_state_machine_info(master, i)
    
    print("✓ Slave configuration completed, entered SAFEOP state")
    return True


# ============================================================================
# EtherCAT Cycle Configuration (Unified configuration, modify here to change all cycles)
# ============================================================================
# Note: Python is not a real-time system, recommended cycle time >= 2ms
# 1ms cycle may cause:
#   1. Python scheduler cannot guarantee precise 1ms cycle
#   2. time.sleep() precision is insufficient at 1ms
#   3. DC synchronization may be unstable
#   4. Slaves may detect cycle instability and refuse to enter OP
# If 1ms must be used, recommended:
#   - Use real-time kernel (RT kernel)
#   - Set thread priority
#   - Use more precise timers (e.g., using RT library)
ETHERCAT_CYCLE_TIME_MS = 2.0  # EtherCAT communication cycle (milliseconds), recommended >= 2ms
ETHERCAT_CYCLE_TIME_NS = int(ETHERCAT_CYCLE_TIME_MS * 1_000_000)  # Convert to nanoseconds (for DC Sync0)

# Global variables for controlling data exchange thread
_data_exchange_running = False
_data_exchange_thread = None
_data_exchange_lock = threading.Lock()  # Lock to protect data exchange
# Count of cycles sent by thread, used to ensure sufficient valid output before switching to OP
_data_exchange_cycle_count = 0
# Thread output shared variables
_thread_controlword = 0x0080  # Initially Fault Reset, then switch to 0x0006 after one cycle
_thread_target_torque = 0
_thread_mode_of_operation = 10  # CST

def data_exchange_worker(master):
    """Data exchange worker thread (Reference: C++ program eRob_CST.cpp ecatthread function)
    
    Key: This thread must continuously run in SAFEOP state, periodically sending valid Output PDO
    This is a prerequisite for slaves to enter OP (90% of issues are here)
    
    This thread will continuously perform data exchange until _data_exchange_running is False
    """
    global _data_exchange_running
    
    padding = 0

    # Set initial PDO data (ensure Output PDO is valid and length is correct)
    with _data_exchange_lock:
        for i, slave in enumerate(master.slaves):
            try:
                if hasattr(slave, 'output') and slave.output:
                    output_data = bytearray(slave.output)
                    if len(output_data) >= 6:
                        output_data[0:2] = _thread_controlword.to_bytes(2, 'little')
                        output_data[2:4] = _thread_target_torque.to_bytes(2, 'little', signed=True)
                        output_data[4] = _thread_mode_of_operation
                        output_data[5] = padding
                        slave.output = bytes(output_data)
            except:
                pass
        # Send initial data (send then recv)
        master.send_processdata()
        wkc = master.receive_processdata(timeout=5000)

        # Note: Do not modify _thread_controlword here!
        # Control word should be fully controlled by main thread state machine (cyclic_operation_cst)
        # Thread only reads _thread_controlword and sends it, does not modify it
    
    # Continuously perform data exchange (Reference: C++ while(1) loop)
    # Key: In SAFEOP state, must periodically send Output PDO
    # Slaves will check: if no periodic output → refuse to enter OP
    # Use unified cycle configuration
    cycle_time = ETHERCAT_CYCLE_TIME_MS / 1000.0  # Convert to seconds
    global _data_exchange_cycle_count
    
    while _data_exchange_running:
        try:
            cycle_start = time.time()
            
            # Use lock to protect data exchange (avoid conflict with main thread)
            with _data_exchange_lock:
                # Receive data (Reference: C++: receive first, then send)
                # Note: In C++ thread, receive first, then process data, then send
                wkc = master.receive_processdata(timeout=5000)
                
                if wkc >= master.expected_wkc:
                    # Read slave data (if needed)
                    # Can read Status Word here, but simplified, not processing for now
                    pass
                
                # Key: Must continuously send valid Output PDO (using shared variables)
                # Reference C++: memcpy(ec_slave[slave].outputs, &rxpdo, sizeof(rxpdo_t))
                for i, slave in enumerate(master.slaves):
                    try:
                        if hasattr(slave, 'output') and slave.output:
                            output_data = bytearray(slave.output)
                            if len(output_data) >= 6:
                                # Reference C++ structure rxpdo_t:
                                # controlword(2) + target_torque(2) + mode_of_operation(1) + padding(1)
                                output_data[0:2] = _thread_controlword.to_bytes(2, 'little')
                                output_data[2:4] = _thread_target_torque.to_bytes(2, 'little', signed=True)
                                output_data[4] = _thread_mode_of_operation
                                output_data[5] = padding
                                slave.output = bytes(output_data)
                    except Exception as e:
                        # If error occurs, log but do not interrupt data exchange
                        pass
                
                # Send data (key: must periodically send)
                master.send_processdata()
            
            # Count cycles, for use in waiting before OP
            _data_exchange_cycle_count += 1
            
            # Control cycle time
            cycle_elapsed = time.time() - cycle_start
            sleep_time = max(0, cycle_time - cycle_elapsed)
            
            # Diagnosis: If cycle time frequently times out, system cannot maintain this cycle
            if cycle_elapsed > cycle_time * 1.5 and _data_exchange_cycle_count % 1000 == 0:
                print(f"⚠ Warning: Cycle time timeout ({cycle_elapsed*1000:.2f}ms > {cycle_time*1000:.2f}ms), system may not be able to maintain {ETHERCAT_CYCLE_TIME_MS}ms cycle")
            
            if sleep_time > 0:
                time.sleep(sleep_time)
        except Exception as e:
            # If error occurs, wait briefly then continue (cannot stop data exchange)
            # Use unified cycle configuration
            time.sleep(ETHERCAT_CYCLE_TIME_MS / 1000.0)


def start_data_exchange_thread(master):
    """Start data exchange thread (Reference: C++ program eRob_CST.cpp STEP 6)
    
    Key: Before entering OP, need to start a thread to continuously perform data exchange
    """
    global _data_exchange_running, _data_exchange_thread, _data_exchange_cycle_count, _thread_controlword, _thread_target_torque
    
    print("\n__________STEP 6: Start Data Exchange Thread__________")
    
    # Reset cycle count and output variables
    _data_exchange_cycle_count = 0
    # Note: Do not set _thread_controlword here!
    # Control word should be fully controlled by state machine (cyclic_operation_cst)
    # If not yet set, use default value 0x0080 (Fault Reset)
    if _thread_controlword == 0:
        _thread_controlword = 0x0080  # Default starts from Fault Reset
    _thread_target_torque = 0

    # Reference C++: start_ecatthread_thread = TRUE
    _data_exchange_running = True
    
    # Start data exchange thread (Reference: C++ osal_thread_create_rt)
    _data_exchange_thread = threading.Thread(target=data_exchange_worker, args=(master,), daemon=True)
    _data_exchange_thread.start()
    
    print("Data exchange thread started (continuously performing data exchange)")
    
    # Wait for thread to perform several data exchanges, ensure slaves are ready
    time.sleep(0.01)  # Wait 10ms, let thread perform several data exchanges
    
    print("___________________________________________")
    return True


def stop_data_exchange_thread():
    """Stop data exchange thread"""
    global _data_exchange_running, _data_exchange_thread
    
    _data_exchange_running = False
    if _data_exchange_thread and _data_exchange_thread.is_alive():
        _data_exchange_thread.join(timeout=1.0)


def set_slaves_to_op_state_cst(master):
    """Set all slaves to enter OP state (Reference: C++ program eRob_CST.cpp STEP 8)
    
    Key points (Reference: C++ code):
    1. Initialize PDO data (do not set operation mode, operation mode is set in STEP 9)
    2. Send initial data
    3. Send/receive process data once
    4. Set ec_slave[0].state = EC_STATE_OPERATIONAL
    5. Call ec_writestate(0)
    6. Use ec_statecheck(0, EC_STATE_OPERATIONAL, 5 * EC_TIMEOUTSTATE) to check
    
    Note: C++ program does not set operation mode in STEP 8, operation mode is set in STEP 9
    """
    print("\n__________STEP 8: State Transition to OP__________")
    
    # Ensure slaves are in SAFEOP state
    master.read_state()
    for i, slave in enumerate(master.slaves):
        if slave.state != pysoem.SAFEOP_STATE:
            print(f"⚠ Slave {i} not in SAFEOP state, current state: {get_state_name(slave.state)}")
            return False
    
    # Key: Based on analysis, prerequisite for slaves to enter OP is master must periodically send valid Output PDO
    # Data exchange thread is already running (started in STEP 6), continuously sending Output PDO
    # In C++ program, when STEP 8 main thread sends data, thread is also running
    # Do not stop thread! Thread must continuously run, periodically sending Output PDO
    # Slaves will check: if no periodic output → refuse to enter OP
    global _data_exchange_running, _data_exchange_cycle_count
    
    # Wait for thread to run sufficient cycles first (at least 300, recommended 200~500)
    wait_cycles = 300
    print(f"\nWaiting for data exchange thread to run {wait_cycles} cycles first, ensure slaves see stable output...")
    start_wait = time.time()
    while _data_exchange_cycle_count < wait_cycles:
        time.sleep(ETHERCAT_CYCLE_TIME_MS / 1000.0)  # Use unified cycle configuration
        # Timeout protection: continue even if exceeds 1 second (1s/1ms=1000 cycles, usually enough)
        if time.time() - start_wait > 1.0:
            print(f"  ⚠ Wait exceeded 1 second, current cycle {_data_exchange_cycle_count}, continue trying to switch to OP")
            break
    
    # Initialize PDO data (Reference: C++), and use shared variables to control thread output
    # First prepare according to 402 enable sequence: 0x0006 -> 0x0007 -> 0x000F
    padding = 0
    
    # Keep thread output as 0x0006 (Shutdown keepalive), real 06→07→0F enable should be executed in control loop after OP
    # Main thread only confirms send/recv, does not change thread output
    # Main thread sends confirmation data (thread continuously running, using lock protection)
    print("\nMain thread sending confirmation data (thread continuously running)...")
    with _data_exchange_lock:
        master.send_processdata()
        wkc = master.receive_processdata(timeout=5000)
        print(f"  Initial data exchange WKC: {wkc}/{master.expected_wkc}")
        master.send_processdata()
        wkc = master.receive_processdata(timeout=5000)
        print(f"  Second data exchange WKC: {wkc}/{master.expected_wkc}")
    
    # Set all slaves to OP state (Reference: C++ ec_slave[0].state = EC_STATE_OPERATIONAL; ec_writestate(0))
    # Note: In pysoem, write_state() will write state according to each slave.state,
    # so need to first set each slave state to OP, then call write_state()
    print("\nSetting state to OP...")
    for i, slave in enumerate(master.slaves):
        slave.state = pysoem.OP_STATE
        print(f"  Slave {i} state set to: {pysoem.OP_STATE} (OP)")
    master.state = pysoem.OP_STATE
    
    # Write state to slaves (Reference: C++ ec_writestate(0))
    # Note: In C++, only ec_slave[0].state is set, then ec_writestate(0) applies to all slaves
    # In pysoem, need to set each slave.state, then call write_state()
    print("Writing state to slaves...")
    write_wkc = master.write_state()
    print(f"  Write state WKC: {write_wkc}")
    
    if write_wkc == 0:
        print("  ⚠ Warning: Write state failed, WKC is 0")
        return False
    
    # Key: Data exchange thread must continuously run!
    # Prerequisite for slaves to enter OP: master must periodically send valid Output PDO
    # If thread is stopped, slaves cannot detect periodic output, will refuse to enter OP
    # So thread must continuously run, continuously sending Output PDO
    
    # Wait for state transition to complete (Reference: C++ ec_statecheck(0, EC_STATE_OPERATIONAL, 5 * EC_TIMEOUTSTATE))
    # Note: Slaves may enter OP slower than 250ms (Python scheduling, DC jitter, etc.), so extend wait and retry
    print("\nWaiting for slaves to enter OP state (extended wait, thread continuously sending Output PDO)...")
    max_attempts = 10  # Retry count
    result_state = None
    for attempt in range(max_attempts):
        result_state = master.state_check(pysoem.OP_STATE, timeout=5 * 50000)  # 5 * EC_TIMEOUTSTATE = 250ms
        master.read_state()
        all_in_op = all(slave.state == pysoem.OP_STATE for slave in master.slaves)
        if all_in_op and result_state == pysoem.OP_STATE:
            print(f"  ✓ Check {attempt + 1}: All slaves have entered OP state")
            break
        if attempt == max_attempts - 1:
            print(f"  ⚠ After {max_attempts} checks still not in OP (may enter later, thread still sending output)")
        else:
            time.sleep(0.1)  # Wait 100ms then retry
    
    # Read latest state
    master.read_state()
    
    if result_state == pysoem.OP_STATE:
        print(f"✓ State switched to OP: {pysoem.OP_STATE}")
        print("___________________________________________")
    else:
        print("⚠ State cannot switch to OP")
        print(f"  state_check returned state: {result_state} (Expected: {pysoem.OP_STATE})")
        
        # Print detailed information of all slaves (Reference: C++)
        for i, slave in enumerate(master.slaves):
            al_status = slave.al_status if hasattr(slave, 'al_status') else 0
            print(f"Slave {i} AL Status Code: {al_status}")
            print(f"  Current state: {get_state_name(slave.state)} (Value: 0x{slave.state:02x})")
            
            # If AL status code is not 0, display detailed information
            if al_status != 0:
                al_info = check_slave_al_status(slave)
                print(f"  {al_info}")
            
            # Print detailed state machine information for debugging
            print_slave_state_machine_info(master, i)
    
    # Read and display state of all slaves (Reference: C++)
    master.read_state()
    for i, slave in enumerate(master.slaves):
        print(f"Slave {i}: Type {slave.id}, Address 0x{i:02x}, State Machine Actual {slave.state}, Required {pysoem.OP_STATE}")
        print(f"Name: {slave.name}")
        print("___________________________________________")
    
    # Key: After entering OP, immediately set control word to 0x0080 (Fault Reset), start fault clear sequence
    # Reference C++ program STEP 8: rxpdo.controlword = 0x0080
    # Must start sending 0x0080 immediately after entering OP, not wait until cyclic_operation_cst starts
    if result_state == pysoem.OP_STATE:
        global _thread_controlword, _thread_target_torque, _thread_mode_of_operation
        print("\n✓ After entering OP, immediately set control word to 0x0080 (Fault Reset) to start fault clearing...")
        _thread_controlword = 0x0080  # Immediately start fault clearing
        _thread_target_torque = 0
        _thread_mode_of_operation = 10  # CST mode
        print("  ✓ Control word set to 0x0080, data exchange thread will immediately start sending fault clear command")
        # Wait several cycles, ensure fault clear command has been sent
        time.sleep(0.01)  # Wait 10ms, let thread send several times
    
    return result_state == pysoem.OP_STATE


def configure_cst_mode(master):
    """Configure CST (Cyclic Synchronous Torque) mode (Reference: C++ program eRob_CST.cpp STEP 9)"""
    print("\n__________STEP 9: Configure CST Mode__________")
    
    operation_mode = 10  # CST mode
    max_torque = 100  # Maximum torque limit
    torque_slope = 100  # Torque slope
    
    for i, slave in enumerate(master.slaves):
        try:
            print(f"\nConfiguring slave {i} ({slave.name}) CST mode...")
            
            # Reference C++: First disable motor
            control_word = 0x0000
            slave.sdo_write(0x6040, 0x00, control_word.to_bytes(2, 'little'))
            time.sleep(0.1)
            
            # Set operation mode to CST (Reference: C++)
            slave.sdo_write(0x6060, 0x00, operation_mode.to_bytes(1, 'little'))
            time.sleep(0.1)
            print(f"  ✓ Operation mode set to CST (10)")
            
            # Set maximum torque limit (Reference: C++)
            slave.sdo_write(0x6072, 0x00, max_torque.to_bytes(2, 'little', signed=True))
            print(f"  ✓ Maximum torque limit: {max_torque}")
            
            # Set torque slope (Reference: C++)
            try:
                slave.sdo_write(0x6087, 0x00, torque_slope.to_bytes(2, 'little', signed=True))
                print(f"  ✓ Torque slope: {torque_slope}")
            except Exception as e:
                print(f"  ⚠ Failed to set torque slope (may not be supported): {e}")
            
            time.sleep(0.1)
            
            # Verify mode (Reference: C++)
            actual_mode = slave.sdo_read(0x6061, 0x00, 1)
            if actual_mode:
                mode_val = int.from_bytes(actual_mode, 'little')
                print(f"  ✓ Verify operation mode: {mode_val} (Expected: {operation_mode})")
            
            print(f"  ✓ Slave {i} CST mode configuration completed")
            
        except Exception as e:
            print(f"  ⚠ Slave {i} CST mode configuration failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n✓ All slaves CST mode configuration completed")


def cyclic_operation_cst(master, duration=300, timeout_us=5000, cycle_time_ms=None):
    """Cyclic data exchange in CST mode (Reference: C++ program eRob_CST.cpp state machine control logic)
    
    Key: This function updates global variables _thread_controlword, _thread_target_torque, etc.,
    and data_exchange_worker thread actually sends data (Reference: C++ ecatthread thread).
    
    Args:
        master: EtherCAT master object
        duration: Running duration (seconds)
        timeout_us: Receive data timeout (microseconds)
        cycle_time_ms: Cycle time (milliseconds), if None then use global configuration ETHERCAT_CYCLE_TIME_MS
    """
    global _thread_controlword, _thread_target_torque, _thread_mode_of_operation
    
    # If cycle not specified, use global configuration
    if cycle_time_ms is None:
        cycle_time_ms = ETHERCAT_CYCLE_TIME_MS
    
    print(f"\n__________Start CST Mode Cyclic Data Exchange__________")
    print(f"Duration: {duration} seconds")
    print(f"State Machine Cycle: {cycle_time_ms} ms")
    print(f"Note: Actual data exchange is performed by data_exchange_worker thread ({ETHERCAT_CYCLE_TIME_MS} ms cycle)")
    
    # Confirm state before starting
    print("\nState confirmation before starting:")
    if not check_slave_states(master, show_all=False):
        print("⚠ Warning: Some slaves are not in OP state, data exchange may fail")
    
    # Diagnosis: Read Status Word and Error Code, check for faults
    print("\nDiagnosing slave status...")
    non_critical_error_codes = [0x730F]  # List of error codes that do not affect usage (e.g., low battery voltage)
    has_non_critical_error = False
    
    for i, slave in enumerate(master.slaves):
        try:
            with _data_exchange_lock:
                # Read Status Word
                if hasattr(slave, 'input') and slave.input and len(slave.input) >= 12:
                    statusword = int.from_bytes(slave.input[0:2], 'little')
                    print(f"Slave {i} Status Word: 0x{statusword:04x}")
                    
                    # Check if there is a fault
                    if statusword & 0x0008:  # Bit 3: Fault
                        print(f"  ⚠ Fault bit detected as set")
                        print(f"  Status Word bit analysis:")
                        print(f"    Bit 3 (Fault): {bool(statusword & 0x0008)}")
                        print(f"    Bit 6 (Switch on disabled): {bool(statusword & 0x0040)}")
                        
                        # Read Error Code
                        try:
                            error_code_data = slave.sdo_read(0x603F, 0x00, 2)
                            if error_code_data:
                                error_code = int.from_bytes(error_code_data, 'little')
                                print(f"  Error Code (0x603F): 0x{error_code:04x}")
                                if error_code != 0:
                                    if error_code in non_critical_error_codes:
                                        print(f"  ℹ Error code 0x{error_code:04x} does not affect usage (e.g., low battery voltage), will continue enable sequence")
                                        has_non_critical_error = True
                                    else:
                                        print(f"  ⚠ Slave error code: 0x{error_code:04x}")
                        except:
                            pass
                        
                        if not has_non_critical_error:
                            print(f"  → Will execute fault clear sequence first")
        except:
            pass
    
    # Initialize global variables (Reference: C++ rxpdo.controlword = 0x0080)
    # Note: If fault detected, need to clear fault first
    # Key: If 0x0080 is already set in set_slaves_to_op_state_cst, do not overwrite here
    # Check current control word, if already 0x0080, already clearing fault, do not reset
    if _thread_controlword != 0x0080:
        print("  Setting control word to 0x0080 (Fault Reset) to start fault clearing...")
        _thread_controlword = 0x0080  # Fault Reset
        _thread_target_torque = 0
        _thread_mode_of_operation = 10  # CST mode
    else:
        print("  Control word is already 0x0080 (Fault Reset), continuing fault clear sequence...")
    
    # Key: After entering OP, wait for system to stabilize before starting enable sequence
    # At 1ms cycle, motor may need more time to respond, so wait first
    # Note: Enable sequence already set 0x0080 in set_slaves_to_op_state_cst, thread is already sending
    # Wait here to let system stabilize, then start complete state machine sequence
    print("\nWaiting for system to stabilize (after entering OP, give motor some time to prepare)...")
    # Adjust wait time based on cycle time: wait longer at 1ms cycle, can be shorter at 2ms cycle
    wait_time_after_op = max(0.1, ETHERCAT_CYCLE_TIME_MS / 10.0)  # At least 100ms, or 10 times the cycle
    time.sleep(wait_time_after_op)
    print(f"✓ Waited {wait_time_after_op*1000:.0f}ms, starting enable sequence (cycle: {ETHERCAT_CYCLE_TIME_MS}ms)")
    
    start_time = time.time()
    step = 0  # State machine step (Reference: C++ int step = 0)
    print_count = 0  # For controlling print frequency
    fault_cleared = False  # Whether fault has been cleared
    
    try:
        # Reference C++ state machine logic (in ecatthread)
        # Key: Update global variables, let data_exchange_worker thread send
        # In C++: Loop cycle is 1ms, step increments by 1 each time until 8000
        # In Python: data_exchange_worker thread cycle is 1ms, state machine update frequency matches
        # To be consistent with C++, we update state machine every 1ms
        while time.time() - start_time < duration:
            # State machine control logic (Reference: C++ step <= 4000, 5300, 6000, 7000)
            # Increase duration of each stage to ensure motor has enough time to respond
            # In C++: step increments by 1 in each loop (if step < 8000)
            # Here we use step variable, increment every 1ms (corresponding to C++ 1ms cycle)
            
            # Read current Status Word, check fault status
            current_statusword = None
            try:
                with _data_exchange_lock:
                    if hasattr(master.slaves[0], 'input') and master.slaves[0].input and len(master.slaves[0].input) >= 12:
                        current_statusword = int.from_bytes(master.slaves[0].input[0:2], 'little')
            except:
                pass
            
            # Fault clear stage: Need longer time to ensure fault is cleared
            # If non-critical error (e.g., low battery voltage), can shorten fault clear time
            # Key: Adjust duration based on cycle time
            # At 1ms cycle, need more steps to achieve same time (e.g., 4000 steps = 4 seconds)
            # At 2ms cycle, need fewer steps to achieve same time (e.g., 2000 steps = 4 seconds)
            base_duration_ms = 4000  # Base duration (milliseconds)
            base_duration_steps = int(base_duration_ms / ETHERCAT_CYCLE_TIME_MS)  # Calculate step count based on cycle
            
            fault_reset_duration = int(base_duration_steps * 0.5) if has_non_critical_error else base_duration_steps
            
            # State machine control logic (Reference: C++ step <= 4000, 5300, 6000, 7000)
            # Key: Must be based on offset of fault_reset_duration, ensure sequential execution
            # Debug: Record step value before state machine judgment
            prev_controlword = _thread_controlword
            
            if step <= fault_reset_duration:
                # 0x0080: Fault Reset (Reference: C++ step <= 4000)
                _thread_controlword = 0x0080
                _thread_target_torque = 0
                
                # Check if fault has been cleared
                if current_statusword is not None:
                    if not (current_statusword & 0x0008):  # Fault bit cleared
                        if not fault_cleared:
                            print(f"✓ Fault cleared (Status Word: 0x{current_statusword:04x})")
                            fault_cleared = True
                    elif has_non_critical_error and step > fault_reset_duration * 0.5:
                        # For non-critical errors, continue enable sequence even if fault bit not cleared
                        if not fault_cleared:
                            print(f"ℹ Non-critical error detected, will continue enable sequence even if fault bit not cleared (Status Word: 0x{current_statusword:04x})")
                            fault_cleared = True  # Mark as processed, continue enable sequence
            elif step <= fault_reset_duration + int(1000 / ETHERCAT_CYCLE_TIME_MS):  # Shutdown stage: +1000ms
                # 0x0006: Shutdown (Reference: C++ step <= 5300, but using offset here)
                _thread_controlword = 0x0006
                _thread_target_torque = 0
            elif step <= fault_reset_duration + int(2000 / ETHERCAT_CYCLE_TIME_MS):  # Switch On stage: +2000ms
                # 0x0007: Switch On (Reference: C++ step <= 6000, but using offset here)
                _thread_controlword = 0x0007
                _thread_target_torque = 0
            elif step <= fault_reset_duration + int(3000 / ETHERCAT_CYCLE_TIME_MS):  # Enable Operation stage: +3000ms
                # 0x000F: Enable Operation (Reference: C++ step <= 7000, but using offset here)
                _thread_controlword = 0x000F
                _thread_target_torque = 0
            else:
                # 0x000F: Enable Operation + Target Torque (Reference: C++ else)
                # When step > fault_reset_duration + 3000, enter normal operation state
                _thread_controlword = 0x000F
                _thread_target_torque = 50  # Set target torque (Reference: C++ 50, currently set to 0 for testing)
            
            # Debug: If control word changes unexpectedly, print warning
            if prev_controlword != _thread_controlword and print_count == 0:
                print(f"DEBUG: step={step}, control word changed from 0x{prev_controlword:04x} to 0x{_thread_controlword:04x}")
            
            _thread_mode_of_operation = 10  # CST mode (Reference: C++ rxpdo.mode_of_operation = 10)
            
            # Print status every 100 cycles (Reference: C++ dorun % 100 == 0)
            # Note: Read slave data through lock here to avoid conflict with thread
            print_count += 1
            if print_count >= 100:  # Print every 100 state machine cycles
                print_count = 0
                try:
                    with _data_exchange_lock:
                        # Read slave data (Reference: C++ structure txpdo_t)
                        if hasattr(master.slaves[0], 'input') and master.slaves[0].input and len(master.slaves[0].input) >= 12:
                            statusword = int.from_bytes(master.slaves[0].input[0:2], 'little')
                            actual_position = int.from_bytes(master.slaves[0].input[2:6], 'little', signed=True)
                            actual_velocity = int.from_bytes(master.slaves[0].input[6:10], 'little', signed=True)
                            actual_torque = int.from_bytes(master.slaves[0].input[10:12], 'little', signed=True)
                            
                            # Read actually sent PDO data (verify if sent correctly)
                            sent_controlword = None
                            sent_target_torque = None
                            sent_mode = None
                            if hasattr(master.slaves[0], 'output') and master.slaves[0].output and len(master.slaves[0].output) >= 6:
                                sent_controlword = int.from_bytes(master.slaves[0].output[0:2], 'little')
                                sent_target_torque = int.from_bytes(master.slaves[0].output[2:4], 'little', signed=True)
                                sent_mode = master.slaves[0].output[4]
                            
                            # Parse key bits of Status Word
                            fault_bit = bool(statusword & 0x0008)
                            enabled_bit = bool(statusword & 0x0004)
                            switched_on_bit = bool(statusword & 0x0002)
                            ready_to_switch_on = bool(statusword & 0x0001)
                            
                            status_info = f"SW=0x{statusword:04x}"
                            if fault_bit:
                                status_info += " [FAULT]"
                            if enabled_bit:
                                status_info += " [ENABLED]"
                            if switched_on_bit:
                                status_info += " [SW_ON]"
                            if ready_to_switch_on:
                                status_info += " [READY]"
                            
                            # Print sent PDO and received status (Reference: C++ print format)
                            # C++: printf("Status: SW=0x%04x, pos=%d, vel=%d, target_torque=%d, mode=%d\n", ...)
                            if sent_controlword is not None:
                                print(f"TX: CW=0x{sent_controlword:04x} TQ={sent_target_torque:4d} MODE={sent_mode:2d} | RX: {status_info}, pos={actual_position:8d}, vel={actual_velocity:6d}, torque={actual_torque:4d}, step={step}")
                            else:
                                print(f"TX: CW=0x{_thread_controlword:04x} TQ={_thread_target_torque:4d} MODE={_thread_mode_of_operation:2d} | RX: {status_info}, pos={actual_position:8d}, vel={actual_velocity:6d}, torque={actual_torque:4d}, step={step}")
                except Exception as e:
                    pass  # Ignore read errors, continue running
            
            # Control state machine update frequency (Reference: C++ increment when step < 8000)
            # Use unified cycle configuration
            # Note: Due to extended stage times, step upper limit also increased accordingly
            if step < 25000:  # Increase upper limit to match extended stages
                step += 1
            
            # Wait one cycle (use unified cycle configuration)
            time.sleep(ETHERCAT_CYCLE_TIME_MS / 1000.0)
            
    except KeyboardInterrupt:
        print("\nUser interrupted operation")
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
    
    # Confirm state again at end
    print("\nState confirmation at end:")
    check_slave_states(master, show_all=True)
    
    # Display final statistics
    elapsed_time = time.time() - start_time
    print(f"\nCyclic data exchange completed:")
    print(f"  Running time: {elapsed_time:.2f} seconds")
    print(f"  Final state machine step: {step}")
    print(f"  Final control word: 0x{_thread_controlword:04x}")
    print(f"  Final target torque: {_thread_target_torque}")


def cyclic_operation(master, duration=10, timeout_us=5000):
    """Cyclic data exchange (PDO communication)
    
    Args:
        master: EtherCAT master object
        duration: Running duration (seconds)
        timeout_us: Receive data timeout (microseconds), default 5000 microseconds (5 milliseconds)
    """
    print(f"\nStarting cyclic data exchange, duration {duration} seconds...")
    print(f"Receive timeout setting: {timeout_us} microseconds ({timeout_us/1000:.1f} milliseconds)")
    
    # Confirm state before starting
    print("State confirmation before starting:")
    if not check_slave_states(master, show_all=False):
        print("⚠ Warning: Some slaves are not in OP state, data exchange may fail")
    
    start_time = time.time()
    cycle_count = 0
    success_count = 0
    timeout_count = 0
    low_wkc_count = 0
    last_state_check_time = start_time
    last_stats_time = start_time
    state_check_interval = 2.0  # Check state every 2 seconds
    stats_interval = 5.0  # Display statistics every 5 seconds
    
    try:
        while time.time() - start_time < duration:
            # Send output data to slaves
            send_result = master.send_processdata()
            
            if send_result == 0:
                print("⚠ Warning: send_processdata returned 0, configuration may not be complete")
            
            # Receive input data from slaves (increased timeout)
            wkc = master.receive_processdata(timeout=timeout_us)
            
            # Analyze WKC value
            if wkc == -1:
                # Timeout
                timeout_count += 1
                # Reduce print frequency to avoid screen flooding
                if timeout_count % 100 == 0:
                    print(f"⚠ Timeout warning: {timeout_count} timeouts occurred (WKC: {wkc})")
                    # Check slave state
                    master.read_state()
                    for slave in master.slaves:
                        if slave.state != pysoem.OP_STATE:
                            print(f"  ⚠ Slave state abnormal: {get_state_name(slave.state)}")
            elif wkc < master.expected_wkc:
                # WKC less than expected value
                low_wkc_count += 1
                if low_wkc_count % 50 == 0:
                    print(f"⚠ WKC abnormal: {low_wkc_count} times (WKC: {wkc}/{master.expected_wkc})")
            elif wkc >= master.expected_wkc:
                # Normal
                cycle_count += 1
                success_count += 1
                
                # Can process input/output data here
                # For example: Read slave input data
                for i, slave in enumerate(master.slaves):
                    try:
                        # Read input data
                        if hasattr(slave, 'input') and slave.input and len(slave.input) > 0:
                            input_data = slave.input
                            # Process input data...
                            # For example: input_value = int.from_bytes(input_data[:2], 'little')
                            pass
                        
                        # Write output data
                        if hasattr(slave, 'output') and slave.output and len(slave.output) > 0:
                            output_data = slave.output
                            # Set output data...
                            # For example: slave.output = b'\x00\x01\x02\x03'
                            pass
                    except Exception as e:
                        # Ignore single slave data processing errors
                        pass
                
                # Print every 1000 cycles
                if cycle_count % 1000 == 0:
                    print(f"Executed {cycle_count} cycles (WKC: {wkc}/{master.expected_wkc})")
            
            # Periodically display statistics
            current_time = time.time()
            if current_time - last_stats_time >= stats_interval:
                elapsed = current_time - start_time
                success_rate = (success_count / (success_count + timeout_count + low_wkc_count) * 100) if (success_count + timeout_count + low_wkc_count) > 0 else 0
                print(f"\n[Statistics] Running time: {elapsed:.1f}s | Success: {success_count} | Timeout: {timeout_count} | WKC abnormal: {low_wkc_count} | Success rate: {success_rate:.1f}%")
                last_stats_time = current_time
            
            # Periodically check slave state (every 2 seconds)
            if current_time - last_state_check_time >= state_check_interval:
                master.read_state()
                all_in_op = True
                for slave in master.slaves:
                    if slave.state != pysoem.OP_STATE:
                        all_in_op = False
                        break
                
                if not all_in_op:
                    print(f"\n⚠ State check: Some slaves are not in OP state")
                    check_slave_states(master, show_all=True)
                
                last_state_check_time = current_time
            
            # Brief delay (use unified cycle configuration)
            # If timeout is frequent, can increase delay
            time.sleep(ETHERCAT_CYCLE_TIME_MS / 1000.0)
            
    except KeyboardInterrupt:
        print("\nUser interrupted operation")
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
    
    # Confirm state again at end
    print("\nState confirmation at end:")
    check_slave_states(master, show_all=True)
    
    # Display final statistics
    total_attempts = success_count + timeout_count + low_wkc_count
    success_rate = (success_count / total_attempts * 100) if total_attempts > 0 else 0
    print(f"\nCyclic data exchange completed:")
    print(f"  Total cycles: {cycle_count}")
    print(f"  Success count: {success_count}")
    print(f"  Timeout count: {timeout_count}")
    print(f"  WKC abnormal count: {low_wkc_count}")
    print(f"  Success rate: {success_rate:.2f}%")
    
    # Give suggestions
    if timeout_count > success_count * 0.1:  # Timeout exceeds 10%
        print(f"\nSuggestions:")
        print(f"  - Current timeout setting: {timeout_us} microseconds ({timeout_us/1000:.1f} milliseconds)")
        print(f"  - Suggest increasing timeout time or check network connection")
        print(f"  - Can try increasing timeout_us parameter of cyclic_operation()")


def set_slaves_to_safeop_state(master):
    """Set slaves to enter SAFEOP state"""
    print("\nSetting slaves to enter SAFEOP state...")
    
    # Display state before setting
    print("State before setting:")
    check_slave_states(master, show_all=True)
    
    # Set each slave's state to SAFEOP_STATE
    for slave in master.slaves:
        slave.state = pysoem.SAFEOP_STATE
    
    master.state = pysoem.SAFEOP_STATE
    master.write_state()
    result_state = master.state_check(pysoem.SAFEOP_STATE, timeout=50000)
    
    # Read and display actual state
    master.read_state()
    
    # Display state after setting
    print("\nState after setting:")
    check_slave_states(master, show_all=True)
    
    if result_state == pysoem.SAFEOP_STATE:
        print("\n✓ All slaves have entered SAFEOP state")
    else:
        print(f"\n⚠ Warning: State check result: {get_state_name(result_state)}")


def main():
    """Main function"""
    print("=" * 60)
    print("pysoem EtherCAT Slave Driver Example")
    print("=" * 60)
    
    # 1. Find network adapters
    adapters = find_adapters()
    if not adapters:
        print("Error: No available network adapters found")
        return
    
    # Select first valid adapter (excluding loopback)
    if not adapters:
        print("Error: No available network adapters found")
        return
    
    selected_adapter = adapters[0]
    print(f"\nSelected adapter: {selected_adapter.name}")
    
    # If loopback interface, give warning
    if selected_adapter.name == 'lo':
        print("Warning: Loopback interface selected, EtherCAT communication may not work properly")
        print("Please ensure your EtherCAT network card is connected and available")
    
    # 2. Check permissions
    has_root = check_permissions()
    
    # 3. Create master and open adapter
    master = pysoem.Master()
    
    try:
        print(f"\nOpening adapter: {selected_adapter.name}")
        try:
            master.open(selected_adapter.name)
        except ConnectionError as e:
            if "could not open interface" in str(e):
                print(f"\nError: Unable to open network interface '{selected_adapter.name}'")
                print("\nPossible reasons:")
                print("  1. Root privileges required - please run this script with sudo")
                print("  2. Network interface is occupied by another program")
                print("  3. Network interface is not properly configured")
                print("\nSolution:")
                print(f"  sudo python3 {sys.argv[0]}")
                raise
            else:
                raise
        
        # 4. Scan slaves (STEP 1)
        if not scan_slaves(master):
            print("Error: No slave devices found")
            print("\nTips:")
            print("  - Please ensure EtherCAT slave devices are properly connected")
            print("  - Check network cable connections")
            print("  - Confirm slave devices are powered on")
            master.close()
            return
        
        # 5. Enter PREOP state (STEP 2)
        if not enter_preop_state(master):
            print("⚠ Warning: Unable to enter PREOP state, cannot continue")
            master.close()
            return
        
        # 6. Configure PDO mapping (STEP 3)
        if not configure_pdo_mapping(master):
            print("⚠ Warning: PDO mapping configuration failed")
            master.close()
            return
        
        # 7. Configure slaves and perform data mapping (STEP 4)
        if not configure_slaves(master):
            print("⚠ Warning: Slave configuration failed, cannot continue")
            master.close()
            return
        
        # 8. Enter SAFEOP state (STEP 5)
        if not enter_safeop_state(master):
            print("⚠ Warning: Unable to enter SAFEOP state, cannot continue")
            master.close()
            return
        
        # 9. Start data exchange (Reference: C++ program eRob_CST.cpp STEP 6)
        # Key: Before entering OP, need to continuously perform data exchange
        start_data_exchange_thread(master)
        
        # 10. Set slaves to enter OP state (Reference: C++ program eRob_CST.cpp STEP 8)
        set_slaves_to_op_state_cst(master)
        
        # 10. Configure CST mode (Reference: C++ program eRob_CST.cpp STEP 9, configure in OP state)
        configure_cst_mode(master)
        
        # 11. Execute CST mode cyclic data exchange (duration increased, default 300 seconds)
        # Note: If timeout occurs (WKC=-1), can increase timeout_us parameter
        # Note: Data exchange thread is already running, cyclic_operation_cst will take over data exchange
        # Use global cycle configuration (do not pass cycle_time_ms parameter, use default global configuration)
        cyclic_operation_cst(master, duration=300, timeout_us=5000)
        
        # 12. Stop data exchange thread
        stop_data_exchange_thread()
        
        # 13. Set slaves to enter SAFEOP state
        set_slaves_to_safeop_state(master)
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 9. Close master connection
        print("\nClosing master connection...")
        try:
            master.close()
        except:
            pass  # If already closed or not opened, ignore error
        print("Program ended")


if __name__ == "__main__":
    main()

