"""CPU state: fetch, decode, execute, memory, writeback, PC update (single-cycle step)."""

from riscv_decode import decode_instruction

NUM_REGS = 32
DEFAULT_MEM_BYTES = 1 << 16  # 64 KiB byte-addressable memory


def _u32(x):
    return x & 0xFFFFFFFF


def _s32(x):
    x = _u32(x)
    return x - 0x100000000 if (x & 0x80000000) else x


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

    def _reg_read(self, r):
        return 0 if r == 0 else _u32(self.regs[r])

    def _reg_write(self, r, val):
        if r != 0:
            self.regs[r] = _u32(val)

    def _load_byte_u(self, addr):
        addr = _u32(addr)
        if addr >= len(self.mem):
            raise ValueError(f"load byte OOB: addr={addr:#x}")
        return self.mem[addr]

    def _store_byte(self, addr, b):
        addr = _u32(addr)
        if addr >= len(self.mem):
            raise ValueError(f"store byte OOB: addr={addr:#x}")
        self.mem[addr] = b & 0xFF

    def step(self):
        """Run exactly one instruction: fetch through writeback and PC update."""
        d = self.fetch_and_decode()
        inst = d["inst"]
        mn = d["mnemonic"]
        rd, rs1, rs2 = d["rd"], d["rs1"], d["rs2"]
        imm = d["imm"]

        pc = self.pc
        pc_next = pc + 4

        v1 = self._reg_read(rs1)
        v2 = self._reg_read(rs2)

        if mn == "add":
            self._reg_write(rd, v1 + v2)
        elif mn == "sub":
            self._reg_write(rd, v1 - v2)
        elif mn == "and":
            self._reg_write(rd, v1 & v2)
        elif mn == "or":
            self._reg_write(rd, v1 | v2)
        elif mn == "xor":
            self._reg_write(rd, v1 ^ v2)
        elif mn == "slt":
            self._reg_write(rd, 1 if _s32(v1) < _s32(v2) else 0)
        elif mn == "sltu":
            self._reg_write(rd, 1 if _u32(v1) < _u32(v2) else 0)
        elif mn == "sll":
            self._reg_write(rd, _u32(v1 << (v2 & 0x1F)))
        elif mn == "srl":
            self._reg_write(rd, _u32(v1) >> (v2 & 0x1F))
        elif mn == "sra":
            self._reg_write(rd, _u32(_s32(v1) >> (v2 & 0x1F)))

        elif mn == "addi":
            self._reg_write(rd, v1 + imm)
        elif mn == "andi":
            self._reg_write(rd, v1 & imm)
        elif mn == "ori":
            self._reg_write(rd, v1 | imm)
        elif mn == "xori":
            self._reg_write(rd, v1 ^ imm)
        elif mn == "slti":
            self._reg_write(rd, 1 if _s32(v1) < imm else 0)
        elif mn == "sltiu":
            self._reg_write(rd, 1 if _u32(v1) < _u32(imm) else 0)
        elif mn == "slli":
            sh = (inst >> 20) & 0x1F
            self._reg_write(rd, _u32(v1 << sh))
        elif mn == "srli":
            sh = (inst >> 20) & 0x1F
            self._reg_write(rd, _u32(v1) >> sh)
        elif mn == "srai":
            sh = (inst >> 20) & 0x1F
            self._reg_write(rd, _u32(_s32(v1) >> sh))

        elif mn == "lb":
            b = self._load_byte_u(v1 + imm)
            if b & 0x80:
                b = b - 256
            self._reg_write(rd, _u32(b))
        elif mn == "lh":
            a = _u32(v1 + imm)
            lo = self._load_byte_u(a)
            hi = self._load_byte_u(a + 1)
            half = (lo | (hi << 8)) & 0xFFFF
            if half & 0x8000:
                half -= 65536
            self._reg_write(rd, _u32(half))
        elif mn == "lw":
            a = _u32(v1 + imm)
            w = (
                self._load_byte_u(a)
                | (self._load_byte_u(a + 1) << 8)
                | (self._load_byte_u(a + 2) << 16)
                | (self._load_byte_u(a + 3) << 24)
            )
            self._reg_write(rd, w)

        elif mn == "sb":
            a = _u32(v1 + imm)
            self._store_byte(a, v2)
        elif mn == "sh":
            a = _u32(v1 + imm)
            self._store_byte(a, v2)
            self._store_byte(a + 1, v2 >> 8)
        elif mn == "sw":
            a = _u32(v1 + imm)
            self._store_byte(a, v2)
            self._store_byte(a + 1, v2 >> 8)
            self._store_byte(a + 2, v2 >> 16)
            self._store_byte(a + 3, v2 >> 24)

        elif mn == "beq":
            if v1 == v2:
                pc_next = pc + imm
        elif mn == "bne":
            if v1 != v2:
                pc_next = pc + imm
        elif mn == "blt":
            if _s32(v1) < _s32(v2):
                pc_next = pc + imm
        elif mn == "bge":
            if _s32(v1) >= _s32(v2):
                pc_next = pc + imm

        elif mn == "jal":
            self._reg_write(rd, pc_next)
            pc_next = pc + imm

        elif mn == "jalr":
            self._reg_write(rd, pc_next)
            pc_next = _u32(v1 + imm) & ~1

        else:
            raise ValueError(f"unsupported instruction: {mn!r} (opcode={d['opcode']:#x})")

        self.pc = _u32(pc_next)


def _smoke_test():
    # addi x1, x0, 5  -> 0x500093 LE
    m = MachineState()
    m.mem[0:4] = bytes([0x93, 0x00, 0x50, 0x00])
    d = m.fetch_and_decode()
    assert d["mnemonic"] == "addi" and d["rd"] == 1 and d["rs1"] == 0 and d["imm"] == 5, d
    assert d["type"] == "I"
    m.step()
    assert m.regs[1] == 5 and m.pc == 4, (m.regs[1], m.pc)
    print("smoke test ok: addi x1,x0,5 -> x1=5, pc=4")


if __name__ == "__main__":
    _smoke_test()
