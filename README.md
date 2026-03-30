# CS-ACL-Server 项目交接文档

## 1. 项目概览

`CS-ACL-Server` 是一个面向 **CS2 赛事直播/数据包装场景** 的本地 Python 服务集合，核心职责是围绕比赛进行中的 **GSI 数据接收、实时接口输出、赛后数据回填、人工运营操作** 展开。

项目当前主要通过若干 Python 脚本直接运行，依赖本地 JSON 文件、阿里云 MySQL、CS GSI 推流和局域网设备接口。

系统由三类能力组成：

1. **实时服务**：`app.py` + `gsi/` + `service.py`
2. **赛后服务**：`all_api.py`
3. **人工/辅助工具**：`setting.html`、`analyse.py`、`pov_switching.py`、`check.py`

## 2. 项目结构

```text
CS-ACL-Server/
├── app.py                         实时服务主入口，启动 Flask :1234 与 GSI Server :3000
├── all_api.py                     赛后服务主入口，启动 Flask :1111
├── service.py                     实时接口的数据拼装逻辑
├── models.py                      SQLAlchemy 模型定义 + 数据库连接
├── global_data.py                 GSI 全局状态缓存
├── analyse.py                     赛事分析与 Excel 导出脚本
├── pov_switching.py               POV 切换脚本，调用 vMix / 局域网设备接口
├── check.py                       选手 Steam ID 配置校验脚本
├── gsi/
│   ├── server.py                  本地 HTTP GSI 接收服务
│   ├── gamestate.py               GSI 状态对象
│   ├── payloadparser.py           GSI payload 解析
│   ├── information.py             GSI 信息对象
│   └── __init__.py
├── gamestate_integration_GSI.cfg  CS 客户端 GSI 配置模板
├── player_info.json               赛前预录配置，核心运行依赖
├── gsi_data.json                  比赛结束时保存的 GSI 快照
├── board.json / first_half.json / second_half.json / overtime.json
│                                  展示数据样例/静态资源
├── seat_screen.json               桌前屏相关静态数据
├── setting.html                   本地管理页，无构建步骤
├── setting.js                     管理页逻辑，调用 :1111 接口
├── setting.css                    管理页样式
├── axios.min.js / vue.global.js / sweetalert2.js
│                                  管理页前端依赖，本地直接引用
├── analyse_out/                   分析 Excel 输出目录
├── requirements.txt               Python 依赖列表（当前文件编码为 UTF-16）
├── ref_handover.md                参考交接文档
└── compare.py / res.json          辅助脚本与数据文件
```

## 3. 系统架构

### 3.1 整体形态

系统不是单一服务，而是多个本地进程/文件协作：

```text
CS 游戏客户端
  └─ 根据 gamestate_integration_GSI.cfg
     向 http://127.0.0.1:3000 POST GSI 数据
          │
          ▼
   gsi/server.py (本地 HTTPServer)
          │
          ├─ 更新 global_data.data
          ├─ 比赛结束时写入 gsi_data.json
          └─ 将 player_info.json.is_over 置为 "1"
          │
          ▼
       app.py
          ├─ Flask :1234 提供实时接口
          ├─ 后台线程做回合/炸弹/暂停状态判断
          └─ 部分现场控制逻辑预留在此

人工运营页 setting.html
  └─ 调用 http://127.0.0.1:1111
          │
          ▼
       all_api.py
          ├─ 提供赛后记分板 / MVP / 比赛元数据录入
          └─ 调用外部 5E XML 接口并写 MySQL

MySQL (Aliyun RDS)
  └─ 赛程、比赛、回合、选手赛后数据、实时数据等

analyse.py
  └─ 从 MySQL 读取数据并导出 Excel 到 analyse_out/
```

### 3.2 运行链路

当前仓库中，**真正处于启用状态** 的主要链路是：

1. CS 客户端通过 GSI 向 `127.0.0.1:3000` 发数据
2. `global_data.data` 被持续刷新
3. `app.py` 对外提供实时接口
4. 比赛结束时生成 `gsi_data.json`，并把 `player_info.json.is_over` 标为 `"1"`
5. 人工打开 `setting.html`，通过 `all_api.py` 完成 MVP 选择、比赛信息补录、赛后数据落库

### 3.3 启动逻辑

