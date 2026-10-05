# Zectrix NBA Board

NBA 赛程赛况看板插件，沿用 Zectrix NOTE4 的独立 Python 插件模式。它只有一个固定版面，根据同步时的赛事状态自适应替换主卡内容，不轮播多个页面。页面内容：

- `LIVE`：当前直播比分和比赛进程
- `NEXT`：今日下一场对阵、北京时间和开赛倒计时
- `FINAL`：今日焦点赛果和明日预告
- `REST`：最近赛果和下一场比赛
- 1 条精选 NBA 热点新闻标题与来源
- 原生 `400x300`、`1BPP` 黑白 PNG
- 支持离线样例、不上传预览和 Zectrix Cloud 推送
- 输出建议同步周期，最低为 10 分钟；随仓库提供的 `scripts/run_scheduled.sh` 按此自动降频（见 Cron 策略 D）

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

赛事主源默认使用 ESPN 公开 scoreboard（免 key，支持按日期回查未来赛程，字段比官方 CDN 更完整），NBA 官方公开 Live CDN JSON 作为可切换的兜底源。中文热点优先抓取新浪 NBA，腾讯 NBA 作为备用。接口不需要 API Key，但属于公开 CDN/页面，不承诺第三方 SLA，因此脚本会缓存最近一次成功结果、失败重试，并在上游不可用时继续使用缓存，不清空屏幕。

通过环境变量 `NBA_SCORE_SOURCE` 选择赛事主源，默认 `espn`：

| 值 | 说明 |
| --- | --- |
| `espn`（默认） | ESPN 公开 scoreboard：`site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`。免 key、可查未来数日赛程，比赛日/无比赛日都能稳定出数。 |
| `official` | NBA 官方 `todaysScoreboard` + `scheduleLeagueV2`。 |

ESPN 源做了两处适配，理解后排查更顺：

- **北京开赛日归档**：NBA 比赛按美国日期归档，而一个北京日横跨两个美日期（美东傍晚 = 北京凌晨）。脚本拉取一个美日期窗口后，把每场比赛按**北京时间开赛日**重新分桶到昨天/今天/明天/后天。因此"今天"桶里放的是北京今天开打的比赛，进行中的直播会被归到"今天"而非掉进"昨天"。
- **队码归一化**：ESPN 个别队用非标准三字母码（如 `GS`、`NO`、`NY`、`UTAH`），脚本归一化为官方码（`GSW`、`NOP`、`NYK`、`UTA`）后再查中文映射，避免中文名缺失。

若某网络下 NBA 官方 CDN 返回 `403`（常见于数据中心出口 IP 被 Akamai 拒绝）或 ESPN 端点不可用，可设置 `NBA_SCOREBOARD_URL` 和 `NBA_SCHEDULE_URL` 指向自建代理/镜像；镜像必须返回**相同的 JSON 结构**（官方分支）或 ESPN scoreboard 结构（ESPN 分支），否则会解析失败。球队中文名由项目内静态映射表统一生成，例如 `LAL → 湖人`、`GSW → 勇士`。屏幕上的状态、节次、时间和新闻来源均为中文。

**中文热点**：新闻标题用正则从新浪 NBA 列表页提取"含汉字 + 真实文章路径"的 `<a>` 链接（`/doc-`、日期段、`/k/` 等），比旧的 class-based 解析更稳。腾讯 NBA 页是纯前端渲染的 JS 壳（静态 HTML 无标题），静态抓取拿不到内容，因此热点主要依赖新浪；某源取空不影响赛事画面，取不到时热点栏保留最近成功候选或显示"暂无最新中文资讯"。

## 固定单页版面

设备永远只显示一张 `400x300` 单页图片，不轮播赛程页、赛果页或新闻页。脚本在每次同步时按 `LIVE → NEXT → FINAL → REST` 的优先级选择主赛事卡内容，版面框架不会重排。

