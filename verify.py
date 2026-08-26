#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面校验:直接对照 calendar.ics 实际输出与期望规则。

规则:
1. 法定放假日:全天班必须上班;行政班必须取消
2. 普通周末(非调休):行政班取消,全天班照常
3. 调休上班日(周末补班):轮班排到班次必须上班,不得因周末取消
4. 周期正确性:全天班次日必为行政班(未被取消时)
5. ICS 结构:VEVENT 配对、UID 唯一
"""
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, '.')
from generate import fetch_holidays, phase_on, load_config

cfg = load_config()
start = date.fromisoformat(cfg["start_date"])

# ---- 读取实际 calendar.ics 输出 ----
raw = open('calendar.ics', 'rb').read().decode('utf-8')
events = dict(re.findall(r'DTSTART;VALUE=DATE:(\d{8})\r\nSUMMARY:([^\r\n]+)', raw))
dates = sorted(events.keys())
if not dates:
    print("❌ calendar.ics 为空或解析失败")
    sys.exit(1)
d0 = date.fromisoformat(f'{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]}')
d1 = date.fromisoformat(f'{dates[-1][:4]}-{dates[-1][4:6]}-{dates[-1][6:]}')

# ---- 覆盖范围内所有年份的节假日数据 ----
off_days, work_extra = set(), set()
for y in range(d0.year, d1.year + 1):
    o, w = fetch_holidays(y)
    off_days |= o
    work_extra |= w


def expect_on(d):
    """期望班次:None=无班,'全天班'/'行政班'=有班"""
    ph = phase_on(start, d)
    if ph == 0:
        return '全天班'  # 铁打不动
    if ph == 1:
        if cfg["admin_shift_cancel_on_holiday"] and d in off_days:
            return None
        if cfg["admin_shift_cancel_on_weekend"] and d.weekday() >= 5 and d not in work_extra:
            return None
        return '行政班'
    return None


WD = '一二三四五六日'
n = (d1 - d0).days + 1
errs = []
stats = {'全天班': 0, '行政班': 0, '放假日全天照上': 0,
         '放假日行政取消': 0, '周末行政取消': 0, '调休日上班': 0}

for i in range(n):
    d = d0 + timedelta(days=i)
    key = d.strftime('%Y%m%d')
    got = events.get(key)
    exp = expect_on(d)
    if exp != got:
        errs.append((d, exp, got))
    if exp == '全天班':
        stats['全天班'] += 1
        if d in off_days:
            stats['放假日全天照上'] += 1
        if d in work_extra:
            stats['调休日上班'] += 1
    elif exp == '行政班':
        stats['行政班'] += 1
        if d in work_extra:
            stats['调休日上班'] += 1
    elif d in off_days and phase_on(start, d) == 1:
        stats['放假日行政取消'] += 1
    elif d.weekday() >= 5 and phase_on(start, d) == 1:
        stats['周末行政取消'] += 1

# ---- ICS 结构检查 ----
begin = raw.count('BEGIN:VEVENT')
endv = raw.count('END:VEVENT')
uids = re.findall(r'UID:([^\r\n]+)', raw)
dup_uids = len(uids) - len(set(uids))

print(f"=== 核对范围 {d0} ~ {d1}({n} 天) ===")
print(f"实际事件: {len(events)} | VEVENT 配对: {begin}/{endv} | UID 重复: {dup_uids}")
for k, v in stats.items():
    print(f"  {k}: {v}")

print(f"\n错误数: {len(errs)}")
for d, exp, got in errs[:15]:
    print(f"  ❌ {d} 周{WD[d.weekday()]} 期望{exp or '无班'} 实际{got or '无班'}")

# ---- 调休上班日明细 ----
print("\n=== 调休上班日(周末补班)与轮班对照 ===")
for d in sorted(work_extra):
    if d0 <= d <= d1:
        ph = {0: '全天班', 1: '行政班', 2: '休', 3: '休'}[phase_on(start, d)]
        s = events.get(d.strftime('%Y%m%d'))
        mark = f"→ 上班({s})" if s else "→ 休息(轮班正好休)"
        print(f"  {d} 周{WD[d.weekday()]} 轮班={ph} {mark}")

# ---- 放假日明细 ----
print("\n=== 放假日处理明细 ===")
for d in sorted(off_days):
    if d0 <= d <= d1:
        ph = {0: '全天班', 1: '行政班', 2: '休', 3: '休'}[phase_on(start, d)]
        s = events.get(d.strftime('%Y%m%d'))
        print(f"  {d} 周{WD[d.weekday()]} 轮班={ph} 实际: {s or '无班'}")

ok = not errs and begin == endv and dup_uids == 0 and len(events) > 0
print("\n🎉 全部校验通过!" if ok else "\n⚠️ 发现问题,需修复!")
sys.exit(0 if ok else 1)
