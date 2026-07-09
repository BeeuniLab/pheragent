# Combined Non-Adjacent Rollback Records

Generated at: 2026-06-26T15:57:05.468587+00:00

This file supplements the original final-checkpoint rollback analysis with runtime backjumps found directly in `executions.jsonl`.

Definitions:
- `final_checkpoint_graph_non_adjacent`: non-adjacent edge detected from final `blocks/*.json` baseline checkpoints.
- `runtime_execution_backjump_non_adjacent`: execution-time control flow jumps from a later block group back to an earlier non-adjacent block group in `executions.jsonl`; `clean_replay*`, `base-image`, `container-preflight`, and `oracle` are excluded.

## Summary

- final_checkpoint_graph_non_adjacent_records_original: 16
- runtime_execution_non_adjacent_backjump_events_added: 19
- runtime_execution_non_adjacent_backjump_runs_added: 16
- combined_non_adjacent_records: 35
- combined_unique_runs: 32
- combined_unique_source_project_pairs: 32
- combined_final_ok_records: 22
- combined_final_failed_records: 13
- strict_true_final_graph_non_adjacent_records: 15
- final_graph_input_marked_but_recomputed_previous_only_records: 1

## Added Runtime Runs

- `executionagent-runs-gpt4o` / `facebook-react-native` ok=False: 21-java-runtime[4/21]->10-system-packages[2/10] skip=20-node-runtime lines=12-13->14-24 | 21-java-runtime[4/21]->10-system-packages[2/10] skip=20-node-runtime lines=60-61->62-72
- `executionagent-runs-gpt4o` / `msgpack-msgpack-c` ok=False: 20-native-build-config[3/20]->00-preflight[1/0] skip=10-system-packages lines=8-9->10-20
- `executionagent-runs-gpt4o` / `mybatis-mybatis-3` ok=True: 20-java-runtime[3/20]->00-preflight[1/0] skip=01-java-deps lines=6-7->8-18
- `executionagent-runs-gpt4o` / `python-cpython` ok=True: 30-project-dependencies[5/30]->10-system-packages[2/10] skip=20-python-runtime;20-runtime-toolchain lines=56-57->58-68
- `executionagent-runs-gpt4o` / `reactivex-rxjava` ok=True: 20-java-runtime[3/20]->00-preflight[1/0] skip=01-java-deps lines=6-7->8-10
- `executionagent-runs-gpt4o` / `spring-projects-spring-security` ok=True: 20-java-runtime[3/20]->00-preflight[1/0] skip=10-system-packages lines=6-7->8-10
- `installamatic-runs` / `nonebot-nonebot2` ok=True: 50-test-tooling[7/50]->30-python-deps[5/30] skip=31-node-deps lines=21-22->23-33
- `installamatic-runs` / `sciphi-ai-r2r` ok=False: 50-test-tooling[5/50]->20-python-runtime[3/20] skip=30-project-dependencies lines=28-29->30-40
- `projects-repo2run` / `DTrOCR` ok=True: 50-test-tooling[4/50]->00-preflight[1/0] skip=20-python-runtime;30-python-deps lines=5-6->7-9 | 50-test-tooling[4/50]->20-python-runtime[2/20] skip=30-python-deps lines=10-10->11-14
- `projects-repo2run` / `Verbiverse` ok=True: 50-test-tooling[4/50]->20-python-runtime[2/20] skip=30-python-deps lines=12-13->14-24
- `projects-repo2run` / `VideoFusion` ok=True: 30-python-deps[5/30]->20-python-runtime[3/20] skip=21-node-runtime lines=15-16->17-35 | 50-test-tooling[7/50]->10-system-packages[2/10] skip=20-python-runtime;21-node-runtime;30-python-deps;31-node-deps lines=57-58->59-92
- `projects-repo2run` / `cogvideox-factory` ok=True: 50-test-tooling[4/50]->00-preflight[1/0] skip=20-python-runtime;30-python-deps lines=4-4->5-7
- `projects-repo2run` / `denser-retriever` ok=True: 50-test-tooling[7/50]->30-python-deps[5/30] skip=31-node-deps lines=21-22->23-33
- `projects-repo2run` / `fastagency` ok=True: 50-test-tooling[7/50]->30-python-deps[5/30] skip=31-node-deps lines=21-22->23-33
- `setupbench-runs-all-gpt-5.4-multiblock` / `apache-cassandra` ok=True: 50-test-tooling[6/50]->30-project-dependencies[4/30] skip=40-native-build-config lines=52-53->54-62
- `setupbench-runs-all-gpt-5.4-multiblock` / `habitat-sh-habitat` ok=True: 50-test-tooling[5/50]->10-system-packages[2/10] skip=20-rust-runtime;30-project-dependencies lines=15-16->17-21

## Files

- `non_adjacent_rollback_records_combined.csv`: event/edge-level combined records.
- `non_adjacent_rollback_runs_combined.csv`: run-level combined records.
- `non_adjacent_rollback_combined_summary.csv`: aggregate counts for combined records.
- `runtime_non_adjacent_backjumps.csv`: raw runtime event-level additions.
- `runtime_non_adjacent_backjump_runs.csv`: raw runtime run-level additions.
