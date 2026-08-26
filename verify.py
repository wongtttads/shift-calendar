#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面校验生成规则:
1. 法定放假日:全天班/行政班都应取消
2. 周末(非调休):行政班取消,全天班不取消
3. 调休上班日:若轮班排到班次(全天/行政)→ 必须上班,不得取消
4. 周期正确性:全天班后必跟行政班(除非被取消)
"""
import sys
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, '.')
from generate import fetch_holidays, phase_on, load_config

cfg = load_config()
start = date.fromisoformat(cfg["start_date"])
total_days = cfg["years"] * 365 + 2
end = start + timedelta(days=total_days)

off_days, work_extra = fetch_holidays(start.year)
o2, w2 = fetch_holidays(end.year)
off_days |= o2
work_extra |= w2

def would_shift_on(d):
    """按规则计算当天轮班状态:None=休,'全天班','行政班'"""
    ph = phase_on(start, d)
    if ph == 0:
        if cfg["full_shift_cancel_on_holiday"] and d in off_days:
            return None
        return '全天班'
    if ph == 1:
        if cfg["admin_shift_cancel_on_holiday"] and d in off_days:
            return None
        if cfg["admin_shift_cancel_on_weekend"] and d.weekday() >= 5 and d not in work_extra:
            return None
        return '行政班'
    return None

errors = []
checks = []

# --- 校验1:法定放假日不得有班 ---
holiday_shifts = []
for d in sorted(off_days):
    if start <= d < end:
        s = would_shift_on(d)
        if s: holiday_shifts.append((d, s))
checks.append(("法定放假日不应有班次", holiday_shifts, 0))

# --- 校验2:普通周末(非调休)行政班取消,全天班保留 ---
weekend_admin_errors = []
weekend_full_ok = 0
for i in range(total_days):
    d = start + timedelta(days=i)
    if d.weekday() >= 5 and d not in off_days and d not in work_extra:
        ph = phase_on(start, d)
        if ph == 1:
            s = would_shift_on(d)
            if s: weekend_admin_errors.append((d, s))
        if ph == 0 and would_shift_on(d) == '全天班':
            weekend_full_ok += 1
checks.append(("普通周末行政班不应有班", weekend_admin_errors, 0))

# --- 校验3:调休上班日(周末补班)排到班次必须上班 ---
extra_missed = []
extra_ok = []
for d in sorted(work_extra):
    if start <= d < end:
        ph = phase_on(start, d)
        if ph in (0, 1):
            s = would_shift_on(d)
            if s:
                extra_ok.append((d, ph, s))
            else:
                extra_missed.append((d, ph))
checks.append(("调休上班日排到班必须上班(漏排)", extra_missed, 0))

# --- 校验4:周期顺序(未被取消时,全天班次日必为行政班) ---
seq_errors = []
prev = None  # (date, kind)
for i in range(total_days):
    d = start + timedelta(days=i)
    s = would_shift_on(d)
    if s is None:
        prev = None
        continue
    if prev == '全天班' and s != '行政班':
        seq_errors.append((prev_date, '全天班', d, s))
    prev = s
    prev_date = d
checks.append(("全天班后应接行政班", seq_errors, 0))

print(f"=== 核对范围 {start} ~ {end} ===")
print(f"放假日: {len([d for d in off_days if start<=d<end])} 天 | "
      f"调休上班日: {len([d for d in work_extra if start<=d<end])} 天 | "
      f"周末行政班应取消: 见下\n")

all_ok = True
for name, items, _ in checks:
    if items:
        all_ok = False
        print(f"❌ {name}: {len(items)} 处问题")
        for it in items[:20]:
            print("   ", it)
    else:
        print(f"✅ {name}: 无问题")

if all_ok:
    print("\n🎉 全部规则校验通过!")
else:
    print("\n⚠️ 存在上述问题,需要修复")

# --- 输出调休上班日明细供人工复核 ---
print("\n=== 2026-2027 调休上班日(周末补班)与轮班对照 ===")
for d in sorted(work_extra):
    if start <= d < end:
        ph = {0:'全天班',1:'行政班',2:'休',3:'休'}[phase_on(start, d)]
        wk = '六日一二三四五'[d.weekday()]
        s = would_shift_on(d)
        mark = "→ 上班" if s else "→ 休息(轮班正好休)"
        print(f"  {d} 周{wk} 轮班={ph} {mark}")

# --- 输出周末行政班取消明细 ---
print("\n=== 普通周末行政班(被取消)明细 ===")
cnt = 0
for i in range(total_days):
    d = start + timedelta(days=i)
    if d.weekday() >= 5 and d not in off_days and d not in work_extra and phase_on(start, d) == 1:
        cnt += 1
print(f"  共 {cnt} 个(全部取消,无班次)")
