# 跨实现差分测试（Python ↔ TypeScript）

## 目的
「算法统一」的自动化保证：同一语料在 smart-sentence-splitter（Python）与
Multi-Publish story2video-engine（TypeScript）上输出**逐字/逐字段一致**（blocks + starts + durs）。

当前语料：`corpus.json`（38 例 = 20 个共享向量 + 边界/舍入探针，含 .xx5 half-up 舍入锁定）。

## 运行

```bash
# 1) Python 侧（splitter 仓库内）
python scripts/cross-parity/run_python.py scripts/cross-parity/corpus.json /tmp/out_py.json

# 2) TS 侧（在 Multi-Publish packages/story2video-engine 目录内，用绝对路径指向语料/输出）
npm exec --yes --package=tsx -- tsx D:/Data/projects/smart-sentence-splitter/scripts/cross-parity/run_typescript.ts D:/Data/projects/smart-sentence-splitter/scripts/cross-parity/corpus.json /tmp/out_ts.json

# 3) 对比（0 退出码 = 完全一致）
python scripts/cross-parity/compare.py /tmp/out_py.json /tmp/out_ts.json
```

## 维护纪律
- 新增/修改分割规则时，必须同步扩充 `corpus.json` 并重跑差分；
- 时间戳断言使用 half-up 舍入（见规范 §7），禁止 Python 原生 round()；
- 任何字段不一致即失败——不一致 = 双实现漂移，禁止静默放行。
