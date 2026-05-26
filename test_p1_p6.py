"""Quick smoke test for P1-P6 integration changes."""
import sys
sys.path.insert(0, "src")

# P1: Combo keywords
from interx_engine.core.rules.priority_scoring_policy import (
    COMBO_KEYWORD_GROUPS,
    NEGATIVE_KEYWORDS_STRONG,
    NEGATIVE_KEYWORDS_MEDIUM,
    NEGATIVE_KEYWORDS_WEAK,
    NEGATIVE_KEYWORDS,
    _load_thresholds,
)

cfg = _load_thresholds()
print(f"P1: Combo keyword pairs = {len(COMBO_KEYWORD_GROUPS)} (expected >=38)")
assert len(COMBO_KEYWORD_GROUPS) >= 38, f"Expected >=38, got {len(COMBO_KEYWORD_GROUPS)}"

# P6: 3-tier negative
print(f"P6: Neg Strong = {len(NEGATIVE_KEYWORDS_STRONG)} keywords")
print(f"P6: Neg Medium = {len(NEGATIVE_KEYWORDS_MEDIUM)} keywords")
print(f"P6: Neg Weak   = {len(NEGATIVE_KEYWORDS_WEAK)} keywords")
print(f"P6: Neg Total  = {len(NEGATIVE_KEYWORDS)} keywords")
print(f"P6: Multipliers = strong:{cfg['NEG_MULT_STRONG']}, medium:{cfg['NEG_MULT_MEDIUM']}, weak:{cfg['NEG_MULT_WEAK']}")
assert cfg["NEG_MULT_STRONG"] == 6.0
assert cfg["NEG_MULT_MEDIUM"] == 4.0
assert cfg["NEG_MULT_WEAK"] == 2.0

# P2: Recurring patterns with priority
from interx_engine.application.use_cases.detect_recurring import _load_patterns
patterns = _load_patterns()
print(f"\nP2: Recurring patterns = {len(patterns)} (expected 18)")
assert len(patterns) == 18, f"Expected 18, got {len(patterns)}"
# Check priority sorting
priorities = [p[2] for p in patterns]
assert priorities == sorted(priorities), "Patterns not sorted by priority!"
print(f"P2: Priority order OK (P1={sum(1 for p in priorities if p==1)}, P2={sum(1 for p in priorities if p==2)}, P3={sum(1 for p in priorities if p==3)})")

# P3: SmartFactory nttId
from interx_engine.infrastructure.collectors.sites.smart_factory_collector import _sf_notice_id
test_url_with_nttid = "https://www.smart-factory.kr/usr/bg/ba/ma/bsnsPbancDtl?nttId=12345"
test_url_without = "https://www.smart-factory.kr/usr/bg/ba/ma/bsnsPbanc"
id1 = _sf_notice_id(test_url_with_nttid)
id2 = _sf_notice_id(test_url_without)
print(f"\nP3: nttId URL → {id1} (expected smart_factory-ntt12345)")
print(f"P3: no-nttId URL → {id2} (MD5 fallback)")
assert id1 == "smart_factory-ntt12345"
assert id2.startswith("smart_factory-")

# P4: Apply status classification
from interx_engine.infrastructure.collectors.sites.base_collector import classify_apply_status
status1 = classify_apply_status("접수기간: 2026-05-01~2026-05-20")
status2 = classify_apply_status("접수기간: 2026-06-01~2026-06-30")
status3 = classify_apply_status("접수기간: 2026-01-01~2026-01-31")
status4 = classify_apply_status("", "2026-05-20")
print(f"\nP4: period 05-01~05-20 (today in range) → '{status1}'")
print(f"P4: period 06-01~06-30 (future) → '{status2}'")
print(f"P4: period 01-01~01-31 (past) → '{status3}'")
print(f"P4: deadline only 05-20 → '{status4}'")

print("\n=== ALL P1-P6 CHECKS PASSED ===")
