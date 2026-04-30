from riscv_decode import decode_instruction


# ================= GLOBAL STATE ================= #
# These variables simulate the hardware state of a CPU

pc = 0                 # Program Counter (address of current instruction)
next_pc = 0            # Holds PC + 4 (next sequential instruction)
branch_target = 0      # Target address if a branch is taken

# Register file (32 registers in RISC-V)
rf = [0] * 32

# Data memory (simple array to simulate RAM)
d_mem = [0] * 32

# List of instructions (loaded from file)
instructions = []

# ALU-related outputs
alu_zero = 0           # Set to 1 if ALU result is zero (used for branches)
alu_ctrl = 0           # Determines which ALU operation to perform
alu_result = 0         # Result of ALU computation
mem_data = 0           # Data read from memory

# Performance tracking
total_clock_cycles = 0


# ================= CONTROL SIGNALS ================= #
# These mimic real CPU control wires that guide execution
RegWrite = 0   # Write result back to register file
MemRead = 0    # Read from memory
MemWrite = 0   # Write to memory
MemToReg = 0   # Choose memory output vs ALU output
ALUSrc = 0     # Choose register vs immediate as ALU input
Branch = 0     # Indicates a branch instruction
ALUOp = 0      # High-level ALU operation category
Jump = 0       # Jump (jal)
JumpReg = 0    # Jump register (jalr)


# ================= ABI REGISTER NAMES ================= #
# Optional: use human-friendly names instead of x0–x31
USE_ABI_NAMES = False
ABI_NAMES = [
    "zero", "ra", "sp",  "gp",  "tp", "t0", "t1", "t2",
    "s0",   "s1", "a0",  "a1",  "a2", "a3", "a4", "a5",
    "a6",   "a7", "s2",  "s3",  "s4", "s5", "s6", "s7",
    "s8",   "s9", "s10", "s11", "t3", "t4", "t5", "t6",
]

def reg_name(i):
    # Returns either x# or ABI name depending on setting
    return ABI_NAMES[i] if USE_ABI_NAMES else f"x{i}"


# ================= INITIAL STATE ================= #
# These functions preload registers/memory for testing

