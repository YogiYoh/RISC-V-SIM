def parse_32bits_binary(bits):
    # Ensure the instruction is exactly 32 bits (RISC-V instruction width)
    if len(bits) != 32:
        raise ValueError("Invalid instruction length")
    
    # Convert the 32-bit binary string into an integer for bit manipulation
    return int(bits, 2)


def get_instruction_type(opcode_int):
    # Determine the instruction format based on the 7-bit opcode
    if opcode_int == 0x33:
        return "R"     # Register-type instructions (add, sub, etc.)
    elif opcode_int in (0x13, 0x03, 0x67):
        return "I"     # Immediate-type (addi, loads, jalr)
    elif opcode_int == 0x23:
        return "S"     # Store-type (sw, sh, sb)
    elif opcode_int == 0x63:
        return "SB"    # Branch-type (beq, bne, etc.)
    elif opcode_int == 0x6F:
        return "UJ"    # Jump-type (jal)
    else:
        return "Unknown"


def decode_operation(opcode, funct3, funct7):
    # Decode the exact instruction mnemonic using opcode and function fields

    if opcode == 0x33:  # R-type ALU instructions
        if funct3 == 0x0:
            return "sub" if funct7 == 0x20 else "add"  # funct7 distinguishes add vs sub
        if funct3 == 0x7:
            return "and"
        if funct3 == 0x6:
            return "or"
        if funct3 == 0x4:
            return "xor"
        if funct3 == 0x2:
            return "slt"
        if funct3 == 0x3:
            return "sltu"
        if funct3 == 0x1:
            return "sll"
        if funct3 == 0x5:
            return "sra" if funct7 == 0x20 else "srl"

    elif opcode == 0x13:  # I-type ALU instructions
        if funct3 == 0x0:
            return "addi"
        if funct3 == 0x7:
            return "andi"
        if funct3 == 0x6:
            return "ori"
        if funct3 == 0x4:
            return "xori"
        if funct3 == 0x2:
            return "slti"
        if funct3 == 0x3:
            return "sltiu"
        if funct3 == 0x1:
            return "slli"
        if funct3 == 0x5:
            return "srai" if funct7 == 0x20 else "srli"

    elif opcode == 0x03:  # Load instructions
        if funct3 == 0x0:
            return "lb"
        if funct3 == 0x1:
            return "lh"
        if funct3 == 0x2:
            return "lw"

    elif opcode == 0x23:  # Store instructions
        if funct3 == 0x0:
            return "sb"
        if funct3 == 0x1:
            return "sh"
        if funct3 == 0x2:
            return "sw"

    elif opcode == 0x63:  # Branch instructions
        if funct3 == 0x0:
            return "beq"
        if funct3 == 0x1:
            return "bne"
        if funct3 == 0x4:
            return "blt"
        if funct3 == 0x5:
            return "bge"

    elif opcode == 0x6F:
        return "jal"    # Jump and link
    elif opcode == 0x67:
        return "jalr"   # Jump and link register

    return "unknown"


def sign_extend(value, bits):
    # Create a mask for the sign bit (most significant bit of the immediate)
    sign_bit = 1 << (bits - 1)

    # If the sign bit is set, the value is negative
    if value & sign_bit:
        value -= (1 << bits)  # Convert to signed two’s complement value

    return value


def imm_i(inst):
    # Extract bits [31:20] for I-type immediate (12 bits)
    imm_raw = (inst >> 20) & 0xFFF
    return sign_extend(imm_raw, 12)


def imm_s(inst):
    # Extract upper immediate bits [31:25]
    imm_11_5 = (inst >> 25) & 0x7F
    # Extract lower immediate bits [11:7]
    imm_4_0  = (inst >> 7) & 0x1F

    # Combine both parts into one 12-bit immediate
    imm_raw = (imm_11_5 << 5) | imm_4_0
    return sign_extend(imm_raw, 12)


