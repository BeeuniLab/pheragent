# Rollback Adjacency Analysis

Generated at: 2026-06-26T12:58:35.239476+00:00

Input: `statistic/project_attempt_not_one_shot_cases.csv`.

Method: for each case, parse `run_dir/blocks/*.json`; sort blocks by `order`; resolve each `baseline_checkpoint` to the block whose checkpoint name references that block id. A rollback is `previous_block_only_rollback` when every resolved prior-block baseline points to the immediately previous order layer. It is `non_adjacent_block_rollback` when at least one baseline points to an older order layer, skipping one or more intervening blocks. Blocks with the same order are treated as the same layer.

## Totals

- Total input cases: 202
- Non-adjacent block rollback: 16
- Previous-block-only rollback: 179
- No prior-block rollback detected: 0
- Insufficient checkpoint/block data: 7
- Total non-adjacent rollback edges: 16
- Total adjacent rollback edges: 542

## Runtime Timeline Supplement

The totals above are based on the final `blocks/*.json` baseline checkpoint graph. A separate pass scanned `executions.jsonl` in all 476 indexed runs and found 19 additional runtime non-adjacent backjump events across 16 runs. These events are not visible in the final checkpoint graph because later successful repairs can make the final graph linear.

- Runtime non-adjacent backjump events added: 19
- Runtime non-adjacent backjump runs added: 16
- Combined non-adjacent records: 35
- Combined unique runs: 32
- Runtime additions by source: `executionagent-runs-gpt4o` 7 events, `installamatic-runs` 2, `setupbench-runs-all-gpt-5.4-multiblock` 2, `projects-repo2run` 8

## By Source Directory

| source_dir | total | non_adjacent | previous_only | no_prior | insufficient |
|---|---:|---:|---:|---:|---:|
| executionagent-runs-gpt4o | 12 | 2 | 10 | 0 | 0 |
| executionagent-runs-gpt54 | 25 | 13 | 12 | 0 | 0 |
| installamatic-runs | 20 | 0 | 20 | 0 | 0 |
| installamatic-runs-rerun-failures-2 | 12 | 0 | 12 | 0 | 0 |
| installamatic-runs-rerun-failures-3 | 10 | 0 | 10 | 0 | 0 |
| projects-repo2run | 70 | 1 | 68 | 0 | 1 |
| setupbench-runs-all-gpt-4.1 | 26 | 0 | 23 | 0 | 3 |
| setupbench-runs-all-gpt-4.1-2rerun | 21 | 0 | 18 | 0 | 3 |
| setupbench-runs-all-gpt-5.4-multiblock | 6 | 0 | 6 | 0 | 0 |

## Files

- `rollback_analysis_by_case.csv`: all 202 input cases with rollback-edge classification.
- `rollback_non_adjacent_cases.csv`: cases that rollback to a non-adjacent block.
- `rollback_previous_only_cases.csv`: cases whose resolved rollback edges only target the previous order layer.
- `rollback_no_prior_block_cases.csv`: cases without a resolved prior-block rollback edge or with insufficient checkpoint data.
- `rollback_analysis_summary.csv`: aggregate counts overall, by source directory, and by original project-attempt classification.
- `rollback_project_lists.csv`: compact project list for inspection.
- `runtime_non_adjacent_backjumps.csv`: non-adjacent runtime backjump events found from `executions.jsonl`.
- `runtime_non_adjacent_backjump_runs.csv`: runtime backjump events collapsed to unique runs.
- `non_adjacent_rollback_records_combined.csv`: original final checkpoint graph records plus runtime timeline backjump records.
- `non_adjacent_rollback_runs_combined.csv`: combined run-level view for final graph and runtime timeline records.
- `non_adjacent_rollback_combined_summary.csv`: aggregate counts for the combined record set.
