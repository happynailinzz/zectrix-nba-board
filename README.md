# Zectrix NBA Board

NBA 赛程赛况看板插件，沿用 Zectrix NOTE4 的独立 Python 插件模式。它只有一个固定版面，根据同步时的赛事状态自适应替换主卡内容，不轮播多个页面。页面内容：

- `LIVE`：当前直播比分和比赛进程
- `NEXT`：今日下一场对阵、北京时间和开赛倒计时
- `FINAL`：今日焦点赛果和明日预告
- `REST`：最近赛果和下一场比赛
- 1 条精选 NBA 热点新闻标题与来源
- 原生 `400x300`、`1BPP` 黑白 PNG
- 支持离线样例、不上传预览和 Zectrix Cloud 推送
- 输出建议同步周期，最低为 10 分钟

## 安装

开发机本地预览可直接在仓库根目录创建虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

服务器从 GitHub 克隆、更新和定时执行的完整步骤见[部署到 VPS](#部署到-vps)。

初始化配置写入 `~/.config/zectrix-nba-board/config.json`，API Key 不会写入项目目录：

```bash
.venv/bin/python scripts/init.py
```

也可以通过参数初始化：

```bash
.venv/bin/python scripts/init.py --api-key 'zt_你的APIKey' --device 'AA:BB:CC:DD:EE:FF' --page 3
```

## 运行

```bash
# 离线样例，不联网、不上传
.venv/bin/python scripts/nba_board.py --offline-sample --date 2026-10-04 --output /tmp/nba.png

# 抓取实时数据但不上传
ZECTRIX_NO_PUSH=1 .venv/bin/python scripts/nba_board.py

# 抓取并推送
.venv/bin/python scripts/nba_board.py
```

## 数据来源

赛事主源使用 NBA 官方公开 Live CDN JSON，未来赛程使用官方赛程 JSON；中文热点优先抓取新浪 NBA，腾讯 NBA 作为备用。接口不需要 API Key，但属于公开 CDN/页面，不承诺第三方 SLA，因此脚本会缓存最近一次成功结果、失败重试，并在上游不可用时继续使用缓存，不清空屏幕。

如果 VPS 需要通过自建代理或镜像访问官方数据，可设置 `NBA_SCOREBOARD_URL` 和 `NBA_SCHEDULE_URL` 覆盖默认端点；输出格式保持 NBA 官方 JSON 结构。

球队中文名由项目内静态映射表统一生成，例如 `LAL → 湖人`、`GSW → 勇士`。屏幕上的状态、节次、时间和新闻来源均为中文。

## 固定单页版面

设备永远只显示一张 `400x300` 单页图片，不轮播赛程页、赛果页或新闻页。脚本在每次同步时按 `LIVE → NEXT → FINAL → REST` 的优先级选择主赛事卡内容，版面框架不会重排。

| 栏位 | 像素区域 | 固定显示内容 | 排版规则 |
| --- | --- | --- | --- |
| 顶栏 | `y=13–43` | NBA 原版字标、日期、星期、`NBA 赛程`、更新时间 | 字标靠左；标题横向居中；更新时间靠右并在顶栏内上下居中。 |
| 主赛事卡 | `y=44–202` | 状态徽标、赛事类型、两队中文名/缩写、比分或 `@`、比赛说明 | 两队名称分别靠近左右安全边距；中间只放比分或对阵符号；说明与状态文本横向居中。 |
| 辅助赛事栏 | `y=206–250` | 下一场、今日比赛摘要或明日预告 | 单行文字左对齐，在栏内上下居中。 |
| 热点栏 | `y=254–286` | 1 条中文 NBA 热点、来源、相对时间 | 单行文字左对齐，在栏内上下居中；标题超宽时自动截断。 |

主卡中的第二行状态说明用于解释**当前主卡所选比赛**，不是后续赛程。后续赛事始终放在第三栏。

## 四种状态

### LIVE：直播中

触发条件：今天至少有一场比赛处于进行中状态。多场直播时，优先选择更接近结束的比赛；其余当天未开赛比赛压缩到第三栏。

| 栏位 | LIVE 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `直播中`；赛事类型 `常规赛`；客队中文名/缩写、实时比分、主队中文名/缩写；比赛进程例如 `第三节 · 剩余 04:28`；说明 `当前直播比分`。 |
| 辅助赛事栏 | `下一场 10:30 · 太阳 PHX @ 掘金 DEN · 今日还有 2 场`；没有剩余比赛时显示 `下一场 暂无`。 |
| 热点栏 | 最新可用中文热点，例如 `热点 湖人公布赛前伤病名单 · 新浪体育 45分钟前`。 |

### NEXT：今日未开赛

触发条件：今天没有直播比赛，但仍存在未开始比赛。多场未开始时，选择距离当前北京时间最近的一场。

| 栏位 | NEXT 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `未开始`；赛事类型 `常规赛`；两队中文名/缩写；中间显示大号 `@`，不显示 `0:0`；说明例如 `今晚 20:30 · 北京时间`；第二行显示 `距开赛约 01小时40分` 或 `今日下一场比赛`。 |
| 辅助赛事栏 | `今日 已结束 3 场 · 下一场后还有 2 场`。 |
| 热点栏 | 最新赛前、伤病、交易或阵容类中文热点。 |

### FINAL：今日已结束

触发条件：今天没有直播和未开始比赛，但至少有一场比赛已结束。多场赛果时，选择最晚结束或最接近当前时间的一场。

| 栏位 | FINAL 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `已结束`；赛事类型 `常规赛`；标题 `今日赛果`；显示当天最近比赛日的前三场重点赛果，每行依次为客队中文名、最终比分、主队中文名；底部显示 `最近 1 个比赛日 · 共 3 场`。不足三场时按实际场数显示。 |
| 辅助赛事栏 | `下一场 明日 08:30 · 凯尔特人 BOS @ 尼克斯 NYK`；没有未来赛程时显示 `下一场 暂无赛程`。 |
| 热点栏 | 最新赛后、伤病、交易或球队动态中文热点。 |

### REST：今日无比赛

触发条件：今天完全没有 NBA 比赛。主卡复用比赛排版，显示最近一场已结束比赛；这样在无赛日仍保持稳定、易读的单页结构。

| 栏位 | REST 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `休赛日`；右侧显示 `今日无比赛`；标题 `最近比赛日赛果`；显示最近一个有比赛日期的前三场重点赛果，每行依次为客队中文名、最终比分、主队中文名；底部显示 `最近 1 个比赛日 · 共 3 场`。不足三场时按实际场数显示；若没有最近赛果，显示 `今日暂无赛程` 与 `等待下一场比赛`。 |
| 辅助赛事栏 | 下一场未来比赛，例如 `下一场 明日 08:30 · 凯尔特人 BOS @ 尼克斯 NYK`。 |
| 热点栏 | 最新可用中文热点；无新内容时保留缓存，超过可用期限后显示 `热点 暂无最新中文资讯`。 |

## 状态优先级与刷新频率

脚本会输出例如 `STATE=LIVE POLL_MINUTES=10` 的调度信息，外层 Hermes、cron 或其他调度器据此决定下一次执行时间。最短请求与刷新周期固定为 10 分钟。

| 状态 | 判定条件 | 数据拉取周期 | 建议屏幕刷新周期 |
| --- | --- | --- | --- |
| `LIVE` | 至少有一场进行中比赛 | 每 10 分钟 | 每 10 分钟 |
| `NEXT_NEAR` | 无直播，最近一场距开赛不超过 2 小时 | 每 10 分钟 | 每 10 分钟 |
| `NEXT_FAR` | 无直播，最近一场距开赛超过 2 小时 | 每 60 分钟 | 有变化时更新 |
| `FINAL` | 今日比赛均已结束 | 每 120 分钟 | 新闻或明日预告变化时更新 |
| `REST` | 今日无任何比赛 | 每 720 分钟 | 每日早晚至少各一次；可按需增加到 3–4 次 |
| `QUIET` | 建议北京时间 `00:30–07:00` | 不拉取 | 保持上一帧，不刷新 |

## 更新策略

### 全刷

下列情况建议全刷整张单页，确保状态切换清晰并控制残影：

- 设备上电后的首次同步。
- 页面状态变化，例如 `NEXT → LIVE`、`LIVE → FINAL`。
- 焦点比赛发生变化，例如当前直播比赛结束后切换到另一场。
- 队伍、比赛状态、延期/取消信息发生变化。
- 热点标题变化明显，或文本长度变化导致底栏内容重排。
- 连续执行 3 次局刷后的下一次刷新。

### 局刷

如果设备固件支持局刷，同一比赛、同一状态下可只更新这些区域：

- 比分区：主赛事卡中间比分。
- 比赛进程区：节次、剩余时间或最终状态。
- 顶栏更新时间。
- 第三栏下一场/今日剩余场数。
- 第四栏热点文本，仅在标题或来源变化时更新。

直播时可采用 `局刷 → 局刷 → 局刷 → 全刷` 的循环；比分、节次和更新时间未变化时不需要推送新图片。

新闻只展示标题、来源和相对时间，不抓取正文、图片、视频或评论。新浪/腾讯页面结构变化时不会阻塞赛事画面，新闻区域会保留最近一次成功候选或显示“暂无最新中文资讯”。

画面使用项目内点阵字体，固定在 400x300 画布上一次性二值化，推送参数使用 `dither=false`，避免云端再次抖动造成文字模糊。

## 部署到 VPS

NOTE4 不需要安装 Python；在可访问 NBA 官方 CDN、Zectrix Cloud、新浪体育和腾讯体育的 VPS 上运行本插件即可。建议使用普通用户部署，不要用 root，也不要把 API Key 写入仓库、Cron 参数或日志。

### 1. 安装运行环境

```bash
mkdir -p ~/services
cd ~/services

# 从 GitHub 克隆插件
git clone https://github.com/happynailinzz/zectrix-nba-board.git

cd ~/services/zectrix-nba-board
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

VPS 需要 Python 3、`venv` 与网络访问权限。项目使用 Pillow 和 CairoSVG 将 NBA SVG 字标栅格化到 `400x300` 黑白屏幕；如服务器缺少 CairoSVG 的系统依赖，请按系统发行版安装 Cairo 所需运行库后再次执行 `pip install -r requirements.txt`。

后续更新插件代码时，在 VPS 上执行：

```bash
cd ~/services/zectrix-nba-board
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt
```

`git pull --ff-only` 会拒绝覆盖服务器上的本地改动。设备配置、缓存、`.venv` 和日志均位于仓库外或已在 `.gitignore` 中忽略，不应提交到 GitHub。

### 2. 初始化设备配置

首次部署时在 VPS 上交互式写入配置：

```bash
cd ~/services/zectrix-nba-board
.venv/bin/python scripts/init.py
```

程序会要求输入：

- Zectrix API Key。
- NOTE4 设备 ID / MAC。
- 推送页面号，默认 `3`。

配置保存在：

```text
~/.config/zectrix-nba-board/config.json
```

部署后收紧权限：

```bash
chmod 700 ~/.config/zectrix-nba-board
chmod 600 ~/.config/zectrix-nba-board/config.json
```

如官方 NBA CDN 在所在网络返回 `403` 或被区域网络限制，可在当前用户的环境文件或 Cron 任务中设置代理/镜像地址，但不能改变返回的 NBA 官方 JSON 结构：

```bash
export NBA_SCOREBOARD_URL='https://your-proxy.example/scoreboard/todaysScoreboard_00.json'
export NBA_SCHEDULE_URL='https://your-proxy.example/scheduleLeagueV2_1.json'
```

### 3. 上线前测试

按下面顺序测试，确认每一层都正常后再启用真实推送：

```bash
cd ~/services/zectrix-nba-board

# 离线样例：不联网、不推送，检查排版
.venv/bin/python scripts/nba_board.py --offline-sample --output /tmp/nba-sample.png

# 实时拉取：联网但不推送，检查状态机和数据源
ZECTRIX_NO_PUSH=1 .venv/bin/python scripts/nba_board.py --output /tmp/nba-live-check.png

# 真实推送：确认屏幕显示无误后执行
.venv/bin/python scripts/nba_board.py
```

每次执行会输出类似下列信息：

```text
STATE=LIVE POLL_MINUTES=10
```

其中 `STATE` 是当前单页状态，`POLL_MINUTES` 是建议下一次拉取周期。Cloud API 返回 `PUSH pageId=3 OK` 只代表平台已接受上传；NOTE4 实际刷新取决于设备下一次轮询。

## Cron 定时任务策略

服务端统一决定画面，不需要设备轮播。最简单的做法是由 Cron 定时执行脚本；脚本会基于实时数据选择 `LIVE / NEXT / FINAL / REST` 主卡。Cron 本身不会读取 `POLL_MINUTES` 自动改变表达式，因此可从下列两种策略中选择。

### 策略 A：统一每 10 分钟运行

适合首次上线和只管理一台设备的场景。优点是最简单，直播和临近开赛不会错过状态切换；缺点是在 `FINAL/REST` 期间会产生不必要的数据请求。

编辑当前用户的 crontab：

```bash
crontab -e
```

添加以下内容，时间统一使用北京时间：

```cron
CRON_TZ=Asia/Shanghai
*/10 * * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1
```

建议在深夜静默，避免 `00:30–07:00` 继续抓取：

```cron
CRON_TZ=Asia/Shanghai
*/10 7-23 * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1
0,10,20 0 * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1
```

第二条规则只允许当天 `00:00`、`00:10`、`00:20` 三次同步，从 `00:30` 到 `07:00` 保持上一帧。

### 策略 B：分时段低频运行

适合优先控制请求量和墨水屏刷新次数的场景。它无法像状态感知调度那样精确切换到 10 分钟，但可用比赛日常见的时段规则实现接近目标的效果：

```cron
CRON_TZ=Asia/Shanghai

# 07:00–11:59：覆盖早场和部分直播，每 10 分钟
*/10 7-11 * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1

# 12:00–17:59：赛程变化较少，每小时一次
0 12-17 * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1

# 18:00–23:59：晚间赛程、新闻与次日预告，每小时一次
0 18-23 * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1

# 无比赛日的晨间/午间/晚间简报可替代后两段的高频规则
30 7,12,18,22 * * * /home/your-user/services/zectrix-nba-board/.venv/bin/python /home/your-user/services/zectrix-nba-board/scripts/nba_board.py >> /tmp/zectrix-nba-board.log 2>&1
```

不要同时启用“全天每 10 分钟”和“分时段低频”两套规则。选择策略 A 或 B 后，删除另一套，避免同一分钟重复推送。

### 策略 C：完全按状态调度

如果要严格按脚本给出的 `POLL_MINUTES` 调度，应由外层调度器保存上次输出的 `STATE/POLL_MINUTES`，在下一次到期后再调用脚本。推荐规则如下：

| 当前状态 | 下一次执行 | 用途 |
| --- | --- | --- |
| `LIVE` | 10 分钟后 | 更新比分、节次和直播状态。 |
| `NEXT` 且开赛不超过 2 小时 | 10 分钟后 | 更新倒计时并捕捉 `NEXT → LIVE`。 |
| `NEXT` 且开赛超过 2 小时 | 60 分钟后 | 更新赛程和热点即可。 |
| `FINAL` | 120 分钟后 | 更新赛后热点和明日预告。 |
| `REST` | 当天下一次固定简报时段 | 推荐 `07:30 / 12:30 / 18:30 / 22:30`。 |
| `QUIET` | `07:00` 后 | 深夜保持上一帧。 |

Hermes、systemd timer、任务队列或自建调度服务都可以实现此策略。外层服务应解析程序标准输出中的 `POLL_MINUTES`，并把下一次执行时间持久化；如果解析失败，安全降级为 60 分钟后重试。

### 日志与排错

建议日志只保留运行状态、数据源错误和 Cloud API 结果，不打印配置文件或 API Key。查看最近日志：

```bash
tail -n 100 /tmp/zectrix-nba-board.log
```

排查顺序：

1. 先运行 `--offline-sample`，确认字体、SVG 字标与画布正常。
2. 再使用 `ZECTRIX_NO_PUSH=1` 检查 NBA 官方数据、缓存和中文热点源。
3. 确认 `STATE` 与实际赛事状态一致后再开启推送。
4. 如果 NBA CDN 失败，检查缓存是否仍可生成画面，并检查 `NBA_SCOREBOARD_URL` / `NBA_SCHEDULE_URL` 的代理配置。
