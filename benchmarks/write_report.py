"""Derive the measurement report from retained measurements."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/results'
s=json.loads((OUT/'summary.json').read_text())
h=json.loads((OUT/'http-results.json').read_text())
i=json.loads((OUT/'index-results.json').read_text())
f=json.loads((OUT/'frontend-results.json').read_text())
e=json.loads((OUT/'environment.json').read_text())
assert all(s[n]['errors']==0 and s[n]['requests']==3000 for n in ('baseline','optimized','cached'))
assert sum(int(t['tests']) for t in e['java_tests'])==18
assert all(t['failures']=='0' and t['errors']=='0' and t['skipped']=='0' for t in e['java_tests'])
b=s['baseline']['median_round_p95_ms'];o=s['optimized']['median_round_p95_ms'];c=s['cached']['median_round_p95_ms']
ix=i['existing_cart_item'];before=ix['without']['median_execution_ms'];after=ix['with']['median_execution_ms']
mb_before=f['baseline']['bytes']/1e6;mb_after=f['optimized']['bytes']/1e6
round_table='\n'.join('| '+str(trial)+' | '+' | '.join(f'{next(r for r in h if r["name"]==name and r["trial"]==trial)["p95_ms"]:.3f}' for name in ['baseline','optimized','cached'])+' |' for trial in [1,2,3])
index_table='\n'.join(f'| {label} | {v["without"]["median_execution_ms"]:.4f} | {v["with"]["median_execution_ms"]:.4f} | 90 / 90 |' for label,v in i.items())
report=f'''# OnlineOrder 本地优化与实测结果

已完成购物车批量读取、查询索引、菜单复用、并发写入保护与真实数据库测试。全部性能数字来自本次合成数据测试，不能解释为线上用户规模或生产 SLA。

## 核心结果

| 测量项 | 优化前 | 优化后 | 范围 |
| --- | ---: | ---: | --- |
| 购物车接口每次业务 SQL | 53 | 4 | 50 条明细，均关闭缓存，索引相同 |
| 购物车接口 P95 | {b:.3f} ms | {o:.3f} ms | 20 并发客户端，三轮 P95 的中位数 |
| 开启热缓存后的每次业务 SQL | 4 | 1 | 相同优化版 JAR；仍包含用户查询 |
| 开启热缓存后的 P95 | {o:.3f} ms | {c:.3f} ms | 100 用户，20 并发，纯读取、已预热 |
| 指定购物车商品 SQL 执行耗时中位数 | {before:.4f} ms | {after:.4f} ms | 105,000 条明细，90 次/配置 |
| 浏览 10 家餐厅的菜单 API 请求数 | 11 | 1 | 实际 React 组件与真实 HTTP 接口 |
| 上述流程未压缩 JSON 响应体 | {f['baseline']['bytes']:,} 字节 | {f['optimized']['bytes']:,} 字节 | 不含图片、HTTP 头及登录请求 |
| PostgreSQL 集成测试 | 原先没有 | 14 个场景通过 | 另有原有 4 个单元测试通过 |

购物车批量读取的 P95 降幅为 {s['batch_p95_reduction_pct']:.2f}%；热缓存 SQL 数量降幅为 {s['cache_sql_reduction_pct']:.2f}%，P95 降幅为 {s['cache_p95_reduction_pct']:.2f}%。这些值分别来自独立的版本对比和缓存开关对比，不可相加。前端少传输 {s['frontend_bytes_saved']:,} 字节（{s['frontend_bytes_reduction_pct']:.2f}%）；首次完整目录的大小没有变化。

## 数据与环境

- 100 家餐厅、10,000 个菜品、10,100 个测试用户和购物车、105,000 条购物车明细。
- 参与 HTTP 测试的是前 100 个用户，每人的购物车有 50 条明细；这些账号不代表真实用户。
- 主机 {e['hardware_model']}，{e['architecture']}，{e['logical_cpus']} 个逻辑 CPU，{e['memory_bytes']//(1024**3)} GiB 内存。
- Java 21、Spring Boot 4.0.5、PostgreSQL 15.2（Docker，arm64）。每个应用使用 2 个 JVM 活跃处理器、256–512 MiB 堆、20 个数据库连接；数据库限制为 2 CPU、2 GiB 内存。
- 基线只修正实体导入、认证 SQL 列名和开发数据自动注入开关。优化版另外改用了 BigDecimal，因此端到端耗时比较是这两份记录版本的比较；缓存开关比较则使用完全相同的优化版 JAR。
- 基线源码保留在 `baseline-source/`；环境、镜像、JAR 指纹及修改差异保存在 results 目录。
- 环境记录时间：{e['recorded_at_utc']}。

## HTTP 原始轮次

每种配置每轮 1,000 个正式请求，共三轮；每种配置合计 3,000 个正式请求，三种配置共 9,000 个，全部响应状态与内容校验通过，错误数为 0。预热请求不计入正式样本。配置执行顺序轮换，测试期间未并行运行构建或其他压测。P95 使用 nearest-rank 算法；最终简历值取三轮 P95 的中位数。

| 轮次 | 基线 P95 ms | 批量读取 P95 ms | 热缓存 P95 ms |
| --- | ---: | ---: | ---: |
{round_table}

三轮 SQL 总次数分别为 159,000、12,000、3,000，来自 PostgreSQL pg_stat_statements。基线服务层 52 次查询加 1 次用户查询，优化后服务层 3 次加 1 次用户查询；命中购物车缓存后只有用户查询。餐厅菜单聚合接口也实际验证为 2 次 SQL，返回 100 家餐厅及 10,000 个菜品。

热缓存测试不包含写入、TTL 过期与冷启动，因此没有宣称混合负载的命中率，也不能据此推导生产吞吐上限。

## 索引测量

在独立索引数据库中对比索引存在与不存在。每个查询每种配置三轮、每轮 30 次正式测量，另有 10 次预热；两个状态交替顺序。每个查询每种配置共 90 个样本，合计保存 540 份 EXPLAIN ANALYZE JSON 计划。计时关闭逐节点仪表，使用服务器 Execution Time；不含计划时间、HTTP 与网络往返。

| 查询 | 无索引中位数 ms | 有索引中位数 ms | 两组样本数 |
| --- | ---: | ---: | ---: |
{index_table}

索引为 menu_items(restaurant_id) 和 order_items(cart_id, menu_item_id)。后者是唯一索引，同时约束同一购物车内同一菜品只出现一条明细。缓冲区经过预热；特别小的耗时是单条 SQL 的服务器执行时间，不是接口响应时间。

## 正确性与前端验证

14 个真实数据库集成场景全部通过：新增、数量累加、精确小数、清空、4 种写入故障回滚、注册完整性、按用户缓存失效，以及 8/16/32 线程同商品并发和 32 线程不同商品并发。每线程加购 10 次，最高单场景 320 次操作；验证明细数量、金额合计及无重复行。并未据此宣称并发读写缓存具有线性一致性。

原有 4 个单元测试通过；前端 1 个对照测试通过，并成功生成生产构建。前端测试运行实际组件、真实菜单 API，替换 Ant Design 展示控件；每次选餐厅后检查 100 个菜品及对应首尾菜品名称。未测浏览器首屏、图片加载、压缩传输量或开发模式的额外挂载。

## 证据与复现

- `results/http-results.json` 与 9 份逐请求 CSV：HTTP 时延与 SQL 调用记录。
- `results/index-results.json`、`results/index-plans.json`：索引结果与全部原始计划。
- `results/frontend-results.json`：每条菜单请求及响应字节数。
- `results/optimized-java-tests/`、`results/baseline-unit-tests/`：JUnit 原始 XML。
- `results/environment.json`、`results/implementation-changes.diff`：环境及代码修改。
- `README.md`、`seed.sql`、测试及测量脚本：完整复现流程。
'''
(ROOT/'benchmarks/REPORT.md').write_text(report)
print('Wrote REPORT.md.')
