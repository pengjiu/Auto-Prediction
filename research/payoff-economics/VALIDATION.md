# P0 开发验证及提交接续记录

日期：2026-10-11。基线：`pengjiu/Auto-Prediction@d6c9447cab29898a6eb5fa06be3598b8474cc02f`。
开发分支：`codex/mutation-payoff-economics`。设计先行提交：`e7ffd40cfde0d5fb39500231d2e7bd114716260b`。

## 本地完整验收（2026-10-11）

在固定分支 `codex/mutation-payoff-economics` 上，将 GitHub Actions 按 `pnpm-lock.yaml` 生成的 Node 22.22.1、pnpm 11.13.1 和完整安装依赖打包恢复到本地容器后，**实际在本地进程中**运行以下检查：

| 检查 | 本地结果 |
|---|---|
| `pnpm run check` | 20 个 workspace 的 TypeScript 检查通过 |
| `pnpm run build` | 19 个工作区包及 Studio 完整构建通过；Vite 仅有包体积提示 |
| `pnpm run test` | 28 项根级测试 + 1,049 项 workspace 测试，共 **1,077 通过、0 失败**，最终退出码 0 |
| P0 原生回归 | 43 通过、0 失败 |
| 补丁应用工具 | 8 通过、0 失败 |
| 定向检查 | `premise-analysis.test.ts` + `server.test.ts` 共 44 通过、0 失败 |

**发现并修复的测试问题（严格按先失败、后修复、再完整复跑执行）：**

1. `scripts/studio-harness-smoke.test.mjs` 的清理函数只终止 detached pnpm 组内的父进程，导致 Studio 子进程孤儿化、端口不释放。现在对 POSIX 独立进程组发送 SIGTERM，并保留 Windows 分支。测试由端口泄漏失败转为 28 项根级测试全部通过。
2. 同一测试直接对比含 ANSI 颜色码的 Vite 输出，可能把真实端口误判为缺失。测试断言先去掉 VT 控制码再比较。
3. `premise-analysis.test.ts` 中两处 `portfolios.length === 1` 是不安全子集剪枝时代的旧期望；新模型输出 3 份正支付篮子。修改为检查全部保留的三个候选及正支付下界，不恢复旧剪枝。
4. `server.test.ts` 隐含依赖本机 Codex 凭证缓存；干净环境合法阻断为 `credential unavailable`。现在仅允许该原因或 `preflight`，并仍要求 `dispatchEligibility: BLOCKED`，未注入任何真实凭证。

以上属于**本地集成/单元/构建验收**，不证明现时市场的净盈利、真实多腿原子性、未模拟的撮合费用或当前 SDK 与匿名实时 API 的兼容性。无真实订单、签名、授权、资金移动。GitHub Actions 的源代码归档仅用于跨网络限制交付完整依赖，测试主体在本地执行。

## 初始 P0 聚焦检查（提交前）

| 检查 | 结果 | 范围 |
|---|---|---|
| 聚焦 TypeScript 严格类型检查 | 通过 | 新预算模块、相同测试体、原 fixed/identity/types/verifier 子集；TS 5.8.3 |
| 原生 Node 测试 | 43 通过、0 失败；本次提交前重跑通过 | 新预算模块、原验证器联测、生产选择表达式与旧最小化限制的隔离回归 |
| 结构化覆盖 | 1,294 个状态集合 | 全部非空 2/3 合约布尔状态子集，另加 1,024 个四合约子集；不是现实合约语义 |
| 预算性质检查 | 1,000 个确定性盘口 | 限价覆盖、取整、费用单调性、成本上界 |
| 一致价格检查 | 200 个概率模型 | exactly-one 有限模型，明确检查非空遍历，非市场回测 |
| 补丁应用工具单元测试 | 8 通过、0 失败；本次提交前重跑通过 | 基线不符、覆盖、非唯一锚点、路径逃逸、符号链接、并发修改等 |
| 上游源码完整性 | 4 文件匹配 Git blob SHA | fixed.ts / identity.ts / types.ts / verifier.ts |

## 关键回归

### 三份 NO 不能仅因存在两份 NO 子集就被剪枝

虚构模型：A/B/C 恰好一个成立；每份 NO 成本 0.60。原选择表达式删除三 NO 组合；新表达式保留。原固定点验证器计算最低支付 2、成本 1.8，零手续费测试条件下净下界 0.2。第二处 subset-minimality 拒绝也删除，其他支付、身份和权限核验保留。这不是当前市场的盈利证据。

### VWAP 不能代替完整成交限价

50 份 0.40 和 50 份 0.60：VWAP 0.50，限价覆盖需要 0.60，100 份保守名义支出 60 而非 50。加另一条每份 0.45 的互补腿时，旧均价模型有 5 的净下界，新限价模型被原验证器拒绝；另一腿降至 0.30 时，保守组合仍保留 10 的净下界。所有价格均为虚构测试值。

### 不放松费用、状态与身份边界

曲线费用仍不能进入当前聚合费用认证。逐档取整超过单笔上界、超限价、超预算、数量比例变化、SELL 混入 BUY、空状态、缺失支付和失效身份均被拒绝。历史模拟回放检查不等于真实订单成交证明。

## 本次 GitHub 提交范围

用户重新授权后，连接器创建分支及设计提交成功，首轮 403 已不再是写入阻塞。源码通过 Git blob/tree/commit 提交，主分支不自动合并。提交前对既有源码进行了 diff 核对；传输阶段发现的两处无关文本偏差已更正，未发布为分支变更。新 helper/test 使用与本地聚焦验收文件相同的 Git blob 身份。

正式源码变更为四个既有文件及一个新增模块，另提交一个新增 Vitest 文件：

- `packages/control-plane/src/relation-payoff.ts`
- `packages/control-plane/src/exact-promotion.ts`
- `packages/execution/src/certificate-shadow.ts`
- `packages/execution/src/index.ts`
- `packages/execution/src/buy-order-budget.ts`
- `packages/execution/test/buy-order-budget.test.ts`

本目录保留原生离线测试、源码替换记录、基线验证器快照、补丁应用工具及其测试。编译产物、缓存、旧下载失败日志和临时压缩包不属于生产变更，没有提交。

## 仍未完成的外部与经济验收

- 本地完整工作区测试已通过；外部真实平台 API 的端到端兼容性和市场执行仍未验证。
- SDK/匿名实时 API 兼容性、连续盘口、执行延迟、真实成交概率与撮合拆分费用校准。
- 任何真实下单、签名、资金移动或盈利验证。

## 环境与复现

最初离线聚焦测试使用 Node 22.16.0、TypeScript 5.8.3，因此当时不能声称全仓通过。后续使用 Node 22.22.1、pnpm 11.13.1 和锁文件依赖恢复到本地，并独立完成完整 `check`/`test`/`build`。本地仍无法解析 GitHub/npm，依赖下载发生在隔离 GitHub Actions runner；实际测试在本地容器执行。

运行方法见 [README.md](README.md)。`evidence/validation-results.json` 为实际聚焦重跑结果；runner 的 `remote_commit` 为 `NOT_MEASURED_BY_OFFLINE_RUNNER`，防止把旧 403 或本地通过冒充远程状态。远程提交以分支和 PR 为准。每次重跑会产生完整 `evidence/native-tests.tap`。

## 选择结论

**HOLD（本地全仓静态、单元与模拟验收通过；待市场与经济性验证），不合并 main，不启用真实资金。** 本轮完成的是已授权的 P0 代码修复与严格本地测试，不是已验证盈利策略。
