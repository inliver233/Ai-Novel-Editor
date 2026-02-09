from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpacingTokens:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24


@dataclass(frozen=True)
class FontTokens:
    xs: int = 9
    sm: int = 10
    md: int = 11
    lg: int = 12
    xl: int = 13


@dataclass(frozen=True)
class RadiusTokens:
    sm: int = 4
    md: int = 6
    lg: int = 8
    pill: int = 999


SPACING = SpacingTokens()
FONT = FontTokens()
RADIUS = RadiusTokens()

