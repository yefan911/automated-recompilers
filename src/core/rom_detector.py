#!/usr/bin/env python3
"""
Universal Console ROM Detector & Header Analyzer
Part of Automated Recompiler Framework.

Detects console target, endianness, entry point, internal memory layout,
and header metadata across GBA, N64, PS1, NES, and SNES.
"""

import os
import sys
import struct
import re
from typing import Dict, Any, Optional

GBA_LOGO_START = bytes([
    0x24, 0xFF, 0xAE, 0x51, 0x69, 0x9A, 0xA2, 0x21,
    0x3D, 0x84, 0x82, 0x0A, 0x84, 0xE4, 0x09, 0xAD
])


def detect_gba(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) < 0xC0:
        return None
    # GBA ROMs contain the Nintendo logo at 0x04..0x9F
    if data[0x04:0x14] == GBA_LOGO_START:
        title = data[0xA0:0xAC].decode('ascii', errors='ignore').strip('\x00').strip()
        game_code = data[0xAC:0xB0].decode('ascii', errors='ignore').strip('\x00').strip()
        maker_code = data[0xB0:0xB2].decode('ascii', errors='ignore').strip('\x00').strip()
        version = data[0xBC]
        checksum = data[0xBD]
        return {
            "console": "Game Boy Advance (GBA)",
            "architecture": "ARM7TDMI (32-bit ARM + 16-bit Thumb)",
            "endianness": "little",
            "entry_point": "0x08000000",
            "title": title,
            "game_code": game_code,
            "maker_code": maker_code,
            "version": version,
            "checksum": hex(checksum),
            "size_bytes": len(data),
            "rom_mapped_vram": "0x08000000",
        }
    return None


def detect_n64(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) < 0x40:
        return None
    magic = data[0:4]
    endian = None
    normalized_data = data

    if magic == b'\x80\x37\x12\x40':
        endian = "Big-Endian (.z64)"
    elif magic == b'\x40\x12\x37\x80':
        endian = "Little-Endian (.n64)"
        # Convert to big endian for parsing
        b = bytearray(data[:0x40])
        for i in range(0, len(b), 4):
            b[i:i+4] = b[i:i+4][::-1]
        normalized_data = bytes(b)
    elif magic == b'\x37\x80\x40\x12':
        endian = "Byte-Swapped (.v64)"
        b = bytearray(data[:0x40])
        for i in range(0, len(b), 2):
            b[i], b[i+1] = b[i+1], b[i]
        normalized_data = bytes(b)
    else:
        return None

    entry_point = struct.unpack(">I", normalized_data[0x08:0x0C])[0]
    crc1 = struct.unpack(">I", normalized_data[0x10:0x14])[0]
    crc2 = struct.unpack(">I", normalized_data[0x14:0x18])[0]
    title = normalized_data[0x20:0x34].decode('latin-1', errors='ignore').strip('\x00').strip()
    media_format = chr(normalized_data[0x3B]) if 32 <= normalized_data[0x3B] <= 126 else '?'
    cart_id = normalized_data[0x3C:0x3E].decode('latin-1', errors='ignore').strip()
    country_code = chr(normalized_data[0x3E]) if 32 <= normalized_data[0x3E] <= 126 else '?'

    return {
        "console": "Nintendo 64 (N64)",
        "architecture": "MIPS III (VR4300i 64-bit / 32-bit mode) + RSP",
        "endianness": endian,
        "entry_point": hex(entry_point),
        "crc1": hex(crc1),
        "crc2": hex(crc2),
        "title": title,
        "cart_id": cart_id,
        "country_code": country_code,
        "size_bytes": len(data),
    }


def _ps1_cd_layout(data: bytes):
    for sector_size, user_offset in ((2352, 24), (2352, 16), (2048, 0)):
        pvd = 16 * sector_size + user_offset
        if data[pvd + 1:pvd + 6] == b"CD001":
            return sector_size, user_offset
    return None


