# Docker Compose（Prod Overlay）

本仓库默认的 `docker-compose.yml` 以 **dev/本地调试** 为主（会暴露 Postgres/Redis 端口，便于本机连接）。

生产/预发布建议叠加 `docker-compose.prod.yml`，默认不对公网暴露 DB/Redis：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

在提交/部署前，可用以下命令校验合并后的配置是否可生成：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

注意：
- `.env.docker` 属于本机/部署平台配置，不要提交到 git。
- 如需进一步缩小暴露面（例如只暴露前端、后端走内网/反代），请在此 overlay 基础上继续收紧。

