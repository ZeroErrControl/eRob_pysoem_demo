/* 
 * This program is an EtherCAT master implementation that initializes and configures EtherCAT slaves,
 * manages their states, and handles real-time data exchange. It includes functions for setting up 
 * PDO mappings, synchronizing time with the distributed clock, and controlling servomotors in 
 * various operational modes. The program also features multi-threading for real-time processing 
 * and monitoring of the EtherCAT network.
 */
//#include <QCoreApplication>


#include <stdio.h>
#include <string.h>
#include "ethercat.h"
#include <iostream>
#include <inttypes.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>

#include <sys/time.h>
#include <pthread.h>
#include <math.h>

#include <chrono>
#include <ctime>

#include <iostream>
#include <cstdint>

#include <sched.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>

// Global variables for EtherCAT communication
char IOmap[4096]; // I/O mapping for EtherCAT
int expectedWKC; // Expected Work Counter
boolean needlf; // Flag to indicate if a line feed is needed
volatile int wkc; // Work Counter (volatile to ensure it is updated correctly in multi-threaded context)
boolean inOP; // Flag to indicate if the system is in operational state
uint8 currentgroup = 0; // Current group for EtherCAT communication
int dorun = 0; // Flag to indicate if the thread should run
bool start_ecatthread_thread; // Flag to start the EtherCAT thread
int ctime_thread; // Cycle time for the EtherCAT thread

int64 toff, gl_delta; // Time offset and global delta for synchronization

// Function prototypes for EtherCAT thread functions
OSAL_THREAD_FUNC ecatcheck(void *ptr); // Function to check the state of EtherCAT slaves
OSAL_THREAD_FUNC_RT ecatthread(void *ptr); // Real-time EtherCAT thread function

// Thread handles for the EtherCAT threads
OSAL_THREAD_HANDLE thread1; // Handle for the EtherCAT check thread
OSAL_THREAD_HANDLE thread2; // Handle for the real-time EtherCAT thread

// Function to synchronize time with the EtherCAT distributed clock
void ec_sync(int64 reftime, int64 cycletime, int64 *offsettime);
// Function to add nanoseconds to a timespec structure
void add_timespec(struct timespec *ts, int64 addtime);

// Define constants for stack size and timing
#define stack64k (64 * 1024) // Stack size for threads
#define NSEC_PER_SEC 1000000000   // Number of nanoseconds in one second
#define EC_TIMEOUTMON 5000        // Timeout for monitoring in microseconds
#define MAX_VELOCITY 30000        // Reduced maximum velocity (from 200000 to 30000)
#define MAX_ACCELERATION 50000    // Reduced maximum acceleration (from 500000 to 50000)

// Conversion units for the servomotor
float Cnt_to_deg = 0.000686645; // Conversion factor from counts to degrees
int8_t SLAVE_ID; // Slave ID for EtherCAT communication

// Structure for RXPDO (Control data sent to slave)
typedef struct {
    uint16_t controlword;      // 0x6040:0, 16 bits
    int32_t target_position;   // 0x607A:0, 32 bits
    uint8_t mode_of_operation; // 0x6060:0, 8 bits
    uint8_t padding;           // 8 bits padding for alignment
} __attribute__((__packed__)) rxpdo_t;

// Structure for TXPDO (Status data received from slave)
typedef struct {
    uint16_t statusword;      // 0x6041:0, 16 bits
    int32_t actual_position;  // 0x6064:0, 32 bits
    int32_t actual_velocity;  // 0x606C:0, 32 bits
    int16_t actual_torque;    // 0x6077:0, 16 bits
} __attribute__((__packed__)) txpdo_t;

// Add these global variables after the other global declarations
volatile int target_position = 0;
pthread_mutex_t target_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t target_position_cond = PTHREAD_COND_INITIALIZER;
bool target_updated = false;
int32_t received_target = 0;

// Add in the global variable declaration section at the beginning of the file
rxpdo_t rxpdo;  // Global variable, used for sending data to slaves
txpdo_t txpdo;  // Global variable, used for receiving data from slaves

// 在全局变量区域添加
struct MotorStatus {
    bool is_operational;
    uint16_t status_word;
    int32_t actual_position;
    int32_t actual_velocity;
    int16_t actual_torque;
} motor_status;


void update_motor_status(int slave_id);  // Add function declaration

// 在文件开头，其他宏定义之后添加
#undef MAX_VELOCITY  // Ensure there are no naming conflicts
#undef MAX_ACCELERATION

// 在全局变量声明区域添加
struct MotionPlanner {
    int32_t start_position;    // Start position
    int32_t target_position;   // Final target position
    int32_t smooth_target;     // Smoothed target position for transition
    int32_t current_position;  // Current planned position
    double current_velocity;   // Current velocity
    double start_time;         // Start time
    double total_time;         // Total time
    double current_time;       // Current time
    bool is_moving;            // Movement state
    
