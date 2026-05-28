# 局域网路演演示运行手册

## 目标

使用一台 Windows 主机运行 FactorPlatform，路演现场其他电脑只通过浏览器访问前端页面。DeepSeek key、本地模型、数据库和 qlib 数据都保留在主机上，不分发到观众电脑。

默认模式是 `REAL`：Docker Postgres/Redis + 本地 API + qlib CN/US + production Next 前端。真实链路失败时，启动脚本会自动进入 `DEMO_FALLBACK`，这是只读 mock 展示模式，页面顶部会显示 `DEMO FALLBACK / MOCK DATA / READ ONLY`。

## 路演前 10 分钟检查清单

1. 打开 Docker Desktop，等待 Docker Engine 完全启动。
2. 确认主机连接可信网络，优先使用主机手机热点或同一可信 Wi-Fi，避免公共会议 Wi-Fi 阻止设备互访。
3. 确认本地 qlib 数据目录存在：
   - CN: `D:\mcQlib\data\qlib_bin\cn_data`
   - US: `D:\mcQlib\data\qlib_bin\us_data`
4. 在 PowerShell 中启动：

```powershell
cd D:\FactorPlatform
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_demo_lan.ps1
```

启动成功后脚本会打印：

```text
MODE=REAL
LOCAL Web: http://127.0.0.1:3001/dashboard
LAN Dashboard: http://<主机局域网IP>:3001/dashboard
LAN Signal Center: http://<主机局域网IP>:3001/signal-center
```

只把 `LAN Dashboard` 或 `LAN Signal Center` 分享给现场电脑。不要分享后端 `/docs` 地址。

## 常用启动参数

手动指定局域网 IP：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_demo_lan.ps1 -PublicHost 192.168.1.23
```

自动放行 Windows 防火墙前端端口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_demo_lan.ps1 -OpenFirewall
```

强制只读兜底展示：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_demo_lan.ps1 -DemoFallback
```

## 健康检查

真实模式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_stack_health.ps1 -BackendPort 8003 -FrontendPort 3001 -LanHost <主机局域网IP> -Mode real
```

兜底模式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\check_stack_health.ps1 -FrontendPort 3001 -LanHost <主机局域网IP> -Mode demo
```

检查输出会显示：

- local frontend/backend health
- LAN frontend URL
- `/backend/health` 代理状态
- qlib CN/US 状态
- AI provider readiness
- 当前是否为 `REAL` 或 `DEMO_FALLBACK`

## 现场打不开怎么办

1. 主机先打开 `http://127.0.0.1:3001/dashboard`，确认本机可访问。
2. 观众电脑确认和主机在同一个网络。
3. 如果同一网络仍打不开，运行：

```powershell
New-NetFirewallRule -DisplayName "FactorPlatform Demo Web 3001" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 3001 -Profile Private
```

如果脚本实际选择了 `3002`，把命令里的端口改成 `3002`。

## 现场网络 fallback

很多会议 Wi-Fi 会阻止同一局域网内设备互相访问。遇到这种情况，优先使用：

- 主机手机热点；
- 主机自建 Windows 移动热点；
- 路演小路由器；
- 最后才使用本机投屏。

## 安全注意

- 只开放前端端口 `3001/3002`。
- 后端 API、`/docs`、DeepSeek key、本地模型和 qlib/Wind 数据都留在主机本机。
- 终端和文档只显示 key 的 `<set>` / `<missing>` 状态，不打印真实 key。
- `DEMO_FALLBACK` 是只读 mock 展示，不能运行刷新、回测、挖掘或数据维护写操作。