def init_part1():
    """Initial rf / d_mem values required by the Part 1 sample."""
    global rf, d_mem
    rf = [0] * 32
    d_mem = [0] * 32

    # Example register setup
    rf[1] = 0x20
    rf[2] = 0x5
    rf[10] = 0x70
    rf[11] = 0x4

    # Example memory contents
    d_mem[0x70 // 4] = 0x5
    d_mem[0x74 // 4] = 0x10


def init_part2():
    """Initial rf / d_mem values required by the Part 2 sample."""
    global rf, d_mem
    rf = [0] * 32
    d_mem = [0] * 32

    # Using ABI register conventions (s0, a0, etc.)
    rf[8]  = 0x20   # s0
    rf[10] = 0x5    # a0
    rf[11] = 0x2    # a1
    rf[12] = 0xa    # a2
    rf[13] = 0xf    # a3


# ================= LOAD PROGRAM ================= #
def load_program(filename):
    # Reads binary instructions from file into memory
    global instructions
    with open(filename, "r") as f:
        instructions = [line.strip() for line in f if line.strip()]


# ================= FETCH STAGE ================= #
def Fetch():
    """
    Fetches instruction from memory using PC.
    Equivalent to Instruction Memory stage in a CPU.
    """
    global pc, next_pc

    index = pc // 4                  # Convert byte address → word index
    raw_bits = instructions[index]   # Get binary string

    inst_int = int(raw_bits, 2)      # Convert to integer

    next_pc = pc + 4                 # Default: move to next instruction

    return inst_int


# ================= DECODE STAGE ================= #
def Decode(inst_int):
    """
    Decodes instruction fields (opcode, registers, immediate).
    Also reads register values (like real CPU register file access).
    """
    decoded = decode_instruction(inst_int)

    # Read register values here (important pipeline step)
    decoded["op1"] = rf[decoded["rs1"]]
    decoded["op2"] = rf[decoded["rs2"]]

    return decoded


# ================= CONTROL UNIT ================= #
def ControlUnit(opcode):
    """
    Sets control signals based on instruction opcode.
    This determines how the rest of the pipeline behaves.
    """
    global RegWrite, MemRead, MemWrite, MemToReg
    global ALUSrc, Branch, ALUOp, Jump, JumpReg

    # Reset all signals
    RegWrite = MemRead = MemWrite = MemToReg = 0
    ALUSrc = Branch = ALUOp = Jump = JumpReg = 0

    # R-type (add, sub, etc.)
    if opcode == 0x33:
        RegWrite = 1
        ALUOp = 2

    # I-type (addi, etc.)
    elif opcode == 0x13:
        RegWrite = 1
        ALUSrc = 1
        ALUOp = 3

    # Load
    elif opcode == 0x03:
        RegWrite = 1
        MemRead = 1
        MemToReg = 1
        ALUSrc = 1

    # Store
    elif opcode == 0x23:
        MemWrite = 1
        ALUSrc = 1

    # Branch
    elif opcode == 0x63:
        Branch = 1
        ALUOp = 1

    # Jump (jal)
    elif opcode == 0x6F:
        Jump = 1
        RegWrite = 1

    # Jump register (jalr)
    elif opcode == 0x67:
        JumpReg = 1
        RegWrite = 1
        ALUSrc = 1


# ================= ALU CONTROL ================= #
def ALUControl(funct3, funct7):
    """
    Converts high-level ALUOp into a specific ALU action.
    This mimics the ALU control logic in hardware.
    """
    global alu_ctrl

    if ALUOp == 0:
        alu_ctrl = 2  # ADD
    elif ALUOp == 1:
        alu_ctrl = 6  # SUB (for branch comparisons)
    elif ALUOp == 2:
        if funct3 == 0 and funct7 == 0:
            alu_ctrl = 2  # ADD
        elif funct3 == 0 and funct7 == 32:
            alu_ctrl = 6  # SUB
        elif funct3 == 7:
            alu_ctrl = 0  # AND
        elif funct3 == 6:
            alu_ctrl = 1  # OR
    elif ALUOp == 3:
        if funct3 == 0:
            alu_ctrl = 2  # ADDI
        elif funct3 == 7:
            alu_ctrl = 0  # ANDI
        elif funct3 == 6:
            alu_ctrl = 1  # ORI


# ================= EXECUTE STAGE ================= #
def Execute(decoded):
    """
    Performs ALU operations and computes branch targets.
    """
    global alu_result, alu_zero, branch_target

    op1 = decoded["op1"]
    imm = decoded["imm"] if decoded["imm"] is not None else 0

    # Select second ALU operand
    op2 = imm if ALUSrc else decoded["op2"]

    ALUControl(decoded["funct3"], decoded["funct7"])

    # Perform ALU operation
    if alu_ctrl == 0:
        alu_result = op1 & op2
    elif alu_ctrl == 1:
        alu_result = op1 | op2
    elif alu_ctrl == 2:
        alu_result = op1 + op2
    elif alu_ctrl == 6:
        alu_result = op1 - op2

    # Zero flag used for branches
    alu_zero = 1 if alu_result == 0 else 0

    # Compute branch target address
    branch_target = pc + imm


# ================= MEMORY STAGE ================= #
def Mem(decoded):
    """
    Handles memory reads and writes.
    """
    global mem_data

    addr = alu_result
    index = addr // 4

    if MemRead:
        mem_data = d_mem[index]

    if MemWrite:
        d_mem[index] = decoded["op2"]
        print(f"memory {hex(addr)} is modified to {hex(d_mem[index])}")


# ================= WRITE BACK ================= #
def WriteBack(decoded):
    """
    Writes result back to register file.
    """
    if RegWrite and decoded["rd"] != 0:
        value = mem_data if MemToReg else alu_result
        rf[decoded["rd"]] = value
        print(f"{reg_name(decoded['rd'])} is modified to {hex(value)}")


# ================= MAIN PIPELINE LOOP ================= #
def run_cpu():
    """
    Simulates the CPU running instruction-by-instruction.
    Each loop = one instruction (not a true parallel pipeline).
    """
    global pc, next_pc, total_clock_cycles

    pc = 0
    total_clock_cycles = 0

    while 0 <= (pc // 4) < len(instructions):

        total_clock_cycles += 1
        print(f"total_clock_cycles {total_clock_cycles} :")

        # 1. FETCH
        inst_int = Fetch()

        # 2. DECODE
        decoded = Decode(inst_int)
        ControlUnit(decoded["opcode"])

        # 3. EXECUTE
        Execute(decoded)

        # 4. MEMORY
        Mem(decoded)

        # 5. WRITE BACK + PC UPDATE
        if Jump:
            if decoded["rd"] != 0:
                rf[decoded["rd"]] = next_pc
                print(f"{reg_name(decoded['rd'])} is modified to {hex(next_pc)}")
            pc = pc + decoded["imm"]

        elif JumpReg:
            if decoded["rd"] != 0:
                rf[decoded["rd"]] = next_pc
                print(f"{reg_name(decoded['rd'])} is modified to {hex(next_pc)}")
            pc = (rf[decoded["rs1"]] + decoded["imm"]) & ~1

        else:
            WriteBack(decoded)

            # Branch decision
            if Branch and alu_zero:
                pc = branch_target
            else:
                pc = next_pc

        print(f"pc is modified to {hex(pc)}")

    print("program terminated:")
    print(f"total execution time is {total_clock_cycles} cycles")