    // Motion parameters
    static constexpr double MAX_VELOCITY = 50000.0;     // Maximum velocity limit
    static constexpr double CYCLE_TIME = 0.0005;          // Cycle time (1ms)
    static constexpr double SMOOTH_FACTOR = 0.002;        // Smoothing factor for target position

    // Quintic polynomial coefficients
    double a0, a1, a2, a3, a4, a5;

    MotionPlanner() : start_position(0), target_position(0), smooth_target(0),
                      current_position(0), current_velocity(0.0),
                      start_time(0.0), total_time(0.0), current_time(0.0),
                      is_moving(false) {}
};

// Define static member variables
constexpr double MotionPlanner::MAX_VELOCITY;
constexpr double MotionPlanner::CYCLE_TIME;
constexpr double MotionPlanner::SMOOTH_FACTOR;

// Global variable
MotionPlanner g_motion_planner;

// Function declaration
int32_t plan_trajectory(MotionPlanner* planner, int32_t actual_position);

// 在全局变量声明区域添加这些变量（在文件开头其他全局变量之后）
bool delay_test_enabled = false;
bool delay_test_active = false;
int delay_test_start_cycle = 5000;  // Start delay test after this many cycles
int delay_test_duration = 1000;     // Run delay test for this many cycles
int delay_test_counter = 0;

// 在其他函数声明之后，添加这些函数声明
void start_delay_test(int start_after_cycles, int test_duration);
void* start_server(void* arg);

//##################################################################################################
// Function: Set the CPU affinity for a thread
void set_thread_affinity(pthread_t thread, int cpu_core) {
    cpu_set_t cpuset; // CPU set to specify which CPUs the thread can run on
    CPU_ZERO(&cpuset); // Clear the CPU set
    CPU_SET(cpu_core, &cpuset); // Add the specified CPU core to the set

    // Set the thread's CPU affinity
    int result = pthread_setaffinity_np(thread, sizeof(cpu_set_t), &cpuset);
    if (result != 0) {
        printf("Unable to set CPU affinity for thread %d\n", cpu_core); // Error message if setting fails
    } else {
        printf("Thread successfully bound to CPU %d\n", cpu_core); // Confirmation message if successful
    }
}

//##################################################################################################
// Function prototype for the EtherCAT test function
int erob_test();

uint16_t data_R;

