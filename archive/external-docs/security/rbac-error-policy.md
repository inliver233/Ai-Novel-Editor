# RBAC Error Semantics Policy（403 vs 404）

目标：在“跨项目资源访问”场景下，减少通过状态码区分资源是否存在所带来的**资源存在性泄露**风险。

## 总体原则

- 未登录：返回 `401 UNAUTHORIZED`
- 已登录但**完全不具备该项目的任何访问权**（非 owner / 非成员）：返回 `404 NOT_FOUND`
- 已登录且是项目成员，但**角色不满足最小权限**（例如 viewer 访问 editor-only）：返回 `403 FORBIDDEN`

> 直观理解：只有当用户已经“知道项目存在”（因为他是成员）时，才返回 403；否则统一 404。

## 适用范围

适用于所有以 `project_id` 为边界的资源（包括但不限于）：
- `/projects/{project_id}` 及其子资源
- 通过子资源间接定位到项目的接口（chapter/outline/character/worldbook 等），最终都会落到项目 RBAC 校验

不适用于：
- 不带项目边界的全局资源列表（例如 `/projects` 列表本身）
- 明确属于“用户自有资源”的接口（例如 llm_profile 按 owner fail-closed，本身已采用 404 语义）

## 实现约定（代码）

后端统一通过 `backend/app/api/deps.py` 的 `require_project_access` 族函数执行：
- 项目不存在：`AppError.not_found()`（404）
- 项目存在但用户不是成员：`AppError.not_found()`（404）
- 项目存在且用户是成员但角色不足：`AppError.forbidden()`（403）

## 契约测试

`test/specs/api/auth-rbac.contract.spec.ts` 覆盖非成员跨项目访问：
- 读取项目 `/projects/{project_id}` → 404
- 读取项目子资源（例如 `/projects/{project_id}/llm_preset`）→ 404
- 修改项目（例如 `PUT /projects/{project_id}`）→ 404