| 栏位 | 像素区域 | 固定显示内容 | 排版规则 |
| --- | --- | --- | --- |
| 顶栏 | `y=13–43` | NBA 原版字标、日期、星期、`NBA 赛程`、更新时间 | 字标靠左；标题横向居中；更新时间靠右并在顶栏内上下居中。 |
| 主赛事卡 | `y=44–202` | 状态徽标、赛事类型、两队中文名/缩写、比分或 `@`、比赛说明 | 两队名称分别靠近左右安全边距；中间只放比分或对阵符号；说明与状态文本横向居中。 |
| 辅助赛事栏 | `y=206–250` | 下一场、今日比赛摘要或明日预告 | 单行文字左对齐，在栏内上下居中。 |
| 热点栏 | `y=254–286` | 1 条中文 NBA 热点标题与来源 | 单行文字左对齐，在栏内上下居中；标题超宽时自动截断（当前实现不带相对时间）。 |

主卡中的第二行状态说明用于解释**当前主卡所选比赛**，不是后续赛程。后续赛事始终放在第三栏。

## 四种状态

### LIVE：直播中

触发条件：今天至少有一场比赛处于进行中状态。多场直播时，优先选择更接近结束的比赛；其余当天未开赛比赛压缩到第三栏。

| 栏位 | LIVE 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `直播中`；赛事类型 `常规赛`；客队中文名/缩写、实时比分、主队中文名/缩写；比赛进程例如 `第三节 · 剩余 04:28`；说明 `当前直播比分`。 |
| 辅助赛事栏 | `NEXT 10:30 · 今日还有 2 场`（下一场开赛时间 + 今日剩余未开赛场次）；没有剩余比赛时显示 `NEXT 暂无 · 今日还有 0 场`。 |
| 热点栏 | 最新可用中文热点，例如 `热点 湖人公布赛前伤病名单 · 新浪体育 45分钟前`。 |

### NEXT：今日未开赛

触发条件：今天没有直播比赛，但仍存在未开始比赛。多场未开始时，选择距离当前北京时间最近的一场。

| 栏位 | NEXT 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `未开始`；赛事类型 `常规赛`；两队中文名/缩写；中间显示大号 `@`，不显示 `0:0`；说明例如 `今晚 20:30 · 北京时间`；第二行显示 `距开赛约 01小时40分` 或 `今日下一场比赛`。 |
| 辅助赛事栏 | `TODAY 已结束 3 场 · 下一场后还有 2 场`。 |
| 热点栏 | 最新赛前、伤病、交易或阵容类中文热点，例如 `热点 湖人公布赛前伤病名单 · 新浪体育`。 |

### FINAL：今日已结束

触发条件：今天没有直播和未开始比赛，但至少有一场比赛已结束。多场赛果时，选择最晚结束或最接近当前时间的一场。

| 栏位 | FINAL 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `已结束`；赛事类型 `常规赛`；标题 `今日赛果 · 共 N 场`（N 为列出场数）；显示当天最近比赛日前三场重点赛果，每行依次为客队中文名、最终比分、主队中文名，比分字号大于队名；行在卡区内垂直居中，行间以浅灰细分隔线区隔。 |
| 辅助赛事栏 | `NEXT 明日 · 07:00 · 共 5 场`（下一比赛日标签 · 首场开赛时间 · 共 N 场；日期映射为 `明日/后天/MM-DD`，场次按北京开赛日分桶统计）；没有未来赛程时显示 `NEXT 暂无后续赛程`。 |
| 热点栏 | 最新赛后、伤病、交易或球队动态中文热点，例如 `热点 詹姆斯难撼动争冠格局 · 新浪体育`。 |

### REST：今日无比赛

触发条件：今天完全没有 NBA 比赛。主卡复用比赛排版，显示最近一场已结束比赛；这样在无赛日仍保持稳定、易读的单页结构。

| 栏位 | REST 显示内容 |
| --- | --- |
| 顶栏 | `10月04日 周日 NBA 赛程`、当前同步时间。 |
| 主赛事卡 | 徽标 `休赛日`；右侧显示 `今日无比赛`；有最近赛果时标题 `最近比赛日 · 共 N 场`，排版与 FINAL 相同（垂直居中、行间细线）；若没有最近赛果，显示 `今日暂无赛程` 与 `等待下一场比赛`。 |
| 辅助赛事栏 | `NEXT 后天 · 07:00 · 共 4 场`（同 FINAL 的「下一比赛日标签 · 首场开赛时间 · 共 N 场」格式）；没有未来赛程时显示 `NEXT 暂无后续赛程`。 |
| 热点栏 | 最新可用中文热点；无新内容时保留缓存，超过可用期限后显示 `热点 暂无最新中文资讯`。 |

