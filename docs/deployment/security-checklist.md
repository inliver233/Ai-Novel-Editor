# Production Security Checklist（部署安全清单）

> 目的：把“生产部署必须确认的安全项”落盘为可执行 checklist，避免误配导致鉴权绕过、跨站请求、明文密钥泄露或端口暴露。

## 0) 基本前提

- [ ] 生产环境必须 `APP_ENV=prod`（禁止用 `dev` 启动生产）
- [ ] 生产环境不设置 `AUTH_DEV_FALLBACK_USER_ID`（必须为空/不配置）
- [ ] 生产环境必须配置 `SECRET_ENCRYPTION_KEY`（用于服务端加密存储 API Key；不要提交到 git）

## 1) CORS（跨域）

- [ ] `CORS_ORIGINS` 使用明确 allowlist（不要用 `*`）
- [ ] `allow_credentials=true` 时，`allow_origins` 不能是 `*`（必须是具体域名列表）
- [ ] 仅允许必要的 headers（例如 `Authorization` / `X-LLM-*` / `Content-Type`）

## 2) Cookie / Session（浏览器会话）

- [ ] Cookie 必须带 `Secure`（仅 HTTPS 发送）
- [ ] Cookie 必须带 `HttpOnly`（JS 不可读，避免 XSS 读到会话信息）
- [ ] Cookie 必须带合适的 `SameSite`（默认建议 `Lax`；若需要跨站嵌入再评估 `None` 且必须 `Secure`）
- [ ] 明确“过期信息”从哪返回（建议从 `/api/auth/user` 返回 `session.expire_at`，避免依赖 JS 读 cookie）

## 3) 端口暴露 / 网络隔离

- [ ] 只暴露必要端口（对外通常只暴露网关/前端；数据库/Redis 不对公网开放）
- [ ] 服务间通信优先走 docker network 内网（不要用 `0.0.0.0:xxxx` 全暴露）
- [ ] 如需反代（nginx/caddy），确认只代理必要路径并限制上游可达性

## 4) Secrets 管理

- [ ] `.env.docker` / `.env` 只放本机/部署平台，不提交到仓库
- [ ] 不在日志/响应/导出中返回明文 key/token（仅允许 `has_api_key` / `masked_api_key`）
- [ ] 用部署平台的 secret store（GitHub Actions Secrets / Kubernetes Secret / Vault 等）注入敏感变量

## 5) 运行时与镜像（Docker）

- [ ] 尽可能以非 root 用户运行容器
- [ ] 需要写入的目录（例如 `/data`、`/data/chroma`）在镜像内预创建并 chown 给运行用户；挂载 volume 后仍可写
- [ ] 文件系统按需只读挂载（避免容器内写入任意路径）
- [ ] 生产镜像不包含开发工具与无关文件（减小攻击面）

## 6) 自查（一次执行就够）

手工自查步骤（建议在生产/预发布环境各跑一次）：

1. [ ] `APP_ENV=prod` 且 `AUTH_DEV_FALLBACK_USER_ID` 未设置
2. [ ] 启动后访问 `/api/auth/user` 未登录应返回 `401`
3. [ ] 登录后检查响应 `Set-Cookie`：包含 `Secure/HttpOnly/SameSite`（按你的策略）
4. [ ] 前端域名不在 allowlist 时，浏览器请求应被 CORS 拒绝
5. [ ] 数据库/Redis 端口不对公网暴露（仅容器网络可达）

## 7) 相关文件与链接（本仓库）

- Compose：`../../docker-compose.yml`
- Prod overlay（不暴露 DB/Redis 端口）：`docker-compose-prod.md`
- Backend Dockerfile：`../../backend/Dockerfile`
- Frontend Dockerfile：`../../frontend/Dockerfile`
- 部署说明：`../../README.md`（Docker Compose 章节）

## 8) 依据（Review）

- `docs/reviews/REV-001.md`
- `docs/reviews/REV-002.md`
- `docs/reviews/REV-017.md`
