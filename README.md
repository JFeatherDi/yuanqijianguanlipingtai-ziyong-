# IOTAT 实验室元器件管理平台

面向实验室的轻量级元器件库存管理平台。前后端完全分离：前端 Vue 3 单页应用，后端 Flask REST API，
数据库 SQLite（WAL 模式）。专为低配服务器（≥350M 内存 / ≥4G 存储）设计。

## 功能

- **登录**：账号 `IOTAT` / 密码 `swust350351`（可用环境变量覆盖）
- **主页看板**：指标卡、实时动态、分类库存占比、库存总览环形图、出入库趋势柱状图、库存预警清单
- **元器件管理**：分类 / 名称 / 规格 / 单位 / 库位 / 库存 / 预警值 / 备注，支持排序、检索、增删改
- **入库登记** / **出库领用**：选器件 → 填数量 → 提交，出库自动校验库存
- **库存预警**：按缺口排序的补货清单，区分「缺货」与「预警」
- **操作记录**：全部出入库流水，按类型筛选、关键字检索、分页浏览
- **数据管理**：Excel (.xlsx/.xlsm) / CSV 批量导入，导出 CSV，下载导入模板
- **系统设置**：账号信息、系统概况、安全与并发说明、环境变量清单

## 界面设计

配色与版式对齐企业级数据看板模板：浅蓝 + 白，冷灰底，蓝色作为唯一强调色。

- 主色 `#2f7fd1`，卡片标题条 `#4a96de`，页面底色 `#edf1f6`，描边 `#dce4ed`
- 所有颜色定义在 `frontend/src/styles/tokens.css`，组件只引用 `var(--c-*)`，不写裸十六进制
- 全站使用 SVG 图标（`AppIcon`），**不使用 emoji**，不依赖任何图标字体
- 图表为手写 SVG（`BarChart` / `DonutChart`），配色使用同一蓝色梯度，不依赖图表库与 CDN
- 字体使用系统字体栈，离线内网可用

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue 3 + Vite + Vue Router + Pinia | Composition API，路由级代码分割 |
| 后端 | Flask 3 + waitress | 应用工厂 + 蓝图，生产级 WSGI |
| 数据库 | SQLite（WAL 模式） | Python 内置，读写并发不互锁 |
| 表格解析 | openpyxl | 仅用于 xlsx |

前端构建产物约 193 KB JS（主包 gzip 约 49 KB），运行时常驻内存约 30–50 MB。

## 项目结构

```
.
├── backend/                     # 后端（Flask）
│   ├── app.py                   # 应用工厂：装配配置、蓝图、跨域、静态资源
│   ├── config.py                # 集中式配置，全部可用环境变量覆盖
│   ├── db.py                    # SQLite 连接、schema、通用查询助手
│   ├── security.py              # 登录限流 + login_required
│   ├── api/                     # 接口层（蓝图注册表在 __init__.py）
│   │   ├── auth.py              # 登录 / 登出 / 当前用户
│   │   ├── components.py        # 元器件 CRUD
│   │   ├── stock.py             # 入库 / 出库
│   │   ├── records.py           # 流水查询、导入、导出、模板
│   │   └── stats.py             # 看板统计（概览 / 分类 / 趋势）
│   ├── services/                # 业务逻辑（不依赖 Flask 请求上下文）
│   │   ├── catalog.py           # 字段规范化与校验
│   │   ├── inventory.py         # 库存变更唯一入口
│   │   └── importer.py          # Excel / CSV 解析（纯函数）
│   ├── tests/smoke.py           # 接口冒烟测试
│   └── requirements.txt
├── frontend/                    # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/                 # client.js（统一 HTTP）+ endpoints.js（接口清单）
│   │   ├── components/          # ui/ 基元 · charts/ 图表 · layout/ 布局 · 业务组件
│   │   ├── composables/         # useRefresh
│   │   ├── domain/              # navigation（导航结构）· inventory（领域字典）
│   │   ├── router/
│   │   ├── stores/              # auth · inventory · dashboard · toast
│   │   ├── styles/              # tokens.css（设计令牌）· base.css（共享组件类）
│   │   ├── utils/               # format（数值/日期格式化）
│   │   └── views/               # 8 个页面
│   ├── dist/                    # 构建产物（已提交，见下方说明）
│   └── vite.config.js
├── start.sh / start.bat         # 一键启动
└── backend/data.db              # SQLite 数据库（首次启动自动生成）
```

