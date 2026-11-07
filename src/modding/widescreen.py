#!/usr/bin/env python3
"""
Widescreen & Ultrawide Camera Geometry Patcher
Part of the Automated Game ROM Recompiler Modding SDK.

Calculates aspect-ratio adjustments, Hor+ Field-of-View (FOV) expansion,
3D projection matrix scales, and 2D HUD preservation bounds for 16:9, 21:9, and 32:9 displays.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional


class AspectRatio(Enum):
    RATIO_4_3 = (4, 3, 4.0 / 3.0, "Standard Retro (N64, PS1, SNES, NES)")
    RATIO_3_2 = (3, 2, 3.0 / 2.0, "Game Boy Advance")
    RATIO_16_10 = (16, 10, 16.0 / 10.0, "16:10 PC Widescreen")
    RATIO_16_9 = (16, 9, 16.0 / 9.0, "16:9 Modern HD Widescreen")
    RATIO_21_9 = (21, 9, 21.0 / 9.0, "21:9 Cinema Ultrawide")
    RATIO_32_9 = (32, 9, 32.0 / 9.0, "32:9 Super Ultrawide")

    def __init__(self, num: int, den: int, value: float, desc: str):
        self.num = num
        self.den = den
        self.ratio = value
        self.desc = desc

    @classmethod
    def from_string(cls, name: str) -> "AspectRatio":
        clean = name.strip().replace(":", "_").replace("/", "_").lower()
        mapping = {
            "4_3": cls.RATIO_4_3,
            "3_2": cls.RATIO_3_2,
            "16_10": cls.RATIO_16_10,
            "16_9": cls.RATIO_16_9,
            "21_9": cls.RATIO_21_9,
            "32_9": cls.RATIO_32_9,
        }
        if clean in mapping:
            return mapping[clean]
        raise ValueError(f"Unknown aspect ratio '{name}'. Supported: 4:3, 3:2, 16:10, 16:9, 21:9, 32:9")


class WidescreenMode(str, Enum):
    HOR_PLUS = "HOR_PLUS"       # Expands horizontal FOV without stretching geometry (recommended)
    PILLARBOX = "PILLARBOX"     # Maintains native aspect with centered letter/pillarboxing
    STRETCH = "STRETCH"         # Uniform stretch to fit window bounds


@dataclass
class ViewportBounds:
    x: int
    y: int
    width: int
    height: int
    pillar_left: int
    pillar_right: int
    hud_offset_x: int


class WidescreenPatcher:
    """
    Computes geometry transformations and projection matrix modifications
    to eliminate stretching on modern displays.
    """

    def __init__(
        self,
        native_ratio: AspectRatio = AspectRatio.RATIO_4_3,
        target_ratio: AspectRatio = AspectRatio.RATIO_16_9,
        mode: WidescreenMode = WidescreenMode.HOR_PLUS
    ):
        self.native_ratio = native_ratio
        self.target_ratio = target_ratio
        self.mode = mode

    @property
    def fov_multiplier(self) -> float:
        """
        Calculates the horizontal FOV expansion factor for Hor+ rendering.
        """
        if self.mode == WidescreenMode.HOR_PLUS:
            return self.target_ratio.ratio / self.native_ratio.ratio
        return 1.0

    @property
    def projection_x_scale(self) -> float:
        """
        Scale factor for the (0,0) component of a 4x4 perspective projection matrix.
        X_scale = X_native * (native_ratio / target_ratio)
        Multiplying X by this ratio expands horizontal coverage without distortion.
        """
        if self.mode == WidescreenMode.HOR_PLUS:
            return self.native_ratio.ratio / self.target_ratio.ratio
        return 1.0

    def compute_viewport(self, window_width: int, window_height: int) -> ViewportBounds:
        """
        Calculates viewport rendering rectangle and pillarbox borders for any target window size.
        """
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in (window_width, window_height)):
            raise ValueError("Window dimensions must be positive integers")
        win_aspect = window_width / window_height

        if self.mode == WidescreenMode.PILLARBOX:
            # Fit native aspect into window bounds
            target_val = self.native_ratio.ratio
            if win_aspect > target_val:
                # Window is wider than game: pillarbox left and right
                vp_h = window_height
                vp_w = int(vp_h * target_val)
                vp_x = (window_width - vp_w) // 2
                vp_y = 0
                return ViewportBounds(
                    x=vp_x, y=vp_y, width=vp_w, height=vp_h,
                    pillar_left=vp_x, pillar_right=window_width - (vp_x + vp_w),
                    hud_offset_x=0
                )
            else:
                # Window is taller than game: letterbox top and bottom
                vp_w = window_width
                vp_h = int(vp_w / target_val)
                vp_x = 0
                vp_y = (window_height - vp_h) // 2
                return ViewportBounds(
                    x=vp_x, y=vp_y, width=vp_w, height=vp_h,
                    pillar_left=0, pillar_right=0,
                    hud_offset_x=0
                )
        else:
            # Hor+ mode: full window is rendered
            hud_margin = int((window_width - (window_height * self.native_ratio.ratio)) / 2)
            hud_margin = max(0, hud_margin)
            return ViewportBounds(
                x=0,
                y=0,
                width=window_width,
                height=window_height,
                pillar_left=0,
                pillar_right=0,
                hud_offset_x=hud_margin
            )

    def patch_matrix_4x4(self, matrix: list) -> list:
        """
        Patches a 16-element row-major or column-major 4x4 projection matrix.
        Adjusts matrix[0] (or matrix[0][0]) by projection_x_scale.
        """
        if len(matrix) != 16:
            raise ValueError("Matrix must be 16 elements (4x4)")

        patched = list(matrix)
        patched[0] = patched[0] * self.projection_x_scale
        return patched

    def emit_c_widescreen_shim(self) -> str:
        """
        Emits standard C99 runtime header for native widescreen matrix adjustment.
        """
        lines = [
            "/* Automated Recompiler Framework — Widescreen & Ultrawide Camera Patcher */",
            "#ifndef RECOMP_WIDESCREEN_H",
            "#define RECOMP_WIDESCREEN_H",
            "",
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "",
            f"#define RECOMP_NATIVE_ASPECT ({self.native_ratio.ratio:.8f}f)",
            f"#define RECOMP_TARGET_ASPECT ({self.target_ratio.ratio:.8f}f)",
            f"#define RECOMP_PROJECTION_X_SCALE ({self.projection_x_scale:.8f}f)",
            f"#define RECOMP_FOV_MULTIPLIER ({self.fov_multiplier:.8f}f)",
            "",
            "/* Adjusts a 4x4 float projection matrix in-place for Hor+ widescreen */",
            "static inline void recomp_apply_widescreen_matrix(float* m) {",
            "    if (m) {",
            "        m[0] *= RECOMP_PROJECTION_X_SCALE;",
            "    }",
            "}",
            "",
            "/* Computes HUD margin offset to keep 2D UI centered at 4:3 safe areas */",
            "static inline int recomp_get_hud_safe_margin(int screen_width, int screen_height) {",
            f"    float native_w = (float)screen_height * RECOMP_NATIVE_ASPECT;",
            "    int margin = (int)(((float)screen_width - native_w) * 0.5f);",
            "    return (margin > 0) ? margin : 0;",
            "}",
            "",
            "#endif /* RECOMP_WIDESCREEN_H */",
        ]
        return "\n".join(lines)