def _ps1_header_info(header: bytes, offset: int, size: int, layout=None, title=None):
    if len(header) < 2048 or not header.startswith(b"PS-X EXE"):
        return None
    if layout is None:
        if offset == 0:
            layout = (2048, 0)
        elif offset >= 24 and (offset - 24) % 2352 == 0:
            layout = (2352, 24)
        elif offset >= 16 and (offset - 16) % 2352 == 0:
            layout = (2352, 16)
        elif offset % 2048 == 0:
            layout = (2048, 0)
        else:
            return None
    elif (offset - layout[1]) % layout[0]:
        return None
    initial_pc, initial_gp, text_vram, text_size = struct.unpack_from("<IIII", header, 0x10)
    stack_base, stack_offset = struct.unpack_from("<II", header, 0x30)
    physical_address = text_vram & 0x1FFFFFFF
    if text_vram >> 29 not in (0, 4, 5) or physical_address + text_size > 0x200000:
        return None
    info = {
        "console": "Sony PlayStation 1 (PS-X EXE)" if offset == 0 else "Sony PlayStation 1 (CD Image)",
        "architecture": "MIPS I (R3000A 32-bit + GTE Coprocessor 2)",
        "endianness": "little",
        "entry_point": hex(initial_pc),
        "initial_gp": hex(initial_gp),
        "text_vram": hex(text_vram),
        "text_size": text_size,
        "initial_sp": hex((stack_base + stack_offset) & 0xFFFFFFFF if stack_base else 0),
        "marker": header[0x4C:0x60].decode("ascii", errors="ignore").strip("\x00 "),
        "exe_offset": offset,
        "sector_size": layout[0],
        "sector_user_offset": layout[1],
        "size_bytes": size,
    }
    if offset:
        info["title"] = title or "PlayStation CD Image"
    return info


def detect_ps1(data: bytes) -> Optional[Dict[str, Any]]:
    layout = _ps1_cd_layout(data)
    title = None
    if layout:
        pvd = 16 * layout[0] + layout[1]
        title = data[pvd + 40:pvd + 72].decode("ascii", errors="ignore").strip("\x00 ")
    start = 0
    while True:
        offset = data.find(b"PS-X EXE", start)
        if offset < 0:
            return None
        info = _ps1_header_info(data[offset:offset + 2048], offset, len(data), layout, title)
        if info:
            return info
        start = offset + 8


def _read_cd_payload(stream, layout, offset: int, size: int, file_size: int) -> bytes:
    """Read an ISO logical byte range without raw-sector framing bytes."""
    if offset < 0 or size < 0:
        return b""
    sector_size, user_offset = layout
    parts = []
    while size:
        sector, within = divmod(offset, 2048)
        amount = min(size, 2048 - within)
        physical = sector * sector_size + user_offset + within
        if physical + amount > file_size:
            return b""
        stream.seek(physical)
        part = stream.read(amount)
        if len(part) != amount:
            return b""
        parts.append(part)
        offset += amount
        size -= amount
    return b"".join(parts)


