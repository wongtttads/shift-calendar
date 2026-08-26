# 上二休二 · 工作日历订阅

把「上二休二 + 节假日取消」轮班表生成 ICS,用 GitHub Pages 托管,苹果日历直接订阅。

## 规则

- 周期:**全天班 → 行政班 → 休 → 休**,循环
- **取消制**:排到班次的当天若命中取消条件则不上班,周期不滑动
  - 全天班:遇法定放假日(国务院公布)取消
  - 行政班:遇法定放假日**或周末**取消
  - 调休上班日(周末补班):不额外放假,本应上班照常上班
- 节假日数据源:[holiday-cn](https://github.com/NateScarlet/holiday-cn)(每日抓取国务院公告)

## 配置

编辑 `config.json`:

| 字段 | 说明 |
|---|---|
| `start_date` | 第一个全天班日期(默认 `2026-08-27`) |
| `years` | 生成跨度(默认 1 年) |
| `full_shift_cancel_on_holiday` | 全天班遇法定放假日取消 |
| `admin_shift_cancel_on_holiday` | 行政班遇法定放假日取消 |
| `admin_shift_cancel_on_weekend` | 行政班遇周末取消 |
| `show_rest` | 是否生成「休息」事件 |

## 本地预览

```bash
python3 generate.py --months 4
```

## 部署(一次性)

1. 创建仓库并推送:
   ```bash
   git init && git add . && git commit -m init
   gh repo create shift-calendar --public --source . --push
   ```
2. 开启 GitHub Pages:
   ```bash
   gh api -X POST repos/wongtttads/shift-calendar/pages \
     -f 'build_type=workflow'
   ```
3. 订阅地址(首次部署后约 1 分钟生效):
   ```
   https://wongtttads.github.io/shift-calendar/calendar.ics
   ```

iPhone:设置 → 日历 → 账户 → 添加账户 → 其他 → 添加订阅日历 → 粘贴链接。

## 自动更新

GitHub Actions 每周一 00:30 自动:拉最新节假日 → 重新生成 → 提交 → 部署。
节假日安排更新后,下一周自动生效,无需手动维护。
