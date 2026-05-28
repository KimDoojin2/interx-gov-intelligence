# -*- coding: utf-8 -*-
"""
수집기 가동률 점검 스크립트
각 enabled 사이트에 1페이지만 수집 시도하여 성공/실패/0건 리포트.

실행:
  venv/Scripts/python check_collectors.py
"""
import sys
import time
import logging
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.basicConfig(level=logging.WARNING, format="%(message)s")

sys.path.insert(0, "src")

from interx_engine.infrastructure.collectors.collector_factory import (
    build_collectors, get_registry, _enabled_site_keys,
)


def main():
    enabled = _enabled_site_keys() or set()
    registry = get_registry()

    targets = sorted(k for k in registry if k in enabled and k != "mock")
    print(f"\n{'='*60}")
    print(f"  InterX 수집기 가동률 점검 — {len(targets)}개 사이트")
    print(f"{'='*60}\n")

    results = []
    for site_key in targets:
        print(f"  [{site_key:12s}] 수집 중...", end="", flush=True)
        t0 = time.time()
        try:
            col = registry[site_key](max_pages=1, timeout=15)
            notices = col.collect(execution_id="HEALTH-CHECK")
            elapsed = time.time() - t0
            count = len(notices)
            status = "OK" if count > 0 else "EMPTY"
            symbol = "+" if count > 0 else "0"
            print(f"\r  [{site_key:12s}] {symbol} {count:3d}건  ({elapsed:.1f}s)")
            results.append((site_key, status, count, elapsed, ""))
        except Exception as e:
            elapsed = time.time() - t0
            err_msg = str(e)[:60]
            print(f"\r  [{site_key:12s}] X FAIL  ({elapsed:.1f}s) {err_msg}")
            results.append((site_key, "FAIL", 0, elapsed, err_msg))

    # Summary
    ok    = [r for r in results if r[1] == "OK"]
    empty = [r for r in results if r[1] == "EMPTY"]
    fail  = [r for r in results if r[1] == "FAIL"]
    total_notices = sum(r[2] for r in results)
    total_time = sum(r[3] for r in results)

    print(f"\n{'='*60}")
    print(f"  결과 요약")
    print(f"{'='*60}")
    print(f"  정상 (공고 수집):  {len(ok):2d}개  ({total_notices}건)")
    print(f"  빈 결과 (0건):     {len(empty):2d}개")
    print(f"  실패 (에러):       {len(fail):2d}개")
    print(f"  총 소요시간:       {total_time:.1f}초")
    print()

    if empty:
        print("  ⚠️  빈 결과 사이트:")
        for r in empty:
            print(f"       {r[0]}")

    if fail:
        print("  ❌ 실패 사이트:")
        for r in fail:
            print(f"       {r[0]}: {r[4]}")

    print()

    # 가동률
    active = len(ok)
    rate = active / len(results) * 100 if results else 0
    print(f"  가동률: {active}/{len(results)} = {rate:.0f}%")
    print()

    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