def _ps1_boot_header(stream, layout, sample: bytes, file_size: int):
    """Resolve SYSTEM.CNF's BOOT path through bounded ISO-9660 directories."""
    pvd = 16 * layout[0] + layout[1]
    root = sample[pvd + 156:pvd + 190]
    if len(root) < 34 or root[0] < 34:
        return False, None

    def directory(record):
        lba = struct.unpack_from("<I", record, 2)[0]
        length = struct.unpack_from("<I", record, 10)[0]
        if length > 131072:
            return {}
        data = _read_cd_payload(stream, layout, lba * 2048, length, file_size)
        entries = {}
        pos = 0
        while pos < len(data):
            rec_len = data[pos]
            if not rec_len:
                pos = ((pos // 2048) + 1) * 2048
                continue
            record = data[pos:pos + rec_len]
            if len(record) != rec_len or rec_len < 34 or record[32] > rec_len - 33:
                return {}
            name = record[33:33 + record[32]].decode("ascii", errors="ignore").upper().split(";")[0]
            entries[name] = record
            pos += rec_len
        return entries

    entries = directory(root)
    config = entries.get("SYSTEM.CNF")
    if config is None:
        return False, None
    config_size = struct.unpack_from("<I", config, 10)[0]
    if config_size > 65536:
        return True, None
    config_lba = struct.unpack_from("<I", config, 2)[0]
    config_data = _read_cd_payload(stream, layout, config_lba * 2048, config_size, file_size)
    match = re.search(rb"(?im)^\s*BOOT\s*=\s*cdrom:\s*[\\/]*([^\r\n]+)", config_data)
    if not match:
        return False, None
    path = match.group(1).decode("ascii", errors="ignore").strip().replace("/", "\\")
    components = [part.upper().split(";")[0] for part in path.split("\\") if part]
    if not components or len(components) > 16 or any(part in (".", "..") for part in components):
        return True, None
    for index, component in enumerate(components):
        record = entries.get(component)
        if record is None:
            return True, None
        if index < len(components) - 1:
            if not record[25] & 2:
                return True, None
            entries = directory(record)
    if record[25] & 2:
        return True, None
    lba = struct.unpack_from("<I", record, 2)[0]
    length = struct.unpack_from("<I", record, 10)[0]
    header = _read_cd_payload(stream, layout, lba * 2048, min(length, 2048), file_size)
    physical = lba * layout[0] + layout[1]
    info = _ps1_header_info(header, physical, file_size, layout)
    if info and 2048 + info["text_size"] > length:
        return True, None
    return True, info


def find_ps1_executable(filepath: str, sample: bytes = None) -> Optional[Dict[str, Any]]:
    """Locate a standalone or CD boot executable without loading the whole image."""
    file_size = os.path.getsize(filepath)
    with open(filepath, "rb") as stream:
        if sample is None:
            sample = stream.read(131072)
        layout = _ps1_cd_layout(sample)
        if layout:
            boot_declared, info = _ps1_boot_header(stream, layout, sample, file_size)
            if boot_declared:
                if info:
                    pvd = 16 * layout[0] + layout[1]
                    info["title"] = sample[pvd + 40:pvd + 72].decode("ascii", errors="ignore").strip("\x00 ")
                return info
        info = detect_ps1(sample)
        if info or layout is None:
            if info:
                info["size_bytes"] = file_size
            return info
        # Some discs have no SYSTEM.CNF. Search sector-aligned headers in chunks.
        stream.seek(0)
        tail = b""
        position = 0
        while True:
            chunk = stream.read(131072)
            if not chunk:
                return None
            data = tail + chunk
            start = 0
            while True:
                local = data.find(b"PS-X EXE", start)
                if local < 0:
                    break
                physical = position - len(tail) + local
                info = _ps1_header_info(data[local:local + 2048], physical, file_size, layout)
                if info:
                    pvd = 16 * layout[0] + layout[1]
                    info["title"] = sample[pvd + 40:pvd + 72].decode("ascii", errors="ignore").strip("\x00 ")
                    return info
                start = local + 8
            tail = data[-2047:]
            position += len(chunk)


def detect_nes(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) >= 16 and data.startswith(b"NES\x1a"):
        prg_rom_chunks = data[4]  # in 16KB units
        chr_rom_chunks = data[5]  # in 8KB units
        flags6 = data[6]
        flags7 = data[7]
        mapper = ((flags7 & 0xF0) | (flags6 >> 4))
        has_battery = bool(flags6 & 0x02)
        has_trainer = bool(flags6 & 0x04)
        mirroring = "Vertical" if (flags6 & 0x01) else "Horizontal"

        # Read 6502 Reset vector from end of PRG ROM ($FFFC)
        entry_point = None
        prg_size = prg_rom_chunks * 16384
        reset_vec_offset = 16 + (512 if has_trainer else 0) + prg_size - 4
        if prg_size and len(data) >= reset_vec_offset + 2:
            reset_val = data[reset_vec_offset] | (data[reset_vec_offset + 1] << 8)
            entry_point = hex(reset_val)

        return {
            "console": "Nintendo Entertainment System (NES)",
            "architecture": "MOS 6502 (Ricoh 2A03/2A07)",
            "endianness": "little",
            "entry_point": entry_point,
            "prg_rom_size_kb": prg_rom_chunks * 16,
            "chr_rom_size_kb": chr_rom_chunks * 8,
            "mapper_number": mapper,
            "has_battery": has_battery,
            "has_trainer": has_trainer,
            "mirroring": mirroring,
            "size_bytes": len(data),
        }
    return None


def _snes_header_info(header: bytes, offset: int, copier_size: int, mapping: str, file_size: int):
    if len(header) < 64:
        return None
    map_mode = header[0x15]
    modes = {"LoROM": (0x20, 0x22, 0x23, 0x30, 0x32), "HiROM": (0x21, 0x31), "ExHiROM": (0x25, 0x35)}
    reset = struct.unpack_from("<H", header, 0x3C)[0]
    if map_mode not in modes[mapping] or reset < 0x8000:
        return None
    return {
        "console": "Super Nintendo (SNES)",
        "architecture": "W65C816S (16-bit 65816)",
        "endianness": "little",
        "entry_point": hex(reset),
        "title": header[:21].decode("ascii", errors="ignore").strip("\x00 "),
        "map_mode": hex(map_mode),
        "mapping": mapping,
        "header_offset": offset,
        "copier_header_size": copier_size,
        "size_bytes": file_size,
    }


def detect_snes(data: bytes) -> Optional[Dict[str, Any]]:
    candidates = []
    for copier_size in (0, 512):
        for base, mapping in ((0x7FC0, "LoROM"), (0xFFC0, "HiROM"), (0x40FFC0, "ExHiROM")):
            offset = base + copier_size
            header = data[offset:offset + 64]
            info = _snes_header_info(header, offset, copier_size, mapping, len(data))
            if info:
                checksum, complement = struct.unpack_from("<HH", header, 0x1C)
                score = int((checksum ^ complement) == 0xFFFF) * 2
                score += int((len(data) % 0x8000 == 512) == bool(copier_size))
                candidates.append((score, info))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def inspect_file(filepath: str) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(filepath):
        print(f"Error: file not found '{filepath}'")
        return None

    file_size = os.path.getsize(filepath)
    with open(filepath, "rb") as f:
        # Read header region up to 128KB (sufficient for all console header formats)
        # Prevents loading hundreds of megabytes into RAM on CD/ISO images
        data = f.read(131072)

    snes_info = None
    if os.path.splitext(filepath)[1].lower() in (".sfc", ".smc"):
        copier_size = 512 if file_size % 0x8000 == 512 else 0
        offset = 0x40FFC0 + copier_size
        if file_size >= offset + 64:
            with open(filepath, "rb") as stream:
                stream.seek(offset)
                snes_info = _snes_header_info(stream.read(64), offset, copier_size, "ExHiROM", file_size)
    detectors = [
        detect_gba,
        detect_n64,
        lambda sample: find_ps1_executable(filepath, sample),
        detect_nes,
        lambda sample: snes_info or detect_snes(sample),
    ]
    for detector in detectors:
        info = detector(data)
        if info:
            info["filename"] = os.path.basename(filepath)
            info["path"] = os.path.abspath(filepath)
            info["size_bytes"] = file_size
            return info

    return {
        "filename": os.path.basename(filepath),
        "console": "Unknown or Raw Image",
        "size_bytes": file_size,
        "magic_hex": data[:16].hex(' '),
    }


def scan_roms_directory(rom_dir: str = "roms"):
    if not os.path.exists(rom_dir):
        print(f"Directory '{rom_dir}' does not exist.")
        return

    found = 0
    print(f"Scanning '{rom_dir}' for game ROMs...\n" + "=" * 60)
    for root, _, files in os.walk(rom_dir):
        for file in files:
            if file == ".gitkeep":
                continue
            full_path = os.path.join(root, file)
            info = inspect_file(full_path)
            if info:
                found += 1
                print(f"\n[FILE] {info.get('filename')}")
                for k, v in info.items():
                    if k not in ("filename", "path"):
                        print(f"  * {k.replace('_', ' ').title()}: {v}")
    print("=" * 60)
    if found == 0:
        print(f"No ROMs found in '{rom_dir}'. Place ROM files into 'roms/gba', 'roms/n64', etc.")
    else:
        print(f"Total ROMs detected: {found}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = inspect_file(sys.argv[1])
        if result:
            for k, v in result.items():
                print(f"{k}: {v}")
    else:
        scan_roms_directory()
