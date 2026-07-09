# Trajectory Statistics And Non-Adjacent Rollback Records

Generated / maintained on: 2026-06-26

本目录保存基于项目轨迹文件重新统计出的结果。统计过程不使用 `results/summary.json` 或 `results/results.jsonl`，因为这些文件可能被覆盖；所有结论都从对应项目 run 目录里的 `manifest.json`、`context.json`、`blocks/*.json`、`executions.jsonl` 和 `logs/` 推导。

## Canonical Master Tables

非相邻回溯的总表入口是：

- `non_adjacent_rollback_master.csv`: edge/event 级总表，35 条记录。
- `non_adjacent_rollback_master_runs.csv`: run 级总表，32 个唯一 run。
- `non_adjacent_rollback_combined_summary.csv`: 总表摘要。

`non_adjacent_rollback_master.csv` 合并两种来源：

- `final_blocks_baseline_checkpoint_graph`: 从最终 `blocks/*.json` 的 `baseline_checkpoint` 关系中发现的非相邻依赖，16 条。
- `executions_jsonl_runtime_timeline`: 从 `executions.jsonl` 真实执行时间线中发现、但最终 checkpoint graph 没捕捉到的运行时非相邻回跳，19 条。

总表中的重复项目/重复事件按记录计数。例如同一个 run 内发生两次 runtime backjump，会保留两条 event 级记录；run 级去重请看 `non_adjacent_rollback_master_runs.csv`。

## Source Directories

标准 run 目录按如下规则读取：

```text
<source_dir>/state/<project_slug>/<repo_dir_name>/runs/<run_id>/
```

`projects-repo2run` 按如下规则读取：

```text
projects-repo2run/<project_slug>/.pheragent/runs/<run_id>/
```

本轮索引的 source directories：

```text
executionagent-runs-gpt4o
executionagent-runs-gpt54
installamatic-runs
installamatic-runs-rerun-failures-2
installamatic-runs-rerun-failures-3
setupbench-runs-all-gpt-5.4-multiblock
setupbench-runs-all-gpt-4.1-2rerun
setupbench-runs-all-gpt-4.1
projects-repo2run
```

共索引 476 个 trajectory run。

## Collection Process

1. 生成 run inventory。

   从每个项目 run 目录读取 `manifest.json`、`context.json`、`blocks/*.json` 和 `executions.jsonl`，生成：

   - `all_trajectory_runs.csv`: 476 个 run 的总清单。
   - `not_one_shot_cases.csv` / `trajectory_not_one_shot_cases.csv`: trajectory 级非 one-shot 案例。
   - `project_attempt_not_one_shot_cases.csv`: 只按最终失败或外层 project retry 判断的更严格案例。

2. 统计 not-one-shot。

   主口径 `not_one_shot_trajectory=True` 的条件是：最终 manifest 非 ok，或外层 project attempt count 大于 1，或任一 block 有内部 repair。

   次级口径 `not_one_shot_project_attempt=True` 忽略 block 内部 repair，只看最终失败/未完成或外层 project retry。

3. 用最终 checkpoint graph 分析 rollback adjacency。

   输入是 `project_attempt_not_one_shot_cases.csv` 的 202 条。对每条 case：

   - 读取 `run_dir/blocks/*.json`。
   - 按 block 的 `order` 排序。
   - 解析每个 block 的 `baseline_checkpoint`，映射到它依赖的历史 block。
   - 如果 baseline 只指向前一个 order layer，归为 `previous_block_only_rollback`。
   - 如果 baseline 指向更早的 order layer，并跳过中间 block，归为 `non_adjacent_block_rollback`。
   - 同 order 的 block 视为同一层。

   这个口径得到：

   - 202 个输入 project-attempt not-one-shot case。
   - 16 条 final checkpoint graph 非相邻记录。
   - 179 条 previous-block-only 记录。
   - 7 条 checkpoint/block 数据不足。

4. 对 final graph 非相邻案例做详细解析。

   对 `rollback_non_adjacent_cases.csv` 的 16 条逐个展开 block flow 和 `executions.jsonl` 时间线，生成 `rollback_non_adjacent_case_chronology.md` 等文件。

   复核结果：16 条输入中，15 条按 `blocks/*.json` 严格重算是真实 final graph 非相邻；`projects-repo2run/instructlab` 在原输入里被标为非相邻，但按实际 block order 是相邻承接，已在相关文件中标注为 `input_marked_non_adjacent_but_recomputed_previous_only`。

5. 补扫 `executions.jsonl` runtime 时间线。

   为捕捉 Apache Cassandra 这类“最终 checkpoint graph 已线性，但运行中确实从后面 block 跳回更早 block 修复”的情况，对 476 个 run 的 `executions.jsonl` 做补扫：

   - 连续相同 `block_id` 聚合为一个 block group。
   - 忽略 `base-image`、`container-preflight`、`oracle` 和 `clean_replay*`。
   - 用 `blocks/*.json` 的 `order` 生成 block rank。
   - 如果当前 group 的 rank 小于上一实际 block group 的 rank，并且中间隔了至少一个 block，记为 runtime 非相邻回跳。

   这个口径处理了 470 个 run；6 个 run 只有 `base-image` / `container-preflight` 或缺少 `blocks/`，没有可判断的 block 回跳。

   补扫得到：

   - 19 条 runtime 非相邻 backjump event。
   - 16 个唯一 runtime backjump run。
   - 这些 runtime backjump 均未被 final checkpoint graph 非相邻列表捕捉到。