int erob_test() {
    int rdl; // Variable to hold read data length
    SLAVE_ID = 1; // Set the slave ID to 1
    int i, j, oloop, iloop, chk; // Loop control variables

    // 1. Call ec_config_init() to move from INIT to PRE-OP state.
    printf("__________STEP 1___________________\n");
    // Initialize EtherCAT master on the specified network interface
    if (ec_init("enp58s0") <= 0) {
        printf("Error: Could not initialize EtherCAT master!\n");
        printf("No socket connection on Ethernet port. Execute as root.\n");
        printf("___________________________________________\n");
        return -1; // Return error if initialization fails
    }
    printf("EtherCAT master initialized successfully.\n");
    printf("___________________________________________\n");

    // Search for EtherCAT slaves on the network
    if (ec_config_init(FALSE) <= 0) {
        printf("Error: Cannot find EtherCAT slaves!\n");
        printf("___________________________________________\n");
        ec_close(); // Close the EtherCAT connection
        return -1; // Return error if no slaves are found
    }
    printf("%d slaves found and configured.\n", ec_slavecount); // Print the number of slaves found
    printf("___________________________________________\n");

    // 2. Change to pre-operational state to configure the PDO registers
    printf("__________STEP 2___________________\n");

    // Check if the slave is ready to map
    ec_readstate(); // Read the state of the slaves

    for(int i = 1; i <= ec_slavecount; i++) { // Loop through each slave
        if(ec_slave[i].state != EC_STATE_PRE_OP) { // If the slave is not in PRE-OP state
            // Print the current state and status code of the slave
            printf("Slave %d State=0x%2.2x StatusCode=0x%4.4x : %s\n",
                   i, ec_slave[i].state, ec_slave[i].ALstatuscode, ec_ALstatuscode2string(ec_slave[i].ALstatuscode));
            printf("\nRequest init state for slave %d\n", i); // Request to change the state to INIT
            ec_slave[i].state = EC_STATE_INIT; // Set the slave state to INIT
            printf("___________________________________________\n");
        } else { // If the slave is in PRE-OP state
            ec_slave[0].state = EC_STATE_PRE_OP; // Set the first slave to PRE-OP state
            /* Request EC_STATE_PRE_OP state for all slaves */
            ec_writestate(0); // Write the state change to the slave
            /* Wait for all slaves to reach the PRE-OP state */
            if ((ec_statecheck(0, EC_STATE_PRE_OP,  3 * EC_TIMEOUTSTATE)) == EC_STATE_PRE_OP) {
                printf("State changed to EC_STATE_PRE_OP: %d \n", EC_STATE_PRE_OP);
                printf("___________________________________________\n");
            } else {
                printf("State EC_STATE_PRE_OP cannot be changed in step 2\n");
                return -1; // Return error if state change fails
            }
        }
    }

//##################################################################################################
    //3.- Map RXPOD
    printf("__________STEP 3___________________\n");

    // Clear RXPDO mapping
    int retval = 0; // Variable to hold the return value of SDO write operations
    uint16 map_1c12; // Variable to hold the mapping for PDO
    uint8 zero_map = 0; // Variable to clear the PDO mapping
    uint32 map_object; // Variable to hold the mapping object
    uint16 clear_val = 0x0000; // Value to clear the mapping

    for(int i = 1; i <= ec_slavecount; i++) { // Loop through each slave
        // 1. First, disable PDO
        retval += ec_SDOwrite(i, 0x1600, 0x00, FALSE, sizeof(zero_map), &zero_map, EC_TIMEOUTSAFE);
        
        // 2. Configure new PDO mapping
        // Control Word
        map_object = 0x60400010;  // 0x6040:0 Control Word, 16 bits
        retval += ec_SDOwrite(i, 0x1600, 0x01, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);
        
        // Target Position
        map_object = 0x607A0020;  // 0x607A:0 Target Position, 32 bits
        retval += ec_SDOwrite(i, 0x1600, 0x02, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);
        
        // Mode of Operation
        map_object = 0x60600008;  // 0x6060:0 Mode of Operation, 8 bits
        retval += ec_SDOwrite(i, 0x1600, 0x03, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);
        
        // Padding (8 bits)
        map_object = 0x00000008;  // 8 bits padding
        retval += ec_SDOwrite(i, 0x1600, 0x04, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);
        
        // Set number of mapped objects
        uint8 map_count = 4;
        retval += ec_SDOwrite(i, 0x1600, 0x00, FALSE, sizeof(map_count), &map_count, EC_TIMEOUTSAFE);
        
        // 4. Configure RXPDO allocation
        clear_val = 0x0000; // Clear the mapping
        retval += ec_SDOwrite(i, 0x1c12, 0x00, FALSE, sizeof(clear_val), &clear_val, EC_TIMEOUTSAFE);
        map_1c12 = 0x1600; // Set the mapping to the new PDO
        retval += ec_SDOwrite(i, 0x1c12, 0x01, FALSE, sizeof(map_1c12), &map_1c12, EC_TIMEOUTSAFE);
        map_1c12 = 0x0001; // Set the mapping index
        retval += ec_SDOwrite(i, 0x1c12, 0x00, FALSE, sizeof(map_1c12), &map_1c12, EC_TIMEOUTSAFE);
    }

    printf("PDO mapping configuration result: %d\n", retval);
    if (retval < 0) {
        printf("PDO mapping failed\n");
        return -1;
    }

    printf("RXPOD Mapping set correctly.\n");
    printf("___________________________________________\n");

    //........................................................................................
    // Map TXPOD
    retval = 0;
    uint16 map_1c13;
    for(int i = 1; i <= ec_slavecount; i++) {
        // First, clear the TXPDO mapping
        clear_val = 0x0000;
        retval += ec_SDOwrite(i, 0x1A00, 0x00, FALSE, sizeof(clear_val), &clear_val, EC_TIMEOUTSAFE);

        // Configure TXPDO mapping entries
        // Status Word (0x6041:0, 16 bits)
        map_object = 0x60410010;
        retval += ec_SDOwrite(i, 0x1A00, 0x01, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);

        // Actual Position (0x6064:0, 32 bits)
        map_object = 0x60640020;
        retval += ec_SDOwrite(i, 0x1A00, 0x02, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);

        // Actual Velocity (0x606C:0, 32 bits)
        map_object = 0x606C0020;
        retval += ec_SDOwrite(i, 0x1A00, 0x03, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);

        // Actual Torque (0x6077:0, 16 bits)
        map_object = 0x60770010;
        retval += ec_SDOwrite(i, 0x1A00, 0x04, FALSE, sizeof(map_object), &map_object, EC_TIMEOUTSAFE);

        // Set the number of mapped objects (4 objects)
        uint8 map_count = 4;
        retval += ec_SDOwrite(i, 0x1A00, 0x00, FALSE, sizeof(map_count), &map_count, EC_TIMEOUTSAFE);

        // Configure TXPDO assignment
        // First, clear the assignment
        clear_val = 0x0000;
        retval += ec_SDOwrite(i, 0x1C13, 0x00, FALSE, sizeof(clear_val), &clear_val, EC_TIMEOUTSAFE);

        // Assign TXPDO to 0x1A00
        map_1c13 = 0x1A00;
        retval += ec_SDOwrite(i, 0x1C13, 0x01, FALSE, sizeof(map_1c13), &map_1c13, EC_TIMEOUTSAFE);

        // Set the number of assigned PDOs (1 PDO)
        map_1c13 = 0x0001;
        retval += ec_SDOwrite(i, 0x1C13, 0x00, FALSE, sizeof(map_1c13), &map_1c13, EC_TIMEOUTSAFE);
    }

    printf("Slave %d TXPDO mapping configuration result: %d\n", SLAVE_ID, retval);

    if (retval < 0) {
        printf("TXPDO Mapping failed\n");
        printf("___________________________________________\n");
        return -1;
    }

    printf("TXPDO Mapping set successfully\n");
    printf("___________________________________________\n");

   //##################################################################################################

    //4.- Set ecx_context.manualstatechange = 1. Map PDOs for all slaves by calling ec_config_map().
   printf("__________STEP 4___________________\n");

   ecx_context.manualstatechange = 1; //Disable automatic state change
   osal_usleep(1e6); //Sleep for 1 second

    uint8 WA = 0; //Variable for write access
    uint8 my_RA = 0; //Variable for read access
    uint32 TIME_RA; //Variable for time read access

    // Print the information of the slaves found
    for (int i = 1; i <= ec_slavecount; i++) {
       // (void)ecx_FPWR(ecx_context.port, i, ECT_REG_DCSYNCACT, sizeof(WA), &WA, 5 * EC_TIMEOUTRET);
        printf("Name: %s\n", ec_slave[i].name); //Print the name of the slave
        printf("Slave %d: Type %d, Address 0x%02x, State Machine actual %d, required %d\n", 
               i, ec_slave[i].eep_id, ec_slave[i].configadr, ec_slave[i].state, EC_STATE_INIT);
        printf("___________________________________________\n");
        ecx_dcsync0(&ecx_context, i, TRUE, 500000, 0);  //Synchronize the distributed clock for the slave
    }

    // Map the configured PDOs to the IOmap
    ec_config_map(&IOmap);

    printf("__________STEP 5___________________\n");

    // Ensure all slaves are in PRE-OP state
    for(int i = 1; i <= ec_slavecount; i++) {
        if(ec_slave[i].state != EC_STATE_PRE_OP) { // Check if the slave is not in PRE-OP state
            printf("Slave %d not in PRE-OP state. Current state: %d\n", i, ec_slave[i].state);
            return -1; // Return error if any slave is not in PRE-OP state
        }
    }

    // Configure Distributed Clock (DC)
    ec_configdc(); // Set up the distributed clock for synchronization

    // Request to switch to SAFE-OP state
    ec_slave[0].state = EC_STATE_SAFE_OP; // Set the first slave to SAFE-OP state
    ec_writestate(0); // Write the state change to the slave

    // Wait for the state transition
    if (ec_statecheck(0, EC_STATE_SAFE_OP, EC_TIMEOUTSTATE * 4) == EC_STATE_SAFE_OP) {
        printf("Successfully changed to SAFE_OP state\n"); // Confirm successful state change
    } else {
        printf("Failed to change to SAFE_OP state\n");
        return -1; // Return error if state change fails
    }

    // Calculate the expected Work Counter (WKC)
    expectedWKC = (ec_group[0].outputsWKC * 2) + ec_group[0].inputsWKC; // Calculate expected WKC based on outputs and inputs
    printf("Calculated workcounter %d\n", expectedWKC);

    // Read and display basic status information of the slaves
    ec_readstate(); // Read the state of all slaves
    for(int i = 1; i <= ec_slavecount; i++) {
        printf("Slave %d\n", i);
        printf("  State: %02x\n", ec_slave[i].state); // Print the state of the slave
        printf("  ALStatusCode: %04x\n", ec_slave[i].ALstatuscode); // Print the AL status code
        printf("  Delay: %d\n", ec_slave[i].pdelay); // Print the delay of the slave
        printf("  Has DC: %d\n", ec_slave[i].hasdc); // Check if the slave supports Distributed Clock
        printf("  DC Active: %d\n", ec_slave[i].DCactive); // Check if DC is active for the slave
        printf("  DC supported: %d\n", ec_slave[i].hasdc); // Print if DC is supported
    }

    // Read DC synchronization configuration using the correct parameters
    for(int i = 1; i <= ec_slavecount; i++) {
        uint16_t dcControl = 0; // Variable to hold DC control configuration
        int32_t cycleTime = 0; // Variable to hold cycle time
        int32_t shiftTime = 0; // Variable to hold shift time
        int size; // Variable to hold size for reading

        // Read DC synchronization configuration, adding the correct size parameter
        size = sizeof(dcControl);
        if (ec_SDOread(i, 0x1C32, 0x01, FALSE, &size, &dcControl, EC_TIMEOUTSAFE) > 0) {
            printf("Slave %d DC Configuration:\n", i);
            printf("  DC Control: 0x%04x\n", dcControl); // Print the DC control configuration
            
            size = sizeof(cycleTime);
            if (ec_SDOread(i, 0x1C32, 0x02, FALSE, &size, &cycleTime, EC_TIMEOUTSAFE) > 0) {
                printf("  Cycle Time: %d ns\n", cycleTime); // Print the cycle time
            }

        }
    }

    printf("__________STEP 6___________________\n");

    // Start the EtherCAT thread for real-time processing
    printf("Setting start_ecatthread_thread to TRUE\n");
    start_ecatthread_thread = TRUE;
    osal_thread_create_rt(&thread1, stack64k * 2, (void *)&ecatthread, (void *)&ctime_thread); // Create the real-time EtherCAT thread
    // set_thread_affinity(*thread1, 4); // Optional: Set CPU affinity for the thread
    osal_thread_create(&thread2, stack64k * 2, (void *)&ecatcheck, NULL); // Create the EtherCAT check thread
    // set_thread_affinity(*thread2, 5); // Optional: Set CPU affinity for the thread
    printf("___________________________________________\n");

    my_RA = 0; // Reset read access variable


    // 8. Transition to OP state
    printf("__________STEP 8___________________\n");

    // Send process data to the slaves
    ec_send_processdata();
    wkc = ec_receive_processdata(EC_TIMEOUTRET); // Receive process data and store the Work Counter

    // Set the first slave to operational state
    ec_slave[0].state = EC_STATE_OPERATIONAL; // Change the state of the first slave to OP
    ec_writestate(0); // Write the state change to the slave

    // Wait for the state transition to complete
    if ((ec_statecheck(0, EC_STATE_OPERATIONAL, 5 * EC_TIMEOUTSTATE)) == EC_STATE_OPERATIONAL) {
        printf("State changed to EC_STATE_OPERATIONAL: %d\n", EC_STATE_OPERATIONAL); // Confirm successful state change
        printf("___________________________________________\n");
    } else {
        printf("State could not be changed to EC_STATE_OPERATIONAL\n"); // Error message if state change fails
        for (int cnt = 1; cnt <= ec_slavecount; cnt++) {
            printf("ALstatuscode: %d\n", ecx_context.slavelist[cnt].ALstatuscode); // Print AL status codes for each slave
        }
    }

    // Read and display the state of all slaves
    ec_readstate(); // Read the state of all slaves
    for (int i = 1; i <= ec_slavecount; i++) {
        printf("Slave %d: Type %d, Address 0x%02x, State Machine actual %d, required %d\n", 
               i, ec_slave[i].eep_id, ec_slave[i].configadr, ec_slave[i].state, EC_STATE_OPERATIONAL); // Print slave information
        printf("Name: %s\n", ec_slave[i].name); // Print the name of the slave
        printf("___________________________________________\n");
    }

    // 9. Configure servomotor and mode operation
    printf("__________STEP 9___________________\n");

    if (ec_slave[0].state == EC_STATE_OPERATIONAL) {
        printf("Operational state reached for all slaves.\n");
        

        uint8 operation_mode = 8;
        uint16_t Control_Word = 128;

        for (int i = 1; i <= ec_slavecount; i++) {
            ec_SDOwrite(i, 0x6040, 0x00, FALSE, sizeof(Control_Word), &Control_Word, EC_TIMEOUTSAFE);
            ec_SDOwrite(i, 0x6060, 0x00, FALSE, sizeof(operation_mode), &operation_mode, EC_TIMEOUTSAFE);

        }
  // The main loop only needs to keep the program running
        while(1) {
            osal_usleep(100000); // Sleep for 100ms to reduce CPU usage
        }
    }

    osal_usleep(1e6);

    ec_close();

     printf("\nRequest init state for all slaves\n");
     ec_slave[0].state = EC_STATE_INIT;
     /* request INIT state for all slaves */
     ec_writestate(0);

    printf("EtherCAT master closed.\n");

    return 0;
}

