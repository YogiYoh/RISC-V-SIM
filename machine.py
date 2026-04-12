"""CPU state, instruction fetch (little-endian), and decode via hw3."""

from riscv_decode import decode_instruction

NUM_REGS = 32
DEFAULT_MEM_BYTES = 1 << 16  # 64 KiB byte-addressable memory

class MachineState:
    def __init__(self, mem_size=DEFAULT_MEM_BYTES):
        self.pc = 0
        self.regs = [0] * NUM_REGS
        self.mem = bytearray(mem_size)

    def fetch_word(self):
        """Read one 32-bit instruction from mem[pc:pc+4], RISC-V little-endian."""
        p = self.pc
        if p % 4 != 0:
            raise ValueError(f"PC must be 4-byte aligned, got {p}")
        if p + 4 > len(self.mem):
            raise ValueError(f"Instruction fetch past memory: pc={p}")
        m = self.mem
        return m[p] | (m[p + 1] << 8) | (m[p + 2] << 16) | (m[p + 3] << 24)

    def fetch_and_decode(self):
        word = self.fetch_word()
        return decode_instruction(word)


def _smoke_test():
    # addi x1, x0, 5  -> 0x500093 (not 0x00508093; 5<<20 == 0x500000)
    m = MachineState()
    m.mem[0:4] = bytes([0x93, 0x00, 0x50, 0x00])
    d = m.fetch_and_decode()
    assert d["mnemonic"] == "addi" and d["rd"] == 1 and d["rs1"] == 0 and d["imm"] == 5, d
    assert d["type"] == "I"
    print("smoke test ok:", d)


if __name__ == "__main__":
    _smoke_test()