6. 合并总表。

   将 final checkpoint graph 口径的 16 条和 runtime timeline 口径的 19 条合并，生成：

   - `non_adjacent_rollback_master.csv`: 35 条 edge/event 级总表。
   - `non_adjacent_rollback_master_runs.csv`: 32 个唯一 run。
   - `rollback_project_lists_supplemented.csv`: 便于人工检查的紧凑列表。

## Master Table Fields

`non_adjacent_rollback_master.csv` 关键字段：

- `collection_method`: 收集口径，`final_blocks_baseline_checkpoint_graph` 或 `executions_jsonl_runtime_timeline`。
- `record_kind`: 原始记录类型。
- `source_dir`, `project_slug`, `owner_repo`, `case_key`: 项目身份信息。
- `ok`, `trajectory_classification`, `project_attempt_classification`: 最终结果和 one-shot 分类。
- `run_dir`, `executions_path`: 可回溯到项目轨迹的路径。
- `edge_direction`: `baseline_checkpoint_dependency` 或 `execution_time_backjump`。
- `source_block` / `target_block`: 对 final graph 口径表示 checkpoint 依赖边；对 runtime 口径表示从后一个 block 跳回更早 block。
- `source_order`, `target_order`, `source_rank`, `target_rank`: block 顺序信息。
- `source_lines`, `target_lines`: runtime 口径下对应 `executions.jsonl` 行范围。
- `skipped_blocks`: 非相邻边跳过的中间 block。
- `failed_phases`, `hint`: 失败阶段和日志摘要。
- `edge_summary`: 便于人工阅读的边摘要。
- `notes`: 复核备注，例如 `missed_by_final_checkpoint_graph`。

## Current Combined Counts

```text
final_checkpoint_graph_non_adjacent_records_original: 16
runtime_execution_non_adjacent_backjump_events_added: 19
runtime_execution_non_adjacent_backjump_runs_added: 16
combined_non_adjacent_records: 35
combined_unique_runs: 32
combined_final_ok_records: 22
combined_final_failed_records: 13
```

Runtime additions by source:

```text
executionagent-runs-gpt4o: 7 events / 6 runs
installamatic-runs: 2 events / 2 runs
setupbench-runs-all-gpt-5.4-multiblock: 2 events / 2 runs
projects-repo2run: 8 events / 6 runs
```

## File Index

Inventory and not-one-shot:

- `all_trajectory_runs.csv`: 全部 476 个 trajectory run。
- `by_directory_summary.csv`: 各 source directory 的聚合统计。
- `not_one_shot_cases.csv` / `.json`: trajectory 级 not-one-shot case。
- `trajectory_not_one_shot_cases.csv` / `.json`: 与 `not_one_shot_cases` 相同，显式命名。
- `project_attempt_not_one_shot_cases.csv` / `.json`: 只按最终失败/外层 retry 的严格口径。
- `duplicate_case_counts.csv`: 重复 project/commit 统计。
- `missing_manifest_runs.csv`: 有轨迹目录但没有 manifest 的 run。
- `scan_sources.csv`: source kind 和解析到的 run 数量。

Final checkpoint graph rollback analysis:

- `rollback_analysis.md`: final graph rollback adjacency 分析说明。
- `rollback_analysis_by_case.csv`: 202 条 project-attempt case 的 rollback 分类。
- `rollback_analysis_summary.csv`: final graph 口径聚合统计。
- `rollback_non_adjacent_cases.csv`: final graph 非相邻输入列表，16 条。
- `rollback_previous_only_cases.csv`: 只回到前一 block layer 的 case。
- `rollback_no_prior_block_cases.csv`: checkpoint/block 数据不足或无 prior block 的 case。
- `rollback_project_lists.csv`: final graph 口径 compact project list。

Final graph non-adjacent details:

- `rollback_non_adjacent_case_chronology.md`: 16 条 final graph 非相邻 case 的时间线解析。
- `rollback_non_adjacent_case_chronology_summary.csv`: 上述解析的汇总。
- `rollback_non_adjacent_block_flow.csv`: block flow 明细。
- `rollback_non_adjacent_block_segments.csv`: 按 `executions.jsonl` 行序聚合的 block segment。
- `rollback_non_adjacent_event_timeline.csv`: event 级时间线。
- `rollback_non_adjacent_detailed.md`: 详细 Markdown 版。
- `rollback_non_adjacent_success_failure_trajectories.csv` / `.md`: 成功/失败分组。

Runtime backjump supplement:

- `runtime_non_adjacent_backjumps.csv`: runtime 非相邻 backjump event，19 条。
- `runtime_non_adjacent_backjump_runs.csv`: runtime backjump run 级汇总，16 个 run。
- `runtime_non_adjacent_backjumps_missed_by_final_graph.csv`: final graph 未捕捉到的 runtime event。
- `runtime_backjump_analysis_summary.csv`: runtime 补扫统计。
- `runtime_non_adjacent_backjumps.md`: runtime 补扫说明和案例。
- `apache_cassandra_rollback_timeline.md`: Apache Cassandra 单独解析。
- `apache_cassandra_runtime_block_transitions.csv`: Apache Cassandra runtime transition 明细。

Combined / master records:

- `non_adjacent_rollback_master.csv`: canonical edge/event 级总表。
- `non_adjacent_rollback_master_runs.csv`: canonical run 级总表。
- `non_adjacent_rollback_records_combined.csv`: master 表的来源合并记录。
- `non_adjacent_rollback_runs_combined.csv`: run 级来源合并记录。
- `non_adjacent_rollback_combined_summary.csv`: 合并统计摘要。
- `non_adjacent_rollback_records_combined.md`: 合并口径说明。
- `rollback_project_lists_supplemented.csv`: 合并口径 compact project list。