/* 
 * PI calculation to synchronize Linux time with the Distributed Clock (DC) time.
 * This function calculates the offset time needed to align the Linux time with the DC time.
 */
void ec_sync(int64 reftime, int64 cycletime, int64 *offsettime) {
    static int64 integral = 0; // Integral term for PI controller
    int64 delta; // Variable to hold the difference between reference time and cycle time
    delta = (reftime) % cycletime; // Calculate the delta time
    if (delta > (cycletime / 2)) {
        delta = delta - cycletime; // Adjust delta if it's greater than half the cycle time
    }
    if (delta > 0) {
        integral++; // Increment integral if delta is positive
    }
    if (delta < 0) {
        integral--; // Decrement integral if delta is negative
    }
    *offsettime = -(delta / 100) - (integral / 20); // Calculate the offset time
    gl_delta = delta; // Update global delta variable
}

/* 
 * Add nanoseconds to a timespec structure.
 * This function updates the timespec structure by adding a specified amount of time.
 */
void add_timespec(struct timespec *ts, int64 addtime) {
    int64 sec, nsec; // Variables to hold seconds and nanoseconds

    nsec = addtime % NSEC_PER_SEC; // Calculate nanoseconds to add
    sec = (addtime - nsec) / NSEC_PER_SEC; // Calculate seconds to add
    ts->tv_sec += sec; // Update seconds in timespec
    ts->tv_nsec += nsec; // Update nanoseconds in timespec
    if (ts->tv_nsec >= NSEC_PER_SEC) { // If nanoseconds exceed 1 second
        nsec = ts->tv_nsec % NSEC_PER_SEC; // Adjust nanoseconds
        ts->tv_sec += (ts->tv_nsec - nsec) / NSEC_PER_SEC; // Increment seconds
        ts->tv_nsec = nsec; // Set adjusted nanoseconds
    }
}

