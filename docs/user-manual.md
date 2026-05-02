# explore-os 用户手册

explore-os 是一款订阅驱动的论文日报助手，围绕你声明的研究兴趣，自动从 arXiv / HuggingFace Daily Papers 检索论文，进行分档解读（略读 + 精读），并通过邮件或应用界面推送。

---

## 目录

1. [安装与启动](#1-安装与启动)
2. [界面功能](#2-界面功能)
3. [配置指南](#3-配置指南)
4. [命令行参考](#4-命令行参考)
5. [常见问题](#5-常见问题)

---

## 1. 安装与启动

### 1.1 获取应用

从发布渠道获取打包好的 `explore-os Setup.exe`（Windows）或 `explore-os.dmg`（macOS）。

双击安装包，按向导完成安装。Windows 会提示"Windows 已保护你的电脑"，点击"更多信息" → "仍要运行"即可。

### 1.2 首次启动

首次启动时会弹出窗口让你选择**数据目录**：

- **默认路径**（推荐）：`%APPDATA%\explore-os`（Windows）或 `~/Library/Application Support/explore-os`（macOS）
- **自定义目录**：如果你想把数据放在其他位置（如移动硬盘），点击"浏览"选择

数据目录包含：
- `explore_os.sqlite3` — 数据库
- `media/` — PDF 缓存和渲染图片
- `logs/` — 运行日志

### 1.3 启动应用

安装完成后，双击桌面快捷方式或开始菜单中的图标启动。

首次使用需要先完成配置（见第 3 章）。

---

## 2. 界面功能

应用主界面分为 4 个页面，通过顶部导航栏切换。

### 2.1 论文列表页（首页）

**路径**：`/`

**功能**：
- 查看所有已收录的论文
- 顶部状态栏可筛选：全部 / 未决（new）/ 已读（read）/ 已收藏（archived）
- 每张卡片显示：标题、作者、关键词、收录时间
- 点击卡片进入论文详情页
- 右上角数字 badge 显示未决论文数量

**操作**：
- 勾选卡片左侧复选框 → 底部出现"批量操作"按钮（删除 / 标记已读 / 收藏）
- 点击卡片 → 进入详情

### 2.2 论文详情页

**路径**：`/papers/:arxivId`

**功能**：三栏布局

| 栏 | 宽度 | 内容 |
|---|---|---|
| 左侧 | 250px | 论文结构树（目录） |
| 中间 | 自适应 | markdown 渲染的论文全文（支持 KaTeX 公式） |
| 右侧 | 400px | ClaimCard 列表（核心claim + 证据 + 反向信号标记） |

**操作**：
- 点击结构树章节 → 滚动到正文对应位置
- 点击 ClaimCard → 展开证据详情
- 顶部操作栏：标记已读 / 收藏 / 添加标签 / 写笔记 / 管理引用链接

### 2.3 订阅管理页

**路径**：`/subscriptions`

**功能**：管理你的研究兴趣订阅

**操作**：
- 点击现有订阅 → 编辑
- 点击"+ 新建订阅" → 创建新订阅

订阅配置项：
- **名称**：自定义名称，如 `video-generation-daily`
- **启用**：开关
- **视角**：researcher / engineer / pm / student（决定解读风格）
- **兴趣关键词**：如 `video generation`、`text-to-video`
- **排除关键词**：如 `medical imaging`
- **数据源**：arxiv（指定分类如 `cs.CV, cs.LG`）/ HuggingFace Papers
- **推送设置**：最大条目数、深度（tldr / deep）

### 2.4 摄入页

**路径**：`/ingest`

**功能**：手动触发论文检索和处理

**操作**：
- **拖拽上传**：拖拽 PDF 文件到页面 → 自动解析并添加到文库
- **URL 摄入**：输入 arXiv URL（如 `https://arxiv.org/abs/2301.12345`）→ 自动拉取并解析
- **运行订阅**：选择订阅名称 → 触发一次完整检索 → 邮件推送

### 2.5 设置页

**路径**：`/settings`

三个配置区块：

#### 通用设置
- 语言：English / 中文

#### LLM 设置
- **API 端点**：如 `https://api.openai.com/v1`（阿里云百炼填 `https://dashscope.aliyuncs.com/compatible-mode/v1`）
- **API Key**：填入你的密钥
- **文本模型**：用于略读翻译、摘要（默认 `gpt-4o-mini` 或 `deepseek-v4-flash`）
- **深度模型**：用于精读解读（默认 `gpt-4o` 或对应模型）
- **多模态模型**：用于图表分类（可选）
- **视觉分类模型**：用于判定图表是否为展示类（可选）
- **每日预算**：单位 CNY，用于成本控制

#### 数据目录
- 当前路径显示
- 可手动指定自定义路径（修改后需重启应用生效）

---

## 3. 配置指南

### 3.1 配置文件的两种方式

explore-os 支持两种配置方式：

1. **UI 配置**（推荐）：在设置页填写
2. **配置文件**：直接编辑 `subscriptions.yaml`

### 3.2 订阅配置示例

默认配置路径：`数据目录/subscriptions.yaml`

```yaml
subscriptions:
  - name: video-generation-daily
    enabled: true
    perspective:
      preset: researcher
    interests:
      - "video generation"
      - "text-to-video"
      - "video diffusion"
    exclude:
      - "medical imaging"
    sources:
      - key: arxiv
        params:
          categories: [cs.CV, cs.LG]
          limit: 30
      - key: hf_papers
        params:
          limit: 20
    deliveries:
      - channel: email
        depth: tldr
        max_items: 15
```

### 3.3 环境变量配置

如果偏好配置文件（`.env`），支持以下变量：

```
# LLM
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxxxx
LLM_MODEL_TEXT=deepseek-v4-flash
LLM_MODEL_DEEP=deepseek-v4
LLM_DAILY_BUDGET_CNY=30

# SMTP 邮件（可选）
SMTP_HOST=smtp.office.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=xxxxx
EMAIL_TO_DEFAULT=your@email.com
```

---

## 4. 命令行参考

除了 GUI，你也可以使用命令行模式。

### 4.1 基础命令

```bash
# 进入项目目录
cd explore-os

# 激活环境
uv sync

# 手动运行订阅
uv run python manage.py run_subscription <subscription_name>
```

### 4.2 常用参数

| 参数 | 说明 | 示例 |
|---|---|---|
| `--target-date YYYY-MM-DD` | 指定运行日期（默认昨天） | `--target-date 2026-05-01` |
| `--dry-run` | 打印内容但不发送邮件 | |
| `--no-llm` | 跳过 LLM 调用（纯字段提取） | |
| `--no-deep` | 跳过精读 | |
| `--no-figures` | 不拉取 PDF | |
| `--limit-per-source N` | 每个 source 上限 | `--limit-per-source 10` |

### 4.3 开发模式

```bash
# 启动后端（端口 8000）
uv run python sidecar_entry.py --port 8000

# 启动前端开发服务器
cd frontend && npm run dev
```

---

## 5. 常见问题

### 5.1 首次启动报错"无法连接后端"

**原因**：后端服务未正确启动

**解决**：
1. 检查数据目录是否存在且有写入权限
2. 查看日志 `logs/explore-os.log` 具体错误信息
3. 运行 `uv sync` 确保依赖完整

### 5.2 邮件发送失败（Gmail 拒收）

**原因**：未配置 SMTP 域名 SPF/DKIM 记录

**解决**：
1. 使用企业邮箱（如腾讯企业邮、阿里邮箱）
2. 或切换到应用内推送（订阅管理页中关闭邮件渠道）

### 5.3 LLM 调用报错

**检查项**：
1. API Key 是否正确填入设置页
2. API 端点是否正确（如用阿里云百炼填 `https://dashscope.aliyuncs.com/compatible-mode/v1`）
3. 账户余额是否充足
4. 点击设置页的"测试连接"按钮诊断

### 5.4 数据目录可以迁移吗

**可以**：
1. 设置页修改数据目录路径为新位置
2. 重启应用
3. 旧目录下的 `media/` 和 `explore_os.sqlite3` 需手动复制到新目录

### 5.5 如何彻底卸载

1. 删除应用安装目录
2. 删除数据目录 `%APPDATA%\explore-os`（或你自定义的路径）
3. 如需彻底清理，删除 `%APPDATA%\explore-os` 整个文件夹

### 5.6 如何查看运行日志

数据目录下的 `logs/` 文件夹中包含：
- `explore-os.log` — 主日志
- `extract_*.log` — 抽取过程日志
- `interpret_*.log` — 解读过程日志
- `jobs_*.log` — 后台任务日志

---

## 附录：技术栈

- **后端**：Django 5 + SQLite + APScheduler
- **前端**：React 18 + TypeScript + Tailwind + shadcn/ui
- **桌面端**：Electron + PyInstaller
- **LLM**：阿里云百炼（DashScope）+ OpenAI 兼容 API
- **PDF 解析**：Docling + MuPDF
- **调度**：APScheduler in-process

---

文档版本：v1.2 | 更新日期：2026-05-02