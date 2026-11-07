"""Shared status, arithmetic, and stack semantics for generated 65816 C."""


SNES_CPU_HELPERS = r'''
static inline void snes_init_context(SnesCpuContext* ctx) {
    memset(ctx, 0, sizeof(*ctx));
    ctx->sp = 0x01FF;
    ctx->p = 0x34;
    ctx->e = true;
    ctx->spc700_ports[0] = 0xAA;
    ctx->spc700_ports[1] = 0xBB;
    ctx->m7a = ctx->m7d = 0x0100;
}
static inline void snes_set_nz(SnesCpuContext* ctx, uint16_t value, unsigned bits) {
    uint16_t mask = bits == 8 ? 0xFF : 0xFFFF;
    value &= mask;
    ctx->p = (uint8_t)((ctx->p & ~0x82) | (value == 0 ? 2 : 0)
                     | ((value & (1u << (bits - 1))) ? 0x80 : 0));
}
static inline void snes_set_p(SnesCpuContext* ctx, uint8_t value) {
    ctx->p = ctx->e ? (uint8_t)(value | 0x30) : value;
    if (ctx->p & 0x10) { ctx->x &= 0xFF; ctx->y &= 0xFF; }
}
static inline void snes_compare(SnesCpuContext* ctx, uint16_t a, uint16_t b, unsigned bits) {
    uint16_t mask = bits == 8 ? 0xFF : 0xFFFF;
    a &= mask; b &= mask;
    ctx->p = (uint8_t)((ctx->p & ~1) | (a >= b ? 1 : 0));
    snes_set_nz(ctx, (uint16_t)(a - b), bits);
}
static inline void snes_arithmetic(SnesCpuContext* ctx, uint16_t operand, unsigned bits, bool subtract) {
    uint32_t mask = bits == 8 ? 0xFFu : 0xFFFFu;
    uint32_t sign = 1u << (bits - 1);
    uint32_t a = ctx->a & mask, b = operand & mask;
    int carry = ctx->p & 1;
    int32_t raw = subtract ? (int32_t)a - (int32_t)b - (1 - carry)
                           : (int32_t)a + (int32_t)b + carry;
    uint32_t result = (uint32_t)raw & mask;
    bool carry_out = subtract ? raw >= 0 : (uint32_t)raw > mask;
    uint32_t overflow_value = result;
    if (ctx->p & 8) {
        result = 0;
        int chain = subtract ? 1 - carry : carry;
        for (unsigned shift = 0; shift < bits; shift += 4) {
            int digit = subtract ? (int)((a >> shift) & 15) - (int)((b >> shift) & 15) - chain
                                 : (int)((a >> shift) & 15) + (int)((b >> shift) & 15) + chain;
            if (shift + 4 == bits) overflow_value = (uint32_t)digit << shift;
            if (subtract) {
                chain = digit < 0;
                if (chain) digit -= 6;
            } else {
                if (digit > 9) digit += 6;
                chain = digit > 15;
            }
            result |= ((uint32_t)digit & 15) << shift;
        }
        carry_out = subtract ? chain == 0 : chain != 0;
    }
    bool overflow = subtract ? (((a ^ b) & (a ^ overflow_value) & sign) != 0)
                             : (((~(a ^ b)) & (a ^ overflow_value) & sign) != 0);
    ctx->a = bits == 8 ? (uint16_t)((ctx->a & 0xFF00) | result) : (uint16_t)result;
    ctx->p = (uint8_t)((ctx->p & ~0x41) | (carry_out ? 1 : 0) | (overflow ? 0x40 : 0));
    snes_set_nz(ctx, (uint16_t)result, bits);
}
static inline void snes_shift_accumulator(SnesCpuContext* ctx, unsigned kind, unsigned bits) {
    uint32_t mask = bits == 8 ? 0xFFu : 0xFFFFu;
    uint32_t value = ctx->a & mask;
    uint32_t carry = ctx->p & 1;
    uint32_t next_carry = (kind == 0 || kind == 2) ? value >> (bits - 1) : value & 1;
    uint32_t result = (kind == 0 || kind == 2) ? (value << 1) & mask : value >> 1;
    if (kind == 2) result |= carry;
    if (kind == 3) result |= carry << (bits - 1);
    ctx->a = bits == 8 ? (uint16_t)((ctx->a & 0xFF00) | result) : (uint16_t)result;
    ctx->p = (uint8_t)((ctx->p & ~1) | next_carry);
    snes_set_nz(ctx, (uint16_t)result, bits);
}
static inline void snes_push8(SnesCpuContext* ctx, uint8_t value) {
    snes_write8(ctx, ctx->sp, value);
    ctx->sp = (uint16_t)(ctx->sp - 1);
    if (ctx->e) ctx->sp = (uint16_t)(0x100 | (ctx->sp & 0xFF));
}
static inline uint8_t snes_pop8(SnesCpuContext* ctx) {
    ctx->sp = (uint16_t)(ctx->sp + 1);
    if (ctx->e) ctx->sp = (uint16_t)(0x100 | (ctx->sp & 0xFF));
    return snes_read8(ctx, ctx->sp);
}
static inline void snes_push16(SnesCpuContext* ctx, uint16_t value) {
    snes_push8(ctx, (uint8_t)(value >> 8));
    snes_push8(ctx, (uint8_t)value);
}
static inline uint16_t snes_pop16(SnesCpuContext* ctx) {
    uint16_t lo = snes_pop8(ctx);
    uint16_t hi = snes_pop8(ctx);
    return (uint16_t)(lo | (hi << 8));
}
'''