/* 
 * EtherCAT check thread function
 * This function monitors the state of the EtherCAT slaves and attempts to recover 
 * any slaves that are not in the operational state.
 */
OSAL_THREAD_FUNC ecatcheck(void *ptr) {
    int slave; // Variable to hold the current slave index
    (void)ptr; // Not used
    int consecutive_errors = 0;
    const int MAX_CONSECUTIVE_ERRORS = 5;

    while (1) {
        if (inOP && ((wkc < expectedWKC) || ec_group[currentgroup].docheckstate)) {
            if (needlf) {
                needlf = FALSE;
                printf("\n");
            }
            
            // Increase the consecutive error count
            if (wkc < expectedWKC) {
                consecutive_errors++;
                printf("WARNING: Working counter error (%d/%d), consecutive errors: %d\n", 
                       wkc, expectedWKC, consecutive_errors);
            } else {
                consecutive_errors = 0;
            }

            // If the consecutive errors exceed the threshold, attempt reinitialization
            if (consecutive_errors >= MAX_CONSECUTIVE_ERRORS) {
                printf("ERROR: Too many consecutive errors, attempting recovery...\n");
                ec_group[currentgroup].docheckstate = TRUE;
                // Reset the error count
                consecutive_errors = 0;
            }

            ec_group[currentgroup].docheckstate = FALSE;
            ec_readstate();
            for (slave = 1; slave <= ec_slavecount; slave++) {
                if ((ec_slave[slave].group == currentgroup) && (ec_slave[slave].state != EC_STATE_OPERATIONAL)) {
                    ec_group[currentgroup].docheckstate = TRUE;
                    if (ec_slave[slave].state == (EC_STATE_SAFE_OP + EC_STATE_ERROR)) {
                        printf("ERROR: Slave %d is in SAFE_OP + ERROR, attempting ack.\n", slave);
                        ec_slave[slave].state = (EC_STATE_SAFE_OP + EC_STATE_ACK);
                        ec_writestate(slave);
                    } else if (ec_slave[slave].state == EC_STATE_SAFE_OP) {
                        printf("WARNING: Slave %d is in SAFE_OP, changing to OPERATIONAL.\n", slave);
                        ec_slave[slave].state = EC_STATE_OPERATIONAL;
                        ec_writestate(slave);
                    } else if (ec_slave[slave].state > EC_STATE_NONE) {
                        if (ec_reconfig_slave(slave, EC_TIMEOUTMON)) {
                            ec_slave[slave].islost = FALSE;
                            printf("MESSAGE: Slave %d reconfigured\n", slave);
                        }
                    } else if (!ec_slave[slave].islost) {
                        ec_statecheck(slave, EC_STATE_OPERATIONAL, EC_TIMEOUTRET);
                        if (!ec_slave[slave].state) {
                            ec_slave[slave].islost = TRUE;
                            printf("ERROR: Slave %d lost\n", slave);
                        }
                    }
                }
                if (ec_slave[slave].islost) {
                    if (!ec_slave[slave].state) {
                        if (ec_recover_slave(slave, EC_TIMEOUTMON)) {
                            ec_slave[slave].islost = FALSE;
                            printf("MESSAGE: Slave %d recovered\n", slave);
                        }
                    } else {
                        ec_slave[slave].islost = FALSE;
                        printf("MESSAGE: Slave %d found\n", slave);
                    }
                }
            }
            if (!ec_group[currentgroup].docheckstate) {
                printf("OK: All slaves resumed OPERATIONAL.\n");
            }
        }
        osal_usleep(500); 
    }
}

