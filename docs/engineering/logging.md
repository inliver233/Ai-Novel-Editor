# Logging

## 原则
- 生产路径禁止使用内建 `print()`（避免污染 stdout / 影响调用方/测试/日志采集）。
- 统一使用 `logging`（由 `src/core/log.py` 的 loguru 拦截器汇总输出）。

## 日志级别（可配置）
- 配置键：`app.log_level`
- 默认值：`INFO`
- 取值建议：`INFO` / `DEBUG`（大小写不敏感）

实现入口：
- `src/core/config.py`：默认配置补齐 `app.log_level`
- `src/main.py`：`setup_logging(config)` 从配置读取并传给 `core.log.configure_logging(...)`

## 输出位置
- 控制台：loguru 输出到 stdout
- 文件：`~/.ai-novel-editor/logs/app.log`

## 回归保护（测试）
- 禁止关键生产文件出现 builtin `print()`：`tests/test_no_builtin_prints_production.py`
- 日志级别配置覆盖：`tests/test_log_level_config.py`

运行示例：
- `py -3.11 -m compileall -q src`
- `py -3.11 -m pytest -q tests/test_no_builtin_prints_production.py tests/test_log_level_config.py`
