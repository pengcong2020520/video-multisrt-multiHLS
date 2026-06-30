/**
 * @video-multisrt/shared-types
 *
 * 全仓共享契约基线，覆盖 Spec §3-§13。
 * 不导入 apps/* 或其他 packages/* 的业务实现；只导出类型、Schema、枚举、常量与纯函数。
 */
// §3 语言代码
export * from './languages.js'
// §5 状态枚举 + §4.2/§4.8/§7 衍生枚举
export * from './enums.js'
// §12 错误码
export * from './errors.js'
// 公共类型
export * from './common.js'
// §4 核心实体 + 支撑表
export * from './entities.js'
// §6 Skill 调用契约
export * from './skill-contract.js'
// Skill-specific 输入输出
export * from './skill-io.js'
// §11 Adapter 类型
export * from './adapters.js'
// §7 API DTO
export * from './api-dto.js'
// §8 文件路径纯函数
export * from './paths.js'
