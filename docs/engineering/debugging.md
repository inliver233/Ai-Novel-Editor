# Debugging Guide（调试指南）

目标：提供一套**可复制执行**的调试入口，快速定位启动失败、UI 卡死、线程/任务取消异常、导入导出异常等问题。

## 1) 最小启动排查

1. 确认解释器与依赖（建议 Python 3.11）：

```powershell
py -3.11 -V
py -3.11 -m pip install -r requirements.txt
```

2. 静态编译检查：

```powershell
py -3.11 -m compileall -q src
```

3. 启动应用：

```powershell
py -3.11 src\main.py
```

## 2) 打开更详细的错误信息

### 2.1 Python 运行时诊断

启用 faulthandler（崩溃/卡死时更容易拿到堆栈）：

```powershell
$env:PYTHONFAULTHANDLER = \"1\"
py -3.11 src\main.py
```

启用开发模式（更严格的运行时告警）：

```powershell
py -3.11 -X dev src\main.py
```

### 2.2 Qt 插件/平台问题（启动即退出/找不到 platform plugin）

打印 Qt 插件加载信息（输出会很长，仅在定位此类问题时启用）：

```powershell
$env:QT_DEBUG_PLUGINS = \"1\"
py -3.11 src\main.py
```

## 3) 日志

日志原则与输出位置见：
- `docs/engineering/logging.md`

常用做法：
- 把 `app.log_level` 调到 `DEBUG`，重现后查看 `app.log`。
- 对长链路（导入/索引/导出/AI 请求）用统一的 task key 关联日志（见 `docs/architecture/tasks.md`）。

## 4) 测试作为调试入口

基础入口：

```powershell
py -3.11 -m unittest discover tests
py -3.11 -m pytest -q
```

针对单文件快速跑：

```powershell
py -3.11 -m pytest -q tests\test_config_schema_migration.py
```

## 5) 常见问题定位建议

### 5.1 UI 卡死/无响应

- 优先检查：是否把 IO/网络/索引/embedding 放在 UI 线程执行。
- 统一通过 TaskManager/调度器编排后台任务（见 `docs/architecture/tasks.md`）。
- 必要时临时加大日志粒度（DEBUG）并记录 task key 的生命周期（started/finished/failed/cancelled）。

### 5.2 取消后仍继续写 DB/UI

- 取消必须是协作式：任何副作用（写 DB/写 UI）前必须再次检查取消状态。
- 对长任务：每批处理后检查取消，并保证阻塞调用有超时。

### 5.3 导入/导出失败

- 先用最小样例复现（小文件、单文档、无外部依赖）。
- 保留复现输入与输出文件路径，便于写入 Issue 的 `Notes.evidence`。

