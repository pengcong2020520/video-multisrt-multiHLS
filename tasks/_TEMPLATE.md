# 模块任务卡 · {{MODULE_NAME}}

> 阶段③ 分配给单个模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（契约，不可改） · 项目记忆 `memory/{{PROJECT_NAME}}.md`

## 归属
- 模块：{{MODULE_NAME}}
- 负责 Agent：module-developer / frontend-developer / ui-designer
- 代码目录：`src/modules/{{MODULE_NAME}}/`

## 任务范围
- 要实现的功能（对应 Spec §2 的模块定义）：
- **边界**：只动本模块目录；与外部仅通过 Spec §4 接口交互。

## 输入
- 依赖的接口（来自哪些模块）：
- 依赖的数据表（Spec §3）：

## 产出
- 代码 + 单元测试
- 本模块对外提供的接口实现（须符合 Spec §4 契约）

## 验收标准
- [ ] 符合 Spec §5 开发规范（lint / 测试 / 提交）
- [ ] 单测通过，覆盖核心逻辑
- [ ] 对外接口与契约一致（字段/错误码）
- [ ] 不越界修改其他模块
- [ ] 已更新项目记忆中的模块状态

## 备注
-