## 状态优先级与刷新频率

脚本会输出例如 `STATE=LIVE POLL_MINUTES=10` 的调度信息，外层 Hermes、cron 或其他调度器据此决定下一次执行时间。最短请求与刷新周期固定为 10 分钟。仓库自带的 `scripts/run_scheduled.sh` 已实现策略 C（见下节），生产环境直接用它，无需手写调度器。

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

NOTE4 不需要安装 Python；在可访问 ESPN scoreboard（默认赛事主源，`site.api.espn.com`，可切换为 NBA 官方 CDN）、Zectrix Cloud、新浪体育的 VPS 上运行本插件即可。建议使用普通用户部署，不要用 root，也不要把 API Key 写入仓库、Cron 参数或日志。

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

如 ESPN scoreboard 或 NBA 官方 CDN 在所在网络返回 `403`（数据中心出口 IP 常被 Akamai 拒绝）或被区域网络限制，可在当前用户的环境文件或 Cron 任务中设置 `NBA_SCOREBOARD_URL` / `NBA_SCHEDULE_URL` 指向代理/镜像地址；镜像不能改变返回的 JSON 结构（官方分支为官方 JSON，ESPN 分支为 ESPN scoreboard JSON），详见[数据来源](#数据来源)。

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

### 策略 D：Cron 高频打点 + wrapper 门控（生产推荐）

策略 C 需要"外层调度器"，落地最省事的是仓库自带的 `scripts/run_scheduled.sh`：cron 仍用简单的固定高频打点（每 10 分钟一个点），wrapper 自己实现门控——

- 每次成功运行后，把「本次时间戳 + 脚本输出的 `POLL_MINUTES`」写入状态文件 `/var/lib/zectrix-nba-board/poll_state`；
- 之后每个 cron 点先读状态文件，**未到下一次截止时间就记一条 SKIP 日志并直接退出**（不抓数据、不推设备），到期才真正执行；
- 比赛日自然收敛为 10 分钟/60 分钟/2 小时/12 小时的节奏，无比赛日 + 深夜时段则极少执行；
- `flock` 防止两点之间重叠执行；日志 `/var/log/zectrix-nba-board.log` 超过 5MB 自动截断；时区锁定 `Asia/Shanghai`。

安装（把打点窗口设为 `07:00–23:50`，深夜静默）：

```cron
CRON_TZ=Asia/Shanghai
*/10 7-23 * * * /path/to/services/zectrix-nba-board/scripts/run_scheduled.sh
```

等价于策略 C，但无需 systemd timer 或队列。日志中的 `SKIP: poll not due until ...` 是正常降频痕迹，不是错误。状态文件损坏或缺失时，wrapper 安全降级为"立即执行"。

### 日志与排错

查看最近日志（策略 D wrapper 默认写 `/var/log/zectrix-nba-board.log`；直接跑脚本时按命令里重定向的位置查）：

```bash
tail -n 100 /var/log/zectrix-nba-board.log
```

排查顺序：

1. 先运行 `--offline-sample`，确认字体、SVG 字标与画布正常。
2. 再使用 `ZECTRIX_NO_PUSH=1` 检查赛事数据源（默认 ESPN，`NBA_SCORE_SOURCE=official` 可切官方 CDN）、缓存和中文热点源。
3. 确认 `STATE` 与实际赛事状态一致后再开启推送。
4. 数据源失败时：确认缓存仍可生成画面；`403`/连接被拒多为出口 IP 被拦（数据中心机房 IP 对 NBA 官方 CDN 常见），按[数据来源](#数据来源)配置 `NBA_SCOREBOARD_URL` / `NBA_SCHEDULE_URL` 代理，或改用可达的 ESPN 端点。
5. 定时任务侧：`SKIP: poll not due until ...` 为策略 D 正常降频；连续出现 `WARN: 数据源失败` 才需要排查网络；状态文件缺失/损坏会安全降级为立即执行，无需人工干预。