/* 
 * RT EtherCAT thread function
 * This function handles the real-time processing of EtherCAT data. 
 * It sends and receives process data in a loop, synchronizing with the 
 * distributed clock if available, and ensuring timely execution based on 
 * the specified cycle time.
 */
OSAL_THREAD_FUNC_RT ecatthread(void *ptr) {
    struct timespec ts, tleft;
    int ht;
    int64 cycletime;
    int missed_cycles = 0;
    const int MAX_MISSED_CYCLES = 10;
    struct timespec cycle_start, cycle_end;
    long cycle_time_ns;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    ht = (ts.tv_nsec / 1000000) + 1;
    ts.tv_nsec = ht * 1000000;
    if (ts.tv_nsec >= NSEC_PER_SEC) {
        ts.tv_sec++;
        ts.tv_nsec -= NSEC_PER_SEC;
    }
    cycletime = *(int *)ptr * 1000;

    toff = 0;
    dorun = 0;
    
    // Initialize PDO data
    rxpdo_t rxpdo;
    txpdo_t txpdo;
    
    rxpdo.controlword = 0x0080;
    rxpdo.target_position = 0;
    rxpdo.mode_of_operation = 8;
    rxpdo.padding = 0;
    
    // Send initial process data
    for (int slave = 1; slave <= ec_slavecount; slave++) {
        memcpy(ec_slave[slave].outputs, &rxpdo, sizeof(rxpdo_t));
    }
    ec_send_processdata();

    int step = 0;
    bool need_update = false;
    int32_t new_target = 0;

    while (1) {
        clock_gettime(CLOCK_MONOTONIC, &cycle_start);
        
        // 每1000个周期打印一次调试信息
        if (dorun % 1000 == 0) {
            printf("DEBUG: dorun=%d, delay_enabled=%d, delay_start=%d, delay_active=%d, delay_counter=%d\n",
                   dorun, delay_test_enabled, delay_test_start_cycle, delay_test_active, delay_test_counter);
        }
        
        add_timespec(&ts, cycletime + toff);
        
        // Check if delay test should be activated
        if (delay_test_enabled && dorun >= delay_test_start_cycle && 
            dorun < (delay_test_start_cycle + delay_test_duration)) {
            
            // 更新延迟测试计数器
            delay_test_counter = dorun - delay_test_start_cycle;
            delay_test_active = true;
            
            // 使用与周期时间匹配的延迟
            usleep(1500); // 5毫秒延迟
        } else {
            delay_test_active = false;
        }
        
        if (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, &tleft) != 0) {
            // If sleep is interrupted, record the error
            missed_cycles++;
            printf("WARNING: Clock sleep interrupted, missed cycles: %d\n", missed_cycles);
            if (missed_cycles >= MAX_MISSED_CYCLES) {
                printf("ERROR: Too many missed cycles, attempting recovery...\n");
                // Reset the counter
                missed_cycles = 0;
                // Resynchronize the clock
                clock_gettime(CLOCK_MONOTONIC, &ts);
                ts.tv_nsec = ((ts.tv_nsec / 1000000) + 1) * 1000000;
                if (ts.tv_nsec >= NSEC_PER_SEC) {
                    ts.tv_sec++;
                    ts.tv_nsec -= NSEC_PER_SEC;
                }
            }
        } else {
            missed_cycles = 0;
        }
        
        dorun++;

        if (start_ecatthread_thread) {
            // Receive process data
            wkc = ec_receive_processdata(EC_TIMEOUTRET);

            if (wkc >= expectedWKC) {
                // Retrieve the current motor status
                for (int slave = 1; slave <= ec_slavecount; slave++) {
                    memcpy(&txpdo, ec_slave[slave].inputs, sizeof(txpdo_t));
                }

                // State machine control
                if (step <= 4000) {
                    rxpdo.controlword = 0x0080;
                    rxpdo.target_position = 0;
                } else if (step <= 6000) {
                    rxpdo.controlword = 0x0006;
                    rxpdo.target_position = txpdo.actual_position;
                } else if (step <= 8000) {
                    rxpdo.controlword = 0x0007;
                    rxpdo.target_position = txpdo.actual_position;
                } else if (step <= 10000) {
                    rxpdo.controlword = 0x000F;
                    rxpdo.target_position = txpdo.actual_position;
                } else {
                    // Normal operational mode
                    // Execute trajectory planning
                    //int32_t planned_pos = plan_trajectory(&g_motion_planner, txpdo.actual_position);
                    // Update output PDO
                    rxpdo.controlword = 0x000F;
                    rxpdo.target_position = txpdo.actual_position + 20;
                    rxpdo.mode_of_operation = 8;
                }

                // Send PDO data to the slaves
                for (int slave = 1; slave <= ec_slavecount; slave++) {
                    memcpy(ec_slave[slave].outputs, &rxpdo, sizeof(rxpdo_t));
                }

                // Print status information every 100 cycles
                if (dorun % 100 == 0) {
                    printf("Status: pos=%d, target=%d, vel=%d, torque=%d\n",
                           txpdo.actual_position, rxpdo.target_position,
                           txpdo.actual_velocity, txpdo.actual_torque);
                    
                    // If we're in delay test, print additional information
                    if (delay_test_active) {
                        printf(">>> DELAY TEST ACTIVE: Cycle %d of %d (%.1f%% complete) <<<\n", 
                               delay_test_counter, delay_test_duration, 
                               (float)delay_test_counter / delay_test_duration * 100.0);
                    } else if (delay_test_enabled && dorun < delay_test_start_cycle) {
                        printf(">>> DELAY TEST PENDING: Will start in %d cycles <<<\n", 
                               delay_test_start_cycle - dorun);
                    }
                }

                if (step < 12000) {
                    step++;
                }
            } else {
                printf("WARNING: Working counter error (wkc: %d, expected: %d)\n", 
                       wkc, expectedWKC);
            }

            // Clock synchronization
            if (ec_slave[0].hasdc) {
                ec_sync(ec_DCtime, cycletime, &toff);
            }

            // Send process data
            ec_send_processdata();
        }

        // Monitor cycle time
        clock_gettime(CLOCK_MONOTONIC, &cycle_end);
        cycle_time_ns = (cycle_end.tv_sec - cycle_start.tv_sec) * NSEC_PER_SEC +
                       (cycle_end.tv_nsec - cycle_start.tv_nsec);
        
        if (cycle_time_ns > cycletime * 1.5) {
            printf("WARNING: Cycle time exceeded: %ld ns (expected: %ld ns)\n", 
                   cycle_time_ns, cycletime);
        }

    }
}