`app.py` 的主函数中先执行：

1. `server.GSIServer(("127.0.0.1", 3000), "vspo")`
2. `myServer.start_server()`
3. 启动后台线程
4. `app.run(host="0.0.0.0", port=1234, debug=False)`

但 `gsi/server.py` 的 `start_server()` 会在 `self.running == False` 时循环等待，直到收到 **第一条鉴权通过的 GSI 请求** 才返回。因此：

- **如果没有来自游戏客户端的有效 GSI POST，请求链路不会继续**
- 在这种情况下，`app.py` 的 Flask 服务 `:1234` 也不会真正启动完成

## 4. 核心模块说明

### 4.1 `app.py`：实时服务主入口

主要职责：

- 启动本地 GSI Server，接收游戏态数据
- 维护比赛中的全局状态
- 对外暴露实时接口
- 根据炸弹状态、暂停状态、半场/终场状态触发现场控制逻辑
- 提供部分赛后比分和记分板查询
- 预留实时/回合级数据入库能力

当前公开接口：

| 接口 | 方法 | 说明 |
| ---- | ---- | ---- |
| `/allPlayerState` | GET | 返回所有选手当前状态、超时标记、埋包/爆炸状态、ACE 信息 |
| `/observedPlayer` | GET | 返回当前 OB 观察视角选手信息 |
| `/scores` | GET | 返回实时比分 |
| `/scoreboard` | GET | 返回赛后记分板，依赖 `gsi_data.json` 和 `adr_json/` |
| `/overallBoard` | GET | 返回中场面板数据，底层来自 `service.py` |
| `/slideBar` | GET | 返回每回合胜利方式侧边栏数据 |

注意：

- 控制接口地址硬编码在文件顶部，如 `192.168.15.235`、`192.168.200.49`
- `backgroundProcess()` 当前只调用 `checkGlobalData()` 和 `sendEventMsg()`，不做数据库或文件持久化

### 4.2 `all_api.py`：赛后服务与人工操作 API

赛后数据和人工录入

主要职责：

- 输出赛后比分与记分板
- 管理 MVP 选择
- 接收比赛元数据录入
- 抓取 5E 提供的 XML 数据并写入数据库
- 给管理页返回队名、选手列表等基础信息

当前公开接口：

| 接口 | 方法 | 说明 |
| ---- | ---- | ---- |
| `/scores` | GET | 返回赛后比分，读取 `gsi_data.json` |
| `/aftergameBoard` | GET | 返回赛后选手面板，依赖数据库 |
| `/aftergameSlideBar` | GET | 返回赛后回合胜利条 |
| `/scoreboard` | GET | 返回赛后记分板 |
| `/player_list` | GET | 返回 MVP 页面用的选手列表 |
| `/setMvp` | POST | 手工设置 MVP |
| `/mvp` | GET | 获取 MVP 数据，支持自动/手选逻辑 |
| `/selectedMVP` | GET | 返回手工指定 MVP 的详细数据 |
| `/saveMatchData` | POST | 拉取外部 XML，写 `DataGame` 与 `GameList` |
| `/teamNames` | GET | 返回管理页展示的左右队名 |

`/saveMatchData` 是重要的赛后入库接口，流程为：

1. 接收 `match_code`、`match_id`、周次、场次、BO 类型等参数
2. 调用 `https://mega-tpa.5eplaycdn.com/xml/bracket/tournament/match_xml?match_code=...`
3. 解析 XML 中每位选手的赛后数据
4. 写入 `DataGame`
5. 写入或更新 `GameList`

### 4.3 `gsi/`：本地 GSI 服务

`gsi/server.py` 基于 Python 标准库 `HTTPServer` 自行实现了一个轻量 GSI 接收服务。

关键行为：

- 监听 `127.0.0.1:3000`
- 校验 payload 中 `auth.token == "vspo"`
- 将原始 payload 写入 `global_data.data`
- 比赛结束时：
  - 把 payload 写到 `gsi_data.json`
  - 把 `player_info.json` 中 `is_over` 改为 `"1"`

### 4.4 `service.py`：实时数据组装

目前主要提供两个函数：

- `get_overall_board()`：生成整体中场板数据
- `get_slide_bar()`：生成分半场/加时的回合结果条

