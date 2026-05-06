from pathlib import Path

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


# Pipeline registers (5-stage / extra-credit mode)
if_id = {"valid": False}
id_ex = {"valid": False}
ex_mem = {"valid": False}
mem_wb = {"valid": False}


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


# ================= PIPELINE OVERVIEW ================= #
# This CPU implements a 5-stage RISC-V pipeline:
#
#   1. IF  (Instruction Fetch)
#   2. ID  (Instruction Decode)
#   3. EX  (Execute / ALU)
#   4. MEM (Data Memory Access)
#   5. WB  (Write Back)
#
# Instead of executing one instruction at a time (single-cycle CPU),
# multiple instructions are processed simultaneously in different stages.
#
# Each stage communicates using pipeline registers:
#   if_id  → holds IF output for ID stage
#   id_ex  → holds ID output for EX stage
#   ex_mem → holds EX output for MEM stage
#   mem_wb → holds MEM output for WB stage
#
# This creates instruction overlap, which increases performance.


# ================= PIPELINE REGISTERS ================= #
# These act like "buffers" between hardware pipeline stages.
# Each cycle, data moves forward one stage.

if_id = {"valid": False}   # IF → ID buffer (instruction fetched)
id_ex = {"valid": False}   # ID → EX buffer (decoded instruction + control signals)
ex_mem = {"valid": False}  # EX → MEM buffer (ALU result + store data)
mem_wb = {"valid": False}  # MEM → WB buffer (final result for register writeback)


# ================= PIPELINE EXECUTION MODEL ================= #
# The pipeline runs inside run_pipeline_cpu()
#
# Each loop iteration = ONE CLOCK CYCLE
# NOT one instruction completion.
#
# That means:
# - Stage 1 executes for instruction A
# - Stage 2 executes for instruction A while Stage 1 executes for B
# - Stage 3 executes for A while others progress, etc.


