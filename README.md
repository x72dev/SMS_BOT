<div align="center">

<img src="https://capsule-render.vercel.app/api?type=rounded&height=220&color=0:EDEDED,45:CBD5E1,100:64748B&text=SMS%20Bot%20v6&fontSize=50&fontColor=111827&fontAlignY=40&desc=Elegant%20README%20for%20Telegram%20Controlled%20Phone%20Link%20SMS%20Automation&descAlignY=63" width="100%" />

# SMS Bot V6 · 自动化

<img src="https://readme-typing-svg.demolab.com?font=Inter&weight=600&size=20&duration=2600&pause=1200&color=334155&center=true&vCenter=true&repeat=true&width=980&lines=Telegram+Remote+Control;Phone+Link+UI+Automation;phone.db+Confirmation;Monitoring+%2B+Recovery+for+Long-Running+Tasks" alt="Typing SVG" />

<p>
  <img src="https://img.shields.io/badge/Windows-10%20%2F%2011-0F172A?style=for-the-badge&logo=windows&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.9%2B-1E293B?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Telegram-Bot%20API-334155?style=for-the-badge&logo=telegram&logoColor=white" />
  <img src="https://img.shields.io/badge/PowerShell-Automation-475569?style=for-the-badge&logo=powershell&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-phone.db-64748B?style=for-the-badge&logo=sqlite&logoColor=white" />
</p>

**Telegram 负责控制，Phone Link 负责执行，数据库负责确认，监控负责恢复。**

<p>
  <a href="#项目概览">项目概览</a> ·
  <a href="#核心优势">核心优势</a> ·
  <a href="#系统路径">系统路径</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#命令速查">命令速查</a> ·
  <a href="#可靠性设计">可靠性设计</a> ·
  <a href="#已知限制">已知限制</a>
</p>

</div>

---

## 项目概览

> 这不是一个只会“点界面发短信”的脚本集合，而是一套围绕 **远程控制、执行落地、结果确认、异常恢复** 搭起来的 Windows 短信自动化系统。

SMS Bot v5 运行在 Windows 环境中，通过 Telegram Bot 接收指令，调用 PowerShell 驱动 Phone Link 完成发送，再由 Python 持续检查 `phone.db` 中是否出现新的已发送记录，最后由监控逻辑负责感知异常并尝试恢复。

这套设计的价值不在“能发”，而在：

- **可控**：所有动作都可以通过 Telegram 远程发起与管理
- **可判定**：不把 UI 返回值当最终结果，而是继续做数据库确认
- **可观察**：进程、窗口、数据库活跃度都有监控
- **可恢复**：异常时能自动拉起 Phone Link 并恢复任务进度

---

## 核心优势

<table>
<tr>
<td width="50%" valign="top">

### 01 · 发送不是终点
发送动作完成后，系统不会立刻把结果判定为成功，而是继续轮询 `phone.db`。只有检测到新的发送记录，才会把这一条短信真正记为成功。

</td>
<td width="50%" valign="top">

### 02 · 双引擎执行
`send_sms.ps1` 支持 **UIA** 与 **SendKeys** 两种执行方式。前者偏精确定位，后者偏环境兼容，可以在不同桌面状态下提供更稳的落地能力。

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 03 · 监控不只是看进程
这套项目不是只检查 Phone Link 有没有活着，还会观察 `phone.db` 是否持续活跃、窗口是否卡死，以及异常后是否需要拉起恢复流程。

</td>
<td width="50%" valign="top">

### 04 · 为长期运行而设计
支持任务持久化、失败通知、批量导入、模板替换、多任务组、短信回流 Telegram，更适合需要长期运行与远程管理的场景。

</td>
</tr>
</table>

---

## 系统路径

```text
Telegram 指令
    ↓
Bot 控制层（sms_bot.py）
    ↓
发送引擎（send_sms.ps1）
    ↓
Windows Phone Link UI
    ↓
Android 侧发出短信
    ↓
phone.db 写入发送记录
    ↓
Bot 二次确认结果
    ↓
通知 / 失败告警 / 任务恢复
```

### 四层职责

| 层级 | 作用 | 关键文件 |
|---|---|---|
| 控制层 | 接收 Telegram 命令、管理任务、回传状态 | `bot/sms_bot.py` |
| 执行层 | 驱动 Phone Link 完成短信发送 | `scripts/send_sms.ps1` |
| 确认层 | 检查 `phone.db` 是否出现新发送记录 | `bot/sms_bot.py` |
| 恢复层 | 检测异常并尝试自动恢复 | `scripts/check_status.ps1` / `scripts/restart_phonelink.ps1` |

---

## 能力一览