这些函数直接读取 `global_data.data` 和 `player_info.json`，没有额外的数据抽象层。因此：

### 4.5 `models.py`：数据库模型与连接

```python
mysql+pymysql://vspnjovi:Pubgm2021@rm-uf6f326265lft8bwrdo.mysql.rds.aliyuncs.com:3306/acl_cs_2025?charset=utf8
```

- 阿里云 RDS MySQL
- 凭据硬编码
- 无环境变量
- `isolation_level="READ UNCOMMITTED"`

### 4.6 `analyse.py`：数据分析与导出

该脚本从数据库中提取战队和选手数据，生成分析 Excel。

已实现能力：

- 地图池胜负统计
- 手枪局胜率统计
- T/CT 胜率统计
- 选手均值指标（rating / ADR / KPR）
- 导出到 `analyse_out/analyse_时间戳.xlsx`

### 4.7 其他辅助脚本

#### `setting.html` / `setting.js`

一个无需构建的本地管理页，直接加载仓库内的 `vue.global.js`、`axios.min.js`、`sweetalert2.js`。

主要功能：

- 手工选择本局 MVP
- 录入比赛元数据并提交到 `/saveMatchData`

页面默认请求：

- `http://127.0.0.1:1111/player_list`
- `http://127.0.0.1:1111/teamNames`
- `http://127.0.0.1:1111/setMvp`
- `http://127.0.0.1:1111/mvp`
- `http://127.0.0.1:1111/saveMatchData`

#### `pov_switching.py`

独立脚本，启动自己的 GSI Server，然后根据当前观察选手自动调用局域网内 vMix / 设备接口切 POV。

依赖的外部地址：

- `http://192.168.15.19:8088/api/?Function=OverlayInput1In&Input=`
- `http://192.168.15.19:8088/API/?Function=OverlayInput1Off`

#### `check.py`

用于检查配置文件中的 Steam ID 是否都存在于数据库中。当前默认读取：

```text
player_info/HF_GL.json
```

## 5. 关键数据与状态文件

### 5.1 `player_info.json`

这是当前项目最关键的运行时配置文件之一。示例结构如下：

```json
{
  "player": {
    "7656...": {
      "player_name": "FL1T",
      "team_name": "Virtus",
      "player_seat": 1
    }
  },
  "teams": {
    "left": {
      "fullname": "Team Spirit",
      "shortname": "Team Spirit"
    },
    "right": {
      "fullname": "Virtus.Pro",
      "shortname": "Virtus.Pro"
    }
  },
  "match_id": "",
  "schedule_id": "",
  "is_over": "0"
}
```

主要用途：

- 定义 10 名选手的 Steam ID、显示名、战队和舞台座位
- 定义左右两侧队伍的全称和简称
- 提供当前比赛的 `match_id`、`schedule_id`
- 记录比赛是否结束

多个模块都会直接读取该文件：

- `app.py`
- `service.py`
- `all_api.py`
- `pov_switching.py`
- `gsi/server.py`

这意味着任何字段格式变更都会产生连锁影响。

### 5.2 `gsi_data.json`

比赛结束时由 `gsi/server.py` 写入，作为赛后快照被以下逻辑使用：

- `all_api.py` 的 `/scores`
- `all_api.py` 的赛后记分板
- `app.py` 的 `/scoreboard`

### 5.3 `adr_json/`

代码预期每回合保存一个 ADR/伤害快照文件，用于赛后 ADR 计算。当前已弃用

### 5.4 其他示例 JSON 文件

仓库中还有若干静态/样例文件：

- `board.json`
- `first_half.json`
- `second_half.json`
- `overtime.json`
- `seat_screen.json`
- `res.json`

## 6. 数据库模型

### 6.1 表模型概览

`models.py` 中当前定义的主要 ORM 类如下：

