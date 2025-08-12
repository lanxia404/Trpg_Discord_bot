import random
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

DICE_RE = re.compile(
    r"^\s*(?:(?P<count>\d*)d(?P<sides>\d+)(?P<mod>[+-]\d+)?)\s*(?:(?P<cmp><=|>=|<|>)\s*(?P<target>\d+))?\s*$",
    re.IGNORECASE,
)

@dataclass
class RollResult:
    rolls: List[int]
    total: int
    expr: str
    detail: str
    cmp: Optional[str] = None
    target: Optional[int] = None
    is_crit_success: bool = False
    is_crit_failure: bool = False

class DiceError(ValueError):
    pass

def parse_and_roll(expr: str, *, max_dice: int = 100, max_sides: int = 1000,
                   d20_crit_succ: int = 20, d20_crit_fail: int = 1,
                   d100_crit_succ: int = 1, d100_crit_fail: int = 100) -> RollResult:
    m = DICE_RE.match(expr)
    if not m:
        raise DiceError("骰式不合法。範例：d6、2d6+1、d100<=65、d20>=15")

    count_s = m.group("count") or "1"
    sides_s = m.group("sides")
    mod_s = m.group("mod") or "0"
    cmp = m.group("cmp")
    target_s = m.group("target")

    count = int(count_s)
    sides = int(sides_s)
    mod = int(mod_s)
    target = int(target_s) if target_s else None

    if not (1 <= count <= max_dice):
        raise DiceError(f"骰子顆數 1~{max_dice}")
    if not (2 <= sides <= max_sides):
        raise DiceError(f"骰面數 2~{max_sides}")

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + mod

    # 判定大成功/大失敗（依最典型需求：自然值）
    is_crit_success = False
    is_crit_failure = False
    if count == 1 and sides == 20:
        if rolls[0] == d20_crit_succ:
            is_crit_success = True
        elif rolls[0] == d20_crit_fail:
            is_crit_failure = True
    if count == 1 and sides == 100:
        if rolls[0] == d100_crit_succ:
            is_crit_success = True
        elif rolls[0] == d100_crit_fail:
            is_crit_failure = True

    parts = [f"{count}d{sides}"]
    if mod:
        parts.append(f"{mod:+d}")
    if cmp and target is not None:
        parts.append(f" {cmp} {target}")
    detail = f"{' + '.join(map(str, rolls))}{f' {mod:+d}' if mod else ''}"

    return RollResult(
        rolls=rolls,
        total=total,
        expr="".join(parts),
        detail=detail,
        cmp=cmp,
        target=target,
        is_crit_success=is_crit_success,
        is_crit_failure=is_crit_failure,
    )