| 模块 | 已实现能力 |
|---|---|
| 发送方式 | 单条发送、批量发送 |
| 数据导入 | `.txt`、`.xlsx` |
| 模板能力 | 变量替换、批量生成内容 |
| 任务管理 | 多任务组、暂停、继续、停止、恢复 |
| 结果判定 | UI 执行 + `phone.db` 二次确认 |
| 监控恢复 | 进程监控、窗口状态监控、数据库活跃度监控、自动恢复 |
| 通知反馈 | 失败告警、进度通知、短信接收回流 |
| 本地管理 | 安装、配置、启停、日志查看、卸载、引擎切换 |

---

## 快速开始

### 运行前确认

- Windows 10 / 11
- Android 手机已成功连接 Phone Link
- 手动发送短信正常
- 已准备 Telegram Bot Token
- 当前网络可访问 Telegram Bot API

### 安装

```text
双击 smsbot.bat
选择 6. Install
按提示完成配置
```

安装过程会自动完成：

- Python 虚拟环境创建
- 依赖安装
- `config.json` 生成
- Telegram 连通性测试
- 开机自启注册

### 启动

```text
Telegram 发送 /start
进入主菜单
导入数据或直接发送
确认任务
开始执行
```

---

## 命令速查

| 命令 | 说明 |
|---|---|
| `/start` | 打开主菜单 |
| `/send` | 单条发送 |
| `/batch` | 批量发送入口 |
| `/template` | 模板管理 |
| `/import` | 导入说明 |
| `/status` | 查看任务状态 |
| `/pause` | 暂停任务 |
| `/resume` | 继续任务 |
| `/stop` | 停止任务 |
| `/monitor` | 监控开关 |
| `/settings` / `/set` | 查看或修改配置 |
| `/sim` | 查看或切换 SIM |
| `/resume_tasks` | 恢复中断任务 |
| `/restart` | 重启 Bot |

---

## 批量数据格式

### 文本导入

```text
手机号|短信内容
手机号|短信内容
```

### Excel 常见字段

```text
姓名
手机号码
银行卡号
放款日期
放款金额
```

### 模板变量示例

```text
{姓名}
{卡号}
{日期}
{金额}
```

---

## 可靠性设计

<table>
<tr>
<td width="50%" valign="top">

### 发送侧
- 发送互斥，避免并发冲突
- 号码标准化处理
- UIA / SendKeys 双路径执行
- 发送后自动回到干净状态

</td>
<td width="50%" valign="top">

### 确认侧
- 不依赖单次 UI 返回值
- 轮询 `phone.db` 判断是否真实写入
- 失败和超时分开处理
- 减少“假成功”记录

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 运行侧
- 任务持久化
- 中断后恢复任务进度
- 多日志文件便于排障
- 管理器可独立操作启停与配置

</td>
<td width="50%" valign="top">

### 监控侧
- 进程存活检测
- 数据库活跃度检测
- 窗口卡死检测
- 自动重启 Phone Link 与恢复任务

</td>
</tr>
</table>

---

## 仓库结构

```text
sms-bot-main/
├─ smsbot.bat
├─ bot/
│  ├─ sms_bot.py
│  ├─ setup.py
│  └─ reconfig.py
└─ scripts/
   ├─ send_sms.ps1
   ├─ check_status.ps1
   ├─ inspect_phonelink.ps1
   ├─ restart_phonelink.ps1
   ├─ install.bat
   ├─ start.bat
   ├─ stop.bat
   ├─ restart.bat
   ├─ reconfig.bat
   ├─ uninstall.bat
   └─ download_python.py
```

---

## 本地管理入口

`smsbot.bat` 提供统一的本地管理菜单，可以完成：

- 启动 / 停止 / 重启 Bot
- 查看运行状态与日志
- 安装与卸载
- 修改配置
- 切换发送引擎

这意味着即使不进入代码层，也可以直接在 Windows 侧完成常见维护动作。

---

## 已知限制

> 本项目依赖 Phone Link 的桌面界面，而不是官方短信 API。

因此它具备高度可操作性，也天然会受到桌面环境影响：

- Phone Link 更新可能导致 UI 自动化细节变化
- 系统弹窗、焦点抢占、窗口遮挡会影响执行稳定性
- 远程桌面断开后，界面类自动化可能受影响
- 更适合稳定、克制、连续运行，而不是极限提速

---

## 适合的使用方式

- 需要通过 Telegram 远程触发短信发送的人
- 需要批量导入与模板替换的人
- 需要把“是否真正发出”作为核心判定条件的人
- 需要长期挂机，并希望异常时能自动恢复的人

---

## 最后

<div align="center">

### **SMS Bot v6 的价值，不只是自动化发送。**

它真正完成的是把一个依赖桌面界面的发送动作，包装成一套更完整的运行系统：

**可控制 · 可确认 · 可观察 · 可恢复**

</div>