def run_pipeline_cpu():
    """
    5-stage pipeline simulation (EXTRA CREDIT IMPLEMENTATION)

    Key idea:
    - Each instruction flows through IF → ID → EX → MEM → WB
    - All stages operate in parallel (like hardware)
    - Pipeline registers store intermediate values between stages
    """

    # ================= PIPELINE INITIALIZATION ================= #
    # Reset CPU state and pipeline registers before starting execution

    global pc, total_clock_cycles, alu_ctrl
    global if_id, id_ex, ex_mem, mem_wb

    pc = 0
    total_clock_cycles = 0

    if_id = {"valid": False}   # no instruction in IF/ID initially
    id_ex = {"valid": False}   # no instruction in ID/EX initially
    ex_mem = {"valid": False}  # no instruction in EX/MEM initially
    mem_wb = {"valid": False}  # no instruction in MEM/WB initially

    finished = False


    # ================= HELPER FUNCTIONS ================= #

    # Checks if PC is still within program bounds
    def pc_in_range():
        return 0 <= (pc // 4) < len(instructions)

    # Returns registers used by instruction (for hazard detection)
    def source_regs(decoded):
        # Used to detect RAW (Read After Write) hazards
        opcode = decoded["opcode"]

        if opcode == 0x33:      # R-type uses rs1 and rs2
            return [decoded["rs1"], decoded["rs2"]]

        if opcode in (0x13, 0x03, 0x67):  # I-type, load, jalr
            return [decoded["rs1"]]

        if opcode in (0x23, 0x63):        # store, branch
            return [decoded["rs1"], decoded["rs2"]]

        return []  # jal has no source registers


    # Checks if a pipeline stage will write a register in the future
    def writes_pending(stage):
        return (
            stage.get("valid")
            and stage.get("RegWrite")
            and stage["decoded"]["rd"] != 0
        )


    # Detects RAW hazards between pipeline stages
    def hazard_registers(decoded):
        needed = set(source_regs(decoded))  # registers current instruction needs
        blocked = []

        # Check ID/EX and EX/MEM for pending writes
        for stage in (id_ex, ex_mem):
            if writes_pending(stage):
                rd = stage["decoded"]["rd"]
                if rd in needed:
                    blocked.append(rd)

        return blocked


    # Detects control instructions (branch/jump)
    def is_control(decoded):
        return decoded["opcode"] in (0x63, 0x6F, 0x67)


    # ================= MAIN PIPELINE LOOP ================= #
    while not finished:

        # Each loop iteration = ONE CLOCK CYCLE
        total_clock_cycles += 1
        print(f"\ncycle {total_clock_cycles}:")


        # ================= WB (Write Back Stage) ================= #
        # Final stage: writes result into register file

        if mem_wb.get("valid"):
            d = mem_wb["decoded"]

            if mem_wb["RegWrite"] and d["rd"] != 0:

                # Select correct value depending on instruction type
                if mem_wb.get("Jump") or mem_wb.get("JumpReg"):
                    value = mem_wb["link_pc"]
                elif mem_wb["MemToReg"]:
                    value = mem_wb["mem_data"]
                else:
                    value = mem_wb["alu_result"]

                rf[d["rd"]] = value
                print(f"WB: {reg_name(d['rd'])} = {hex(value)}")


        # ================= MEM (Memory Stage) ================= #
        # Handles loads and stores

        next_mem_wb = {"valid": False}
        mem_data_wb = 0

        if ex_mem.get("valid"):
            d = ex_mem["decoded"]
            addr = ex_mem["alu_result"]
            index = addr // 4

            # Load operation
            if ex_mem["MemRead"]:
                mem_data_wb = d_mem[index]

            # Store operation
            if ex_mem["MemWrite"]:
                d_mem[index] = ex_mem["op2"]
                print(f"MEM: memory[{hex(addr)}] = {hex(d_mem[index])}")

            # Pass results to WB stage
            next_mem_wb = {
                "valid": True,
                "decoded": d,
                "alu_result": ex_mem["alu_result"],
                "mem_data": mem_data_wb,
                "RegWrite": ex_mem["RegWrite"],
                "MemToReg": ex_mem["MemToReg"],
                "Jump": ex_mem.get("Jump", 0),
                "JumpReg": ex_mem.get("JumpReg", 0),
                "link_pc": ex_mem.get("link_pc"),
            }


        # ================= EX (Execute Stage) ================= #
        # ALU operations + branch/jump decision logic

        next_ex_mem = {"valid": False}
        branch_taken = False
        new_pc = pc
        control_in_ex = False

        if id_ex.get("valid"):
            d = id_ex["decoded"]

            # Detect control hazard in EX stage
            control_in_ex = id_ex["Branch"] or id_ex["Jump"] or id_ex["JumpReg"]

            op1 = id_ex["op1"]
            op2 = id_ex["imm"] if id_ex["ALUSrc"] else id_ex["op2"]

            # ALU operation execution
            ac = id_ex["alu_ctrl"]
            if ac == 0:
                result = op1 & op2
            elif ac == 1:
                result = op1 | op2
            elif ac == 2:
                result = op1 + op2
            elif ac == 6:
                result = op1 - op2
            else:
                result = op1 + op2

            zero = 1 if result == 0 else 0

            instr_pc = id_ex["pc"]

            # Branch target computation
            branch_target = instr_pc + id_ex["imm"]

            # Branch decision
            if id_ex["Branch"] and zero:
                branch_taken = True
                new_pc = branch_target

            # Jump decision
            if id_ex["Jump"]:
                branch_taken = True
                new_pc = instr_pc + id_ex["imm"]

            # Jump register decision
            if id_ex["JumpReg"]:
                branch_taken = True
                new_pc = (op1 + id_ex["imm"]) & ~1

            link_pc = instr_pc + 4 if (id_ex["Jump"] or id_ex["JumpReg"]) else None

            # Pass results to MEM stage
            next_ex_mem = {
                "valid": True,
                "decoded": d,
                "alu_result": result,
                "op2": id_ex["op2"],
                "MemRead": id_ex["MemRead"],
                "MemWrite": id_ex["MemWrite"],
                "RegWrite": id_ex["RegWrite"],
                "MemToReg": id_ex["MemToReg"],
                "Jump": id_ex["Jump"],
                "JumpReg": id_ex["JumpReg"],
                "link_pc": link_pc,
            }


        # ================= ID + IF (Decode + Fetch Stages) ================= #
        # This stage also handles hazard detection and stalls

        next_id_ex = {"valid": False}
        next_if_id = {"valid": False}

        # If branch is taken, flush incorrect instructions
        if branch_taken:
            pc = new_pc
            print("IF: stall (control transfer)")

        elif control_in_ex:
            print("IF: stall (control hazard)")

        else:

            if if_id.get("valid"):
                inst = if_id["inst"]
                d = decode_instruction(inst)

                # RAW hazard detection (stall pipeline if needed)
                blocked = hazard_registers(d)

                if blocked:
                    next_if_id = if_id  # freeze pipeline stage
                    waiting = ", ".join(reg_name(r) for r in sorted(set(blocked)))
                    print(f"ID: stall (waiting for {waiting})")

                else:
                    ControlUnit(d["opcode"])
                    ALUControl(d["funct3"], d["funct7"])

                    imm_v = d["imm"] if d["imm"] is not None else 0

                    # Pass decoded data into ID/EX pipeline register
                    next_id_ex = {
                        "valid": True,
                        "decoded": d,
                        "op1": rf[d["rs1"]],
                        "op2": rf[d["rs2"]],
                        "imm": imm_v,
                        "pc": if_id["pc"],
                        "alu_ctrl": alu_ctrl,
                        "RegWrite": RegWrite,
                        "MemRead": MemRead,
                        "MemWrite": MemWrite,
                        "MemToReg": MemToReg,
                        "ALUSrc": ALUSrc,
                        "Branch": Branch,
                        "Jump": Jump,
                        "JumpReg": JumpReg,
                    }

                    # Fetch next instruction if no hazard
                    if is_control(d):
                        print("IF: stall (control hazard)")
                    elif pc_in_range():
                        inst_int = int(instructions[pc // 4], 2)
                        next_if_id = {"valid": True, "inst": inst_int, "pc": pc}
                        pc += 4


        # ================= PIPELINE REGISTER UPDATE ================= #
        # This is the "clock edge" — everything moves forward one stage

        mem_wb = next_mem_wb
        ex_mem = next_ex_mem
        id_ex = next_id_ex
        if_id = next_if_id


        print(f"PC = {hex(pc)}")

        # Stop when pipeline is empty and program is done
        if not (
            if_id.get("valid")
            or id_ex.get("valid")
            or ex_mem.get("valid")
            or mem_wb.get("valid")
        ):
            if (pc // 4) >= len(instructions):
                finished = True


    print("\nProgram finished")
    print(f"Total cycles: {total_clock_cycles}")

def main():
    global USE_ABI_NAMES

    filename = input("Enter the program file name to run:\n").strip()
    mode = input("Enter 1 for single-cycle, 2 for pipelined:\n").strip()

    path = Path(filename)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path

    # PDF only requires the filename prompt; Part 1 vs Part 2 init follows the handout samples.
    if "part2" in path.name.lower():
        init_part2()
        USE_ABI_NAMES = True
    else:
        init_part1()
        USE_ABI_NAMES = False

    load_program(path)
    if mode == "2":
        run_pipeline_cpu()
    else:
        run_cpu()


if __name__ == "__main__":
    main()