| 分类 | 表 | ORM 类 | 说明 |
| ---- | ---- | ---- | ---- |
| 赛程/大场 | `game_list` | `GameList` | 比赛记录，含周次、场次、BO 类型、获胜队等 |
| 选手主数据 | `player_list` | `PlayerList` | Steam ID、选手名、昵称、队伍、首发/离线标记 |
| 赛后数据 | `data_game` | `DataGame` | 单场选手赛后汇总数据 |
| 赛程同步 | `schedule` | `Schedule` | 赛程信息 |
| 小局比赛 | `match` | `Match` | 单张地图/小局信息 |
| 实时比赛 | `real_time_match` | `RealTimeMatch` | 实时比分表 |
| 实时选手 | `real_time_player` | `RealTimePlayer` | 实时选手击杀/死亡/助攻 |
| 回合数据 | `data_round` | `DataRound` | 选手每回合数据 |
| 线下主数据 | `player_offline` | `PlayerOffline` | 线下赛需要的选手信息 |
| 回合赛果 | `data_round_team` | `DataRoundTeam` | 每回合胜方和获胜方式 |
| 对比选择 | `cp_team` | `CpTeam` | 队伍对比选择 |
| 对比选择 | `cp_player` | `CpPlayer` | 选手对比选择 |
| 展示选择 | `player_show` | `PlayerShow` | 选手展示开关 |
| 测试表 | `data_game_test` | `DataGameTest` | 赛后数据测试表 |
| 测试表 | `game_list_test` | `GameListTest` | 比赛记录测试表 |

### 6.2 代码中的主要读写链路

#### 实时接口依赖

- `app.py` 的实时大多数接口直接读取 `global_data.data`
- `service.py` 只做拼装，不落库

#### 赛后数据依赖

- `/saveMatchData` 写 `DataGame`、`GameList`
- `get_aftergame_board()` 查询 `DataGame` + `PlayerOffline`
- `get_aftergame_slide_bar()` 查询 `DataRoundTeam`
- `mvp()` 查询 `GameList`、`DataGame`、`PlayerList`
- `analyse.py` 查询 `Schedule`、`Match`、`DataRoundTeam`、`DataGame`、`PlayerList`

#### 预留但默认未启用

- `store_real_time_data()` 会写 `RealTimeMatch`、`RealTimePlayer`、`Schedule`、`Match`
- `store_round_data()` 会写 `DataRound`、`DataRoundTeam`

## 7. 运行方式

### 7.1 环境要求

- Python 3
- MySQL 
- CS 客户端可加载 GSI 配置并向本机推送
- 局域网设备可访问（若需要现场控制/POV）

### 7.2 推荐启动顺序

#### 实时服务

1. 配置或更新 `player_info.json`
2. 将 `gamestate_integration_GSI.cfg` 放入 CS 对应目录
3. 确保游戏会向 `127.0.0.1:3000` 推送 GSI
4. 启动：

```bash
python3 app.py
```

注意：

- 如果没有第一条有效 GSI 请求，`app.py` 进程会卡在 GSI Server 等待阶段
- 成功后 Flask 对外监听 `0.0.0.0:1234`

#### 赛后服务

```bash
python3 all_api.py
```

成功后 Flask 对外监听 `0.0.0.0:1111`

#### 管理页

直接打开 [setting.html](/Users/jk/Projects/hero/CS-ACL-Server/setting.html) 即可，无构建步骤。

### 7.3 常用人工操作链路

#### 场中

- 游戏通过 GSI 持续向本机发送状态
- 导播/包装系统通过 `:1234` 拉实时接口

#### 赛后

1. 比赛结束，确认 `gsi_data.json` 已生成，`player_info.json.is_over == "1"`
2. 打开 `setting.html`
3. 选择本局 MVP
4. 填写 `match_code`、`match_id`、周次、场次、BO 信息、获胜队等
5. 提交到 `/saveMatchData`
6. 由后端抓取 5E XML 并写入数据库

## 8. 外部依赖

### 8.1 外部系统

| 依赖 | 用途 | 位置 |
| ---- | ---- | ---- |
| CS GSI | 实时游戏数据输入 | `gsi/server.py`, `gamestate_integration_GSI.cfg` |
| 阿里云 MySQL RDS | 赛事数据存储 | `models.py` |
| 5E XML 接口 | 赛后数据抓取 | `all_api.py:/saveMatchData` |
| 局域网控制接口 | 炸弹/暂停/BGM/POV 等现场控制 | `app.py`, `pov_switching.py` |

### 8.2 局域网

主要内网地址：

- `192.168.15.235:8000`
- `192.168.200.49:8000`
- `192.168.15.19:8088`

这些地址和演播/导播现场环境有强耦合，需要根据实际情况修改。