// Add a new function to start the delay test
void start_delay_test(int start_after_cycles, int test_duration) {
    delay_test_start_cycle = start_after_cycles;
    delay_test_duration = test_duration;
    delay_test_counter = 0;
    delay_test_active = false;
    delay_test_enabled = true;
    
    printf("\n\n");
    printf("*******************************************************\n");
    printf("*                                                     *\n");
    printf("*            DELAY TEST SCHEDULED                     *\n");
    printf("*            Will start after %d cycles               *\n", start_after_cycles);
    printf("*            Will run for %d cycles                   *\n", test_duration);
    printf("*                                                     *\n");
    printf("*******************************************************\n\n");
}



// Function to update motor status information
void update_motor_status(int slave_id) {
    // Update status information from TXPDO
    motor_status.status_word = txpdo.statusword;
    motor_status.actual_position = txpdo.actual_position;
    motor_status.actual_velocity = txpdo.actual_velocity;
    motor_status.actual_torque = txpdo.actual_torque;
    
    // Check status word to determine if motor is operational
    // Bits 0-3 should be 0111 for enabled and ready state
    motor_status.is_operational = (txpdo.statusword & 0x0F) == 0x07;
}

// Modify the main function to start the server thread
int main(int argc, char **argv) {
    needlf = FALSE;
    inOP = FALSE;
    start_ecatthread_thread = FALSE;
    dorun = 0;
    ctime_thread = 500; // 1毫秒周期时间

    // Set a higher real-time priority
    struct sched_param param;
    param.sched_priority = 99; // Maximum real-time priority
    if (sched_setscheduler(0, SCHED_FIFO, &param) == -1) {
        perror("sched_setscheduler failed");
    }

    // Lock memory to prevent paging
    if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
        perror("mlockall failed");
    }

    // Set CPU affinity
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(3, &cpuset);

    if (sched_setaffinity(0, sizeof(cpu_set_t), &cpuset) == -1) {
        perror("sched_setaffinity");
        return EXIT_FAILURE;
    }


    // 在启动 erob_test 前启用延迟测试
    start_delay_test(15000, 1000);  // 等待15000个周期后开始(包含使能前的4000+6000+5000个周期)，持续1000个周期

    printf("Running on CPU core 3\n");
    erob_test();
    printf("End program\n");

    return EXIT_SUCCESS;
}