## 一键启动

### Linux / macOS（服务器）

```bash
chmod +x start.sh
./start.sh
```

### Windows（本地）

```bat
start.bat
```

脚本会自动：检测前端构建产物 → 创建虚拟环境 → 安装依赖 → 初始化数据库 → 启动服务（`0.0.0.0:5000`）。

`frontend/dist` 已随仓库提交，因此**服务器只需要 Python，不需要安装 Node**。
如果 dist 不存在但本机有 npm，脚本会自动构建；两者都没有时会给出明确提示。

## 开发模式（前后端分别启动）

```bash
# 终端 1：后端
python -m backend.app

# 终端 2：前端（Vite 会把 /api 代理到 127.0.0.1:5000）
cd frontend
npm install
npm run dev          # http://localhost:5173
```

开发期由 Vite 代理 `/api`，浏览器视作同源，Session Cookie 直接生效，无需额外跨域配置。

生产部署时先在 `frontend/` 执行 `npm run build`，随后只启动 Flask 即可 ——
它会托管 `frontend/dist`，并把非 `/api` 路径回退到 `index.html` 以支持前端路由。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `5000` | 监听端口 |
| `APP_DB_PATH` | `backend/data.db` | 数据库文件 |
| `APP_SECRET_KEY` | 内置默认值 | 会话签名密钥，**正式部署务必修改** |
| `APP_USERNAME` / `APP_PASSWORD` | `IOTAT` / 内置 | 登录凭据，**正式部署务必修改** |
| `APP_SESSION_HOURS` | `12` | 会话有效期 |
| `APP_LOGIN_MAX_FAIL` / `APP_LOGIN_LOCK_SECONDS` | `5` / `300` | 登录限流 |
| `APP_MAX_UPLOAD_MB` | `8` | 上传体积上限 |
| `APP_THREADS` / `APP_CONNECTION_LIMIT` | `8` / `20` | waitress 并发限制 |
| `APP_CORS_ORIGINS` | `http://localhost:5173,...` | 允许携带 Cookie 跨域的前端地址 |
| `APP_STATIC_DIST` | `frontend/dist` | 前端构建产物目录 |

## 批量导入

1. 进入「数据管理」页，先点「下载导入模板」
2. 按表头填写：`名称, 分类, 规格, 单位, 位置, 库存, 预警值, 备注`
3. 拖入或选择文件后点「确认导入」

列顺序不限，中英文表头都能识别（别名表见 `backend/services/importer.py`）。
**名称 + 规格**都相同的行会累加到已有库存，不会新建重复器件；「库存」列填的是本次增量而非覆盖值。
导入会写入类型为「导入」的流水，可在「操作记录」页追溯。

## 接口一览

```
POST   /api/auth/login            登录
POST   /api/auth/logout           登出
GET    /api/auth/me               当前用户

GET    /api/components            列表（支持 q / category / low）
POST   /api/components            新增
PUT    /api/components/:id        更新
DELETE /api/components/:id        删除（连带清理流水）

POST   /api/stock/in              入库
POST   /api/stock/out             出库（原子扣减，不会扣成负数）

GET    /api/records               流水（q / type / limit / offset，返回 total）
GET    /api/records/export        导出元器件清单 CSV
GET    /api/records/template      下载导入模板
POST   /api/records/import        批量导入

GET    /api/stats/overview        看板概览指标
GET    /api/stats/categories      分类库存分布
GET    /api/stats/flow?days=7     出入库趋势
GET    /api/health                健康检查
```

所有接口返回统一的 `{ ok: boolean, ... }` 封套；未登录返回 `401`。

## 并发与安全

