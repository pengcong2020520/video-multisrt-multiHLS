> 本项目文档由用户提供，存放于 `~/多语种多音轨外切/`。以下为原文索引。


# 多语种多音轨外切平台 MVP 文档索引

本文档包面向内部运营使用的「AI 真人/真人短剧视频翻译与多语种音轨外切平台」MVP。

## 文档清单

- [BRD.md](./BRD.md)：业务需求文档，说明业务目标、用户、收益、范围和里程碑。
- [PRD.md](./PRD.md)：产品需求文档，说明页面、流程、功能、交互、状态和验收标准。
- [ARCHITECTURE.md](./ARCHITECTURE.md)：产品与技术架构文档，说明模块划分、处理管线、模型选型和部署建议。
- [AGENT_SKILL_ARCHITECTURE.md](./AGENT_SKILL_ARCHITECTURE.md)：Agent + Skill 编排设计，说明 Agent Runtime、Skill 目录、编排模板和人机协同边界。
- [TECH_SPEC.md](./TECH_SPEC.md)：最小技术规格文档，定义核心数据结构、接口、任务状态机、边界和非目标。

## MVP 一句话定义

上传 1-3 分钟无字幕中文/英文短剧视频，通过 Web 前端触发 Agent Runtime，编排媒体、ASR、翻译、TTS、混音和打包 Skill，生成多语种外挂字幕和多语种替换人声音轨，并在网页中支持视频预览、字幕切换、音轨切换和结果下载。

## 第一版明确不做

- 不做面向 C 端创作者的开放平台。
- 不承诺唇形级口型同步。
- 不承诺多人重叠对白的完美分离和识别。
- 不承诺完全自动成片，必须保留人工校对入口。
- 不做完整视频剪辑工作台、素材库、版权交易、发布分发系统。
- 不把 ASR、翻译、TTS、声源分离绑定到单一模型，所有模型能力通过适配层接入。
- 不让 Agent 自主发布、删除、覆盖最终产物；关键动作必须受任务状态和人工确认约束。

## 推荐阅读顺序

1. 先读 [BRD.md](./BRD.md)，确认业务方向和 MVP 范围。
2. 再读 [PRD.md](./PRD.md)，确认运营人员实际如何使用。
3. 然后读 [ARCHITECTURE.md](./ARCHITECTURE.md)，确认系统如何拆模块。
4. 再读 [AGENT_SKILL_ARCHITECTURE.md](./AGENT_SKILL_ARCHITECTURE.md)，确认 Agent Runtime 和 Skill 如何复用。
5. 最后读 [TECH_SPEC.md](./TECH_SPEC.md)，作为研发接口和数据结构的第一版约束。
