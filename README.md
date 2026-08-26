# 上二休二 · 工作日历订阅

把「上二休二 + 节假日取消」轮班表生成 ICS,用 GitHub Pages 托管,苹果日历直接订阅。

## 规则

- 周期:**全天班 → 行政班 → 休 → 休**,循环
- **取消制**:排到班次的当天若命中取消条件则不上班,周期不滑动
  - **全天班:铁打不动,任何节假日(含法定放假日)都要上班,不取消**
  - **行政班:遇法定放假日取消;遇普通周末取消;调休上班日(周末补班)不取消——当天排到班照常上班**
- 节假日数据源:[holiday-cn](https://github.com/NateScarlet/holiday-cn)(每日抓取国务院公告)

## 配置

编辑 `config.json`:

| 字段 | 说明 |
|---|---|
| `start_date` | 第一个全天班日期(默认 `2026-08-27`) |
| `years` | 基准生成跨度(默认 1 年;**实际滚动生成**:每次运行至少覆盖到今天+1年半,订阅永不"断档") |
| `full_shift_cancel_on_holiday` | 全天班遇法定放假日取消(默认 **false** = 全天班铁打不动) |
| `admin_shift_cancel_on_holiday` | 行政班遇法定放假日取消(默认 true) |
| `admin_shift_cancel_on_weekend` | 行政班遇周末取消(默认 true,调休上班日除外) |
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

GitHub Actions 每周一 00:30 自动:拉最新节假日(网络优先,失败回退仓库内缓存)→ 重新生成(滚动覆盖到今天+1年半)→ 提交 → 部署。

- **节假日更新**:国务院公布新年安排后,holiday-cn 数据源自动同步,下一周自动生效
- **防停用**:每次运行写入 `last-run.txt` 时间戳并提交,确保仓库持续活跃,GitHub 不会停用定时任务
- **事件幂等**:事件 UID 由日期+类型确定性生成,订阅刷新只做增量更新,不会产生重复事件
- **断档保护**:无论何时查看,日历始终覆盖未来 1 年半的班次
