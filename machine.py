from riscv_decode import decode_instruction

# Global CPU state
pc = 0
next_pc = 0

# Register file: 32 registers, all start at 0
rf = [0] * 32

# Data memory: 32 words (each entry = 4 bytes), all start at 0
d_mem = [0] * 32

# Instruction memory: loaded from the input text file
instructions = []

decode_list = []



def load_program(filename):
    """Read binary instruction strings from a text file into instructions[]."""
    global instructions
    with open(filename, "r") as f:
        instructions = [line.strip() for line in f if line.strip()]


def Fetch():
    """Return the decoded instruction at the current PC and update next_pc."""
    global pc, next_pc

    # PC / 4 gives the index into the instruction list
    index = pc // 4
    raw_bits = instructions[index]

    # Convert binary string to integer, then decode into fields
    inst_int = int(raw_bits, 2)
    decoded = decode_instruction(inst_int)
    # Default next instruction is PC + 4
    next_pc = pc + 4

    return decoded


def run_cpu():
    global pc, next_pc, decode_list
    
    decode_list.clear()
    pc = 0
    
    while (pc // 4) < len(instructions):
        decode = Fetch()
        decode_list.append(decode)
        
        pc = next_pc


if __name__ == "__main__":
    path = "instruction.txt"
    load_program(path)

    run_cpu()
    
    for i in range(len(decode_list)):
        print(f"instruction {i}:")
        
        print(decode_list[i])
        print()

    
    
