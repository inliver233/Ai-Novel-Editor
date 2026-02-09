# 向量 Embedding 配置（provider + 项目级覆盖 + 安全存储）

本项目的 Vector RAG 需要 embeddings 配置。为避免仅依赖后端环境变量（`.env`），支持在「项目设置」中保存一份**项目级覆盖**配置。

Embedding 配置由两部分组成：

- **provider**：决定使用哪种 embedding 后端（默认 `openai_compatible`）。
- **provider 配置字段**：常见为 `base_url / model / api_key`，并可扩展 provider 专属字段（例如 Azure 的 `deployment/api_version`）。

当前项目设置（ProjectSettings）覆盖字段：

- `base_url` / `model`：明文存储（非密钥）。
- `api_key`：加密存储（不返回明文，仅回显 `masked_api_key` / `has_api_key`）。
- 若项目未配置某字段，则回退使用后端环境变量（env fallback）。

## Provider 列表（Embedding）

- `openai_compatible`：OpenAI-compatible `/embeddings`（示例：Mock LLM `http://127.0.0.1:4010/v1`）。
- `azure_openai`：Azure OpenAI embeddings（需要 `deployment` + `api_version`）。
- `google`：Google Gemini embeddings（`/v1beta/models/{model}:embedContent` / `:batchEmbedContents`；API key 使用 `x-goog-api-key` header）。
- `custom`：自定义 HTTP provider（当前按 OpenAI-compatible embeddings 处理）。
- `local_proxy`：本地代理/网关（当前按 OpenAI-compatible embeddings 处理）。
- `sentence_transformers`：本地 sentence-transformers（可选依赖；未安装依赖时会被判定为不可用；模型会缓存到本地目录）。

## Env 变量（默认值）

后端 `backend/app/core/config.py` 提供的默认配置：

- `VECTOR_EMBEDDING_PROVIDER`：`openai_compatible | azure_openai | google | custom | local_proxy | sentence_transformers`
- `VECTOR_EMBEDDING_BASE_URL`
- `VECTOR_EMBEDDING_MODEL`
- `VECTOR_EMBEDDING_API_KEY`
- `VECTOR_EMBEDDING_AZURE_DEPLOYMENT`
- `VECTOR_EMBEDDING_AZURE_API_VERSION`
- `VECTOR_EMBEDDING_SENTENCE_TRANSFORMERS_MODEL`
- `VECTOR_EMBEDDING_SENTENCE_TRANSFORMERS_CACHE_DIR`
- `VECTOR_EMBEDDING_SENTENCE_TRANSFORMERS_DEVICE`

## 本地模型部署体积与风险（sentence-transformers）

- 依赖体积：`sentence-transformers` 通常会拉入 `torch/transformers` 等依赖，安装包体积与运行内存占用明显增加。
- 模型体积：首次使用可能触发下载（或从本地路径加载），建议提前在部署环境准备好模型文件并设置缓存目录，避免运行时下载失败导致降级。
- 资源风险：低配 CPU 环境推理速度较慢；如需 GPU 请显式配置 device，但必须确保 CUDA/驱动环境可用（否则会自动回退到 CPU）。

## 加密与安全

- `api_key` 写入时会通过 `backend/app/core/secrets.py` 加密后存入数据库。
- `APP_ENV=prod` 时必须配置 `SECRET_ENCRYPTION_KEY`（Fernet key），否则无法写入/读取加密密钥。
- `APP_ENV=dev` 且在 Windows 上允许使用 DPAPI（`dpapi:` 前缀）作为本地单机便捷方案；生产环境不允许 DPAPI。

安全红线：

- 任意 API 响应/日志/导出都不得包含明文 key；仅允许 `has_api_key` / `masked_api_key`。
- 对外部 embedding 服务的调用必须可降级：配置缺失/依赖缺失/上游不可用时返回稳定的 `disabled_reason`，不得阻塞写作流程。

## UI / API 入口

- 前端：`/projects/:id/settings` 页面新增「向量检索（Vector RAG）」配置区。
- 后端：`GET/PUT /api/projects/{project_id}/settings` 会返回并更新向量配置相关字段（不返回明文 key）。
