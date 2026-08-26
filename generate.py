#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上二休二 · 工作日历生成器
规则:
  - 周期:全天班 → 行政班 → 休 → 休,循环
  - 取消制:排到班次的当天若命中「取消条件」则当天不上班,周期不滑动
    * 全天班:法定放假日(isOffDay=true)取消;周末不取消
    * 行政班:法定放假日或周末取消
  - 调休上班日(周末补班,isOffDay=false):不额外放假,若本应上班则照常上班
输出:calendar.ics(iCalendar 标准,全天事件,供苹果日历订阅)
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"
OUT_FILE = BASE / "calendar.ics"
HOLIDAY_URL = "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json"

DEFAULT_CONFIG = {
    "title": "上二休二 班表",
    "start_date": "2026-08-27",          # 第一个全天班日期
    "years": 1,                          # 生成跨度(年):至少覆盖到今天+1年(滚动)
    "full_shift_cancel_on_holiday": False,  # 全天班铁打不动,任何节假日照常上班
    "admin_shift_cancel_on_holiday": True,  # 行政班遇法定放假日取消
    "admin_shift_cancel_on_weekend": True,  # 行政班遇周末取消(调休上班日除外)
    "show_rest": False,                  # 是否同时生成「休息」事件
    "timezone": "Asia/Shanghai",
    "holiday_source": "holiday-cn",      # 节假日数据源
}


def load_config():
    if CONFIG_FILE.exists():
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        return merged
    return dict(DEFAULT_CONFIG)


def fetch_holidays(year):
    """从 holiday-cn 拉取某年节假日数据。
    网络优先(保证 Actions 每周拿到最新安排),失败时回退本地缓存,再失败返回空表。"""
    import urllib.request
    cache = BASE / "holidays" / f"{year}.json"
    url = HOLIDAY_URL.format(year=year)
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        # 完整性防御:仅当解析出的 days 列表不为空(数据源确实发布了安排)
        # 且是完整 JSON 时才写缓存;避免把"部分下载/空占位"缓存覆盖好数据。
        if data.get("days"):
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(raw)
            except Exception:
                pass
        return _parse_holidays(data)
    except Exception as exc:
        print(f"[warn] 无法获取 {year} 节假日数据: {exc},尝试本地缓存", file=sys.stderr)
        if cache.exists():
            try:
                data = json.loads(cache.read_bytes().decode("utf-8"))
                return _parse_holidays(data)
            except Exception:
                pass
        return set(), set()


def _parse_holidays(data):
    off_days = set()     # 放假日
    work_extra = set()   # 调休上班日(周末补班)
    days = data.get("days", [])
    if not days:
        year = data.get("year")
        print(f"[info] {year} 年节假日安排尚未公布(国务院通常年底发布),"
              f"该年日期暂按普通工作日处理", file=sys.stderr)
    for day in days:
        d = date.fromisoformat(day["date"])
        if day.get("isOffDay"):
            off_days.add(d)
        else:
            work_extra.add(d)
    return off_days, work_extra


def phase_on(start, d):
    """上二休二:0=全天班,1=行政班,2=休,3=休"""
    return ((d - start).days % 4)


def generate(cfg):
    start = date.fromisoformat(cfg["start_date"])
    # 滚动生成:结束日期 = max(起始+years年, 今天+1年+缓冲),保证订阅永不"断档"
    span_days = cfg["years"] * 365 + 2
    end = start + timedelta(days=span_days)
    today = date.today()
    min_end = today + timedelta(days=365 + 180)  # 至少未来一年半
    if end < min_end:
        end = min_end
    total_days = (end - start).days
    off_days = set()
    work_extra = set()
    years_needed = {start.year, end.year}
    for y in years_needed:
        o, w = fetch_holidays(y)
        off_days |= o
        work_extra |= w

    events = []  # (date, kind)
    for i in range(total_days):
        d = start + timedelta(days=i)
        phase = phase_on(start, d)
        if phase == 0:      # 全天班
            if cfg["full_shift_cancel_on_holiday"] and d in off_days:
                continue
            events.append((d, "全天班"))
        elif phase == 1:    # 行政班
            if cfg["admin_shift_cancel_on_holiday"] and d in off_days:
                continue
            # 周末取消,但调休上班日(如周六补班)不取消:那天本来就要上班
            if (cfg["admin_shift_cancel_on_weekend"]
                    and d.weekday() >= 5
                    and d not in work_extra):
                continue
            events.append((d, "行政班"))
        elif cfg["show_rest"]:
            events.append((d, "休息"))

    # 写 ICS。UID 使用确定性值(日期+类型),保证同一事件跨版本 UID 稳定,
    # 苹果日历订阅刷新时只做增量更新,不会"删旧建新"产生重复事件。
    from datetime import datetime, timezone as dt_timezone
    stamp = datetime.now(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//dsh-shift-calendar//CN//",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + cfg["title"],
        "X-WR-TIMEZONE:" + cfg["timezone"],
    ]
    for d, kind in events:
        uid = f"shift-{d.isoformat()}-{kind}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"SUMMARY:{kind}",
            f"DESCRIPTION:{kind} - 上二休二轮班",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    OUT_FILE.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return events


def summarize(events, months=4):
    """按月份分组打印前 N 个月班次"""
    from collections import defaultdict
    by_month = defaultdict(list)
    for d, kind in events:
        by_month[(d.year, d.month)].append((d.day, kind))
    print(f"共生成 {len(events)} 个事件 -> {OUT_FILE.name}")
    for (y, m) in sorted(by_month)[:months]:
        items = ", ".join(f"{day}日{kind}" for day, kind in by_month[(y, m)])
        print(f"  {y}-{m:02d}: {items}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=4)
    args = ap.parse_args()
    cfg = load_config()
    events = generate(cfg)
    summarize(events, args.months)
