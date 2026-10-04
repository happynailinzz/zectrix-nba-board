---
name: zectrix-nba-board
description: 为 Zectrix NOTE4 生成 NBA 近三日赛程赛况和 3 条热点新闻看板。触发词：NBA 看板、NBA 赛程、NBA 赛况、篮球新闻、Zectrix NBA。
---

# Zectrix NBA 看板

运行 `scripts/nba_board.py`，在固定单页内根据当前赛事状态显示一场焦点比赛、辅助赛事信息和 1 条精选新闻，生成原生 `400x300`、`1BPP` 黑白图片并可通过 Zectrix Cloud API 推送。

首次使用先运行：

```bash
python3 scripts/init.py
```

需要用户提供自己的 Zectrix API Key、设备 ID/MAC 和页面号，不要猜测或使用示例凭据。

离线预览：

```bash
python3 scripts/nba_board.py --offline-sample --date 2026-10-04
```

日常运行：

```bash
python3 scripts/nba_board.py
```

赛事默认来自 NBA 官方公开 Live CDN JSON，中文热点默认来自新浪 NBA，腾讯 NBA 作为备用；数据源不可用时优先使用最近一次成功缓存，不清空赛况画面。赛程时间按北京时间显示，服务端统一维护球队中文映射。

脚本按 `LIVE → NEXT → FINAL → REST` 选择页面状态，并输出建议轮询周期：直播中 10 分钟、两小时内开赛 10 分钟、远期开赛 60 分钟、当天结束 120 分钟、无比赛日 720 分钟。页面不轮播，永远只有一个固定版面。