def imm_sb(inst):
    # Branch immediates are split and shifted due to instruction alignment
    imm12   = ((inst >> 31) & 0x1) << 12
    imm11   = ((inst >> 7)  & 0x1) << 11
    imm10_5 = ((inst >> 25) & 0x3F) << 5
    imm4_1  = ((inst >> 8)  & 0xF) << 1

    # Combine all parts into a 13-bit immediate
    imm_raw = imm12 | imm11 | imm10_5 | imm4_1
    return sign_extend(imm_raw, 13)


def imm_uj(inst):
    # Jump immediates use a larger, scattered bit layout
    imm20    = ((inst >> 31) & 0x1) << 20
    imm19_12 = ((inst >> 12) & 0xFF) << 12
    imm11    = ((inst >> 20) & 0x1) << 11
    imm10_1  = ((inst >> 21) & 0x3FF) << 1

    # Combine into a 21-bit immediate
    imm_raw = imm20 | imm19_12 | imm11 | imm10_1
    return sign_extend(imm_raw, 21)


def decode_instruction(inst):
    """Decode a 32-bit instruction word into fields for the simulator (no I/O)."""
    inst &= 0xFFFFFFFF
    rd = (inst >> 7) & 0x1F
    funct3 = (inst >> 12) & 0x7
    rs1 = (inst >> 15) & 0x1F
    rs2 = (inst >> 20) & 0x1F
    funct7 = (inst >> 25) & 0x7F
    opcode = inst & 0x7F
    inst_type = get_instruction_type(opcode)
    mnemonic = decode_operation(opcode, funct3, funct7)

    imm = None
    if inst_type == "I":
        imm = imm_i(inst)
    elif inst_type == "S":
        imm = imm_s(inst)
    elif inst_type == "SB":
        imm = imm_sb(inst)
    elif inst_type == "UJ":
        imm = imm_uj(inst)

    return {
        "inst": inst,
        "opcode": opcode,
        "funct3": funct3,
        "funct7": funct7,
        "rd": rd,
        "rs1": rs1,
        "rs2": rs2,
        "type": inst_type,
        "mnemonic": mnemonic,
        "imm": imm,
    }


def decode_print_binary(bits):
    # Convert the binary instruction into an integer
    inst = parse_32bits_binary(bits)
    d = decode_instruction(inst)
    inst_type = d["type"]
    op = d["mnemonic"]
    rd, rs1, rs2 = d["rd"], d["rs1"], d["rs2"]
    funct3, funct7, opcode = d["funct3"], d["funct7"], d["opcode"]

    print(f"Instruction Type: {inst_type}")
    print(f"Operation: {op}")

    # Print fields depending on instruction format
    if inst_type == "R":
        print(f"rd: x{rd}")
        print(f"rs1: x{rs1}")
        print(f"rs2: x{rs2}")
        print(f"funct3: {funct3}")
        print(f"funct7: {funct7}")

    elif inst_type == "I":
        print(f"rd: x{rd}")
        print(f"rs1: x{rs1}")
        print(f"imm: {d['imm']}")
        print(f"funct3: {funct3}")

    elif inst_type == "S":
        print(f"rs1: x{rs1}")
        print(f"rs2: x{rs2}")
        print(f"imm: {d['imm']}")
        print(f"funct3: {funct3}")

    elif inst_type == "SB":
        print(f"rs1: x{rs1}")
        print(f"rs2: x{rs2}")
        print(f"imm: {d['imm']}")
        print(f"funct3: {funct3}")

    elif inst_type == "UJ":
        print(f"rd: x{rd}")
        print(f"imm: {d['imm']}")

    else:
        print(f"opcode: 0x{opcode:02X}")

    print()


def main():
    # Read instruction input from the user
    line = input("Enter an instruction: ")

    # Remove any characters that are not binary digits
    bits = ''.join(c for c in line if c in '01')

    # Decode and display the instruction
    decode_print_binary(bits)


# Run main only when this file is executed directly
if __name__ == "__main__":
    main()