"""Shared ARMv4T condition and arithmetic semantics for generated C."""


def condition_expr(condition: int) -> str:
    n = "((ctx->cpsr >> 31) & 1)"
    c = "((ctx->cpsr >> 29) & 1)"
    v = "((ctx->cpsr >> 28) & 1)"
    return (
        "ctx->flag_z", "!ctx->flag_z", c, f"!{c}", n, f"!{n}",
        v, f"!{v}", f"({c} && !ctx->flag_z)", f"(!{c} || ctx->flag_z)",
        f"({n} == {v})", f"({n} != {v})", f"(!ctx->flag_z && {n} == {v})",
        f"(ctx->flag_z || {n} != {v})", "true", "false",
    )[condition]


ARM_FLAG_HELPERS = r'''
static inline void arm_set_nz(ArmCpuContext* ctx, uint32_t value) {
    ctx->flag_z = value == 0;
    ctx->cpsr = (ctx->cpsr & 0x3FFFFFFFu) | (value & 0x80000000u)
              | (ctx->flag_z ? 0x40000000u : 0);
}
static inline uint32_t arm_add(ArmCpuContext* ctx, uint32_t a, uint32_t b,
                              uint32_t carry, bool flags) {
    uint64_t sum = (uint64_t)a + b + carry;
    uint32_t result = (uint32_t)sum;
    if (flags) {
        ctx->cpsr = (ctx->cpsr & 0xCFFFFFFFu)
                  | ((sum >> 32) ? 0x20000000u : 0)
                  | ((~(a ^ b) & (a ^ result) & 0x80000000u) ? 0x10000000u : 0);
        arm_set_nz(ctx, result);
    }
    return result;
}
static inline uint32_t arm_sub(ArmCpuContext* ctx, uint32_t a, uint32_t b,
                              uint32_t carry, bool flags) {
    return arm_add(ctx, a, ~b, carry, flags);
}
static inline uint32_t arm_shift(ArmCpuContext* ctx, uint32_t value,
                                unsigned kind, unsigned count,
                                bool reg_shift, bool flags) {
    uint32_t carry = (ctx->cpsr >> 29) & 1;
    uint32_t result = value;
    if (!reg_shift && count == 0 && (kind == 1 || kind == 2)) count = 32;
    if (!reg_shift && count == 0 && kind == 3) {
        result = (value >> 1) | (carry << 31);
        carry = value & 1;
    } else if (count != 0) {
        if (kind == 0) {
            carry = count <= 32 ? ((value >> (32 - count)) & 1) : 0;
            result = count < 32 ? value << count : 0;
        } else if (kind == 1) {
            carry = count <= 32 ? ((value >> (count - 1)) & 1) : 0;
            result = count < 32 ? value >> count : 0;
        } else if (kind == 2) {
            carry = count < 32 ? ((value >> (count - 1)) & 1) : value >> 31;
            result = count < 32 ? ((value >> count) | ((value & 0x80000000u)
                     ? (~0u << (32 - count)) : 0)) : ((value & 0x80000000u) ? ~0u : 0);
        } else {
            unsigned shift = count & 31;
            result = shift ? ((value >> shift) | (value << (32 - shift))) : value;
            carry = result >> 31;
        }
    }
    if (flags) {
        ctx->cpsr = (ctx->cpsr & ~0x20000000u) | (carry << 29);
        arm_set_nz(ctx, result);
    }
    return result;
}
'''
