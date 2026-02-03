# Top 10 必不破坏工作流（手工回归清单）

> 目标：在重构期间，确保用户核心写作体验不回归。  
> 使用方式：按本文逐条执行，每条都要留下证据（截图/日志/输出）。

## 运行前准备
- 需要 1 个可用项目（包含 `project.db` / `vectors.db`，或应用当前实现使用的数据文件）。
- 建议开启日志输出（如有），并记录测试日期与环境信息。

## 证据规范（最小要求）
- 每条工作流至少提供一种证据：
  - 截图（界面关键状态）
  - 日志片段（关键操作完成/异常为空）
  - 导出文件/输出（如导出/备份/恢复等）

## Top 10 工作流列表（待细化）

1. **项目：创建/打开项目**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

2. **写作：打开文档并编辑/保存**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

3. **写作：大纲面板（解析/刷新/跳转）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

4. **AI：基础对话/补全（可用性与不阻塞 UI）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

5. **Codex：打开/运行一次核心流程（不崩溃/不丢状态）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

6. **RAG：建立索引/检索一次（或使用现有索引）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

7. **导入：导入文档/项目（含失败保护）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

8. **导出：导出文档（格式/内容一致性）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

9. **查找替换：基本查找/替换（含边界条件）**
   - Steps: TODO
   - Expected: TODO
   - Evidence: TODO

10. **主题/设置：切换主题或关键设置后重启仍生效**
    - Steps: TODO
    - Expected: TODO
    - Evidence: TODO