- **SQLite WAL 模式**：读不阻塞写、写不阻塞读
- **原子出库**：`UPDATE ... WHERE stock >= ?` 单语句扣减，多人同时领用最后一件不会扣成负数
- **写锁排队**：繁忙时最多等待 10 秒，而不是直接抛 `database is locked`
- **登录限流**：同一 IP 连续失败 5 次锁定 5 分钟
- **会话过期**：12 小时无操作自动登出，每次请求续期
- **生产 WSGI**：waitress 限制最多 8 个线程 + 20 连接，单请求超时 30 秒
- **上传上限**：单请求正文最大 8 MB
- **缓存策略**：`index.html` 回源校验、哈希资源长期强缓存、接口响应 `no-store`
  （避免发版后浏览器继续使用旧入口文件导致白屏）

## 测试

```bash
python backend/tests/smoke.py
```

覆盖登录鉴权、限流、CRUD、出入库与超额拦截、筛选、统计分组、导入导出、
缓存头与 SPA 回退等 41 项断言，跑完自动清理临时数据库。

## 访问

- **本机**：http://localhost:5000
- **局域网**：http://<服务器内网IP>:5000
- **内网穿透**：直接用穿透域名访问，无需额外配置

## 常见问题

**Q: 服务器没有 Python？**
A: `sudo apt install python3 python3-venv`（Debian/Ubuntu）或 `yum install python3`（CentOS）。

**Q: 服务器没有 Node，能用吗？**
A: 可以。`frontend/dist` 已提交，只需 Python。若修改了前端源码，在开发机执行
`cd frontend && npm run build` 后把 `dist` 一起部署即可。

**Q: 端口 5000 被占用？**
A: 设置环境变量 `APP_PORT=8000`，或修改 `backend/config.py` 的默认值。

**Q: 如何备份数据？**
<<<<<<< HEAD
A: 复制 `backend/data.db` 即可（建议先停服务，或连同 `-wal` / `-shm` 一起复制）。

**Q: 换了域名 / 端口，跨域报错？**
A: 把前端地址加入 `APP_CORS_ORIGINS`（逗号分隔）。

## 安全说明

- 默认账号密码内置，**正式部署请通过 `APP_USERNAME` / `APP_PASSWORD` / `APP_SECRET_KEY` 覆盖**
- 服务监听 `0.0.0.0`，建议仅在内网或通过内网穿透使用，不要直接暴露公网
- 如需 HTTPS，建议在穿透层或反向代理层处理
=======
A: 直接复制 `data.db` 文件即可。


## 🔄 Git 推送自动部署（Debian 服务器）

配置后，本地 `git push` → 服务器自动拉取代码并重启服务。

### 1. 服务器初始安装

```bash
# 克隆项目到服务器
git clone git@github.com:JFeatherDi/yuanqijianguanlipingtai-ziyong-.git ~/components
cd ~/components
bash start.sh    # 首次启动，创建 venv 和数据库
```

### 2. 配置 Webhook Secret

在服务器上设置环境变量（与 GitHub Webhook 配置保持一致）：

```bash
# 生成随机密钥
openssl rand -hex 32
# 写入 systemd 服务环境
sudo mkdir -p /etc/systemd/system/auto-deploy.service.d
echo '[Service]
Environment="WEBHOOK_SECRET=你的随机密钥"' | sudo tee /etc/systemd/system/auto-deploy.service.d/webhook.conf
```

### 3. 安装 systemd 服务

```bash
sudo cp ~/components/auto-deploy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now auto-deploy
sudo systemctl status auto-deploy
```

### 4. 配置 GitHub Webhook

1. 打开 GitHub 仓库 → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**：`http://<服务器公网IP或域名>:5000/webhook`
3. **Content type**：`application/json`
4. **Secret**：填入和服务端相同的密钥
5. **Events**：勾选 **Just the push event**
6. **Add webhook**

### 5. 后续使用

本地修改后直接推送即可自动部署：

```bash
git add . && git commit -m "更新内容" && git push origin master
```

服务器会在几秒内自动拉取代码、更新依赖、重启服务。

### 项目结构（自动部署后）

```
.
├── app.py
├── static/
├── deploy.sh            # 自动部署脚本
├── auto-deploy.service  # systemd 服务文件
├── requirements.txt
├── start.sh
├── start.bat
└── data.db
```
>>>>>>> efd365a1be0d9e96453e6f9465d8d299a7842ecd
