# Apache Cassandra rollback / runtime backjump analysis

Generated at: 2026-06-26T15:12:55.208049+00:00

口径：直接读取 Cassandra 三个 benchmark run 的项目轨迹目录：`blocks/*.json`、`executions.jsonl` 和 `manifest.json`。没有使用 results/summary。

## setupbench-runs-all-gpt-5.4-multiblock

- run_dir: `setupbench-runs-all-gpt-5.4-multiblock/state/apache-cassandra/cassandra/runs/setupbench-cassandra`
- manifest ok: True; error: ``; final_image: `pheragent-setupbench:setupbench-cassandra-3a5fd9487c7a-011-final-clean-replay-clean-replay`
- executions: 93 events; blocks: 7
- runtime backjump: 50-test-tooling[50] lines 52-53 -> 30-project-dependencies[30] lines 54-62 (runtime_backjump_non_adjacent)

### Final checkpoint graph from blocks/*.json

| order | block | status | baseline source | edge | skipped |
|---:|---|---|---|---|---|
| 0 | `00-preflight` | succeeded | `00-preflight` | previous_or_forward_final_graph |  |
| 10 | `10-system-packages` | succeeded | `00-preflight` | previous_or_forward_final_graph |  |
| 20 | `20-runtime-toolchain` | succeeded | `10-system-packages` | previous_or_forward_final_graph |  |
| 30 | `30-project-dependencies` | succeeded | `20-runtime-toolchain` | previous_or_forward_final_graph |  |
| 40 | `40-native-build-config` | succeeded | `30-project-dependencies` | previous_or_forward_final_graph |  |
| 50 | `50-test-tooling` | succeeded | `40-native-build-config` | previous_or_forward_final_graph |  |
| 60 | `60-service-or-final-validation-prep` | succeeded | `50-test-tooling` | previous_or_forward_final_graph |  |

### Runtime block groups

| lines | block | order | phases | failed phases | checkpoint before | note |
|---:|---|---:|---|---|---|---|
| 1-1 | `base-image` |  | docker_build#1=0 |  | `` | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfile: 1.47kB ... |
| 2-2 | `container-preflight` |  | container_preflight#1=0 |  | `pheragent-setupbench:setupbench-cassandra-1303d5f86952-base` | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 8cca9c8c6a51 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19... |
| 3-5 | `00-preflight` | 0 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 6-8 | `10-system-packages` | 10 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-c8ea82e72cb9-002-00-preflight-success` |  |
| 9-11 | `20-runtime-toolchain` | 20 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-563286dd4152-003-10-system-packages-success` |  |
| 12-39 | `30-project-dependencies` | 30 | block#1=1 / validation#1=0 / llm_probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_repair#2=0 / repair#2=1 / llm_repair#3=0 / repair#3=0 / block#2=1 / validation#2=0 / llm_repair#4=0 / repair#4=0 / block#3=1 / validation#3=0 / llm_repair#5=0 / repair#5=0 / block#4=1 / validation#4=0 / llm_repair#6=0 / repair#6=0 / block#5=1 / validation#5=0 / llm_repair#7=0 / repair#7=0 / block#6=0 / validation#6=0 / finalize#6=0 | block#1=1 / repair#1=1 / repair#2=1 / block#2=1 / block#3=1 / block#4=1 / block#5=1 | `pheragent-setupbench:setupbench-cassandra-7bf452af301e-004-20-runtime-toolchain-success` |  |
| 40-51 | `40-native-build-config` | 40 | block#1=1 / validation#1=1 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | block#1=1 / validation#1=1 | `pheragent-setupbench:setupbench-cassandra-0a53ca38dba2-005-30-project-dependencies-repa...` |  |
| 52-53 | `50-test-tooling` | 50 | block#1=1 / validation#1=1 | block#1=1 / validation#1=1 | `pheragent-setupbench:setupbench-cassandra-635a35353477-006-40-native-build-config-repaired` |  |
| 54-62 | `30-project-dependencies` | 30 | llm_repair#1=0 / repair#1=1 / llm_repair#2=0 / repair#2=1 / llm_repair#3=0 / repair#3=0 / block#4=0 / validation#4=0 / finalize#4=0 | repair#1=1 / repair#2=1 | `pheragent-setupbench:setupbench-cassandra-7bf452af301e-004-20-runtime-toolchain-success` |  |
| 63-65 | `40-native-build-config` | 40 | block#4=0 / validation#4=0 / finalize#4=0 |  | `pheragent-setupbench:setupbench-cassandra-6f624f8fbf1a-007-30-project-dependencies-repa...` |  |
| 66-68 | `50-test-tooling` | 50 | block#4=0 / validation#4=0 / finalize#4=0 |  | `pheragent-setupbench:setupbench-cassandra-fb896676d92a-008-40-native-build-config-success` |  |
| 69-71 | `60-service-or-final-validation-prep` | 60 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-2d81ea37b3c2-009-50-test-tooling-success` |  |
| 72-74 | `00-preflight` | 0 | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 75-77 | `10-system-packages` | 10 | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 78-80 | `20-runtime-toolchain` | 20 | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 81-83 | `30-project-dependencies` | 30 | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 84-86 | `40-native-build-config` | 40 | clean_replay#5=0 / clean_replay_validation#5=0 / clean_replay_finalize#5=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 87-89 | `50-test-tooling` | 50 | clean_replay#6=0 / clean_replay_validation#6=0 / clean_replay_finalize#6=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 90-92 | `60-service-or-final-validation-prep` | 60 | clean_replay#7=0 / clean_replay_validation#7=0 / clean_replay_finalize#7=0 |  | `pheragent-setupbench:setupbench-cassandra-08861fd152f3-001-base-workspace` |  |
| 93-93 | `oracle` |  | oracle#1=0 |  | `pheragent-setupbench:setupbench-cassandra-3a5fd9487c7a-011-final-clean-replay-clean-replay` | 3,664 Flushing.java:179 - Completed flushing /workspace/repo/.cassandra-data/system/local-7ad54392bcdd35a684174e047860b377/oa-3-big-Data.db (53B) for commitl... |

## setupbench-runs-all-gpt-4.1-2rerun

- run_dir: `setupbench-runs-all-gpt-4.1-2rerun/state/apache-cassandra/cassandra/runs/setupbench-cassandra`
- manifest ok: False; error: `final clean replay failed`; final_image: `pheragent-setupbench:setupbench-cassandra-001-base-workspace`
- executions: 15 events; blocks: 3
- runtime backjump: none

### Final checkpoint graph from blocks/*.json

| order | block | status | baseline source | edge | skipped |
|---:|---|---|---|---|---|
| 0 | `00-preflight` | succeeded | `00-preflight` | previous_or_forward_final_graph |  |
| 1 | `01-system-deps` | succeeded | `00-preflight` | previous_or_forward_final_graph |  |
| 2 | `02-build-test-prep` | succeeded | `01-system-deps` | previous_or_forward_final_graph |  |

### Runtime block groups

| lines | block | order | phases | failed phases | checkpoint before | note |
|---:|---|---:|---|---|---|---|
| 1-1 | `base-image` |  | docker_build#1=0 |  | `` | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfile: #1 tran... |
| 2-2 | `container-preflight` |  | container_preflight#1=0 |  | `pheragent-setupbench:setupbench-cassandra-base` | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 4a8cefb86f6a 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19... |
| 3-5 | `00-preflight` | 0 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-001-base-workspace` |  |
| 6-8 | `01-system-deps` | 1 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-002-00-preflight-success` |  |
| 9-11 | `02-build-test-prep` | 2 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-003-01-system-deps-success` |  |
| 12-14 | `00-preflight` | 0 | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-001-base-workspace` |  |
| 15-15 | `01-system-deps` | 1 | clean_replay#2=100 | clean_replay#2=100 | `pheragent-setupbench:setupbench-cassandra-001-base-workspace` | E: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/noble-updates/main/binary-amd64/Packages.gz File has unexpected size (1284134 != 1284127). Mirror s... |

## setupbench-runs-all-gpt-4.1

- run_dir: `setupbench-runs-all-gpt-4.1/state/apache-cassandra/cassandra/runs/setupbench-cassandra`
- manifest ok: False; error: `oracle validation failed`; final_image: `pheragent-setupbench:setupbench-cassandra-004-20-build-prep-success`
- executions: 14 events; blocks: 3
- runtime backjump: none

### Final checkpoint graph from blocks/*.json

| order | block | status | baseline source | edge | skipped |
|---:|---|---|---|---|---|
| 0 | `00-preflight` | succeeded | `00-preflight` | previous_or_forward_final_graph |  |
| 1 | `10-system-deps` | succeeded | `00-preflight` | previous_or_forward_final_graph |  |
| 2 | `20-build-prep` | succeeded | `10-system-deps` | previous_or_forward_final_graph |  |

### Runtime block groups

| lines | block | order | phases | failed phases | checkpoint before | note |
|---:|---|---:|---|---|---|---|
| 1-1 | `base-image` |  | docker_build#1=0 |  | `` | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfile: #1 tran... |
| 2-2 | `container-preflight` |  | container_preflight#1=0 |  | `pheragent-setupbench:setupbench-cassandra-base` | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 3083b7f1fa8c 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19... |
| 3-3 | `base-image` |  | docker_build#1=0 |  | `` | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfile: 1.47kB ... |
| 4-4 | `container-preflight` |  | container_preflight#1=0 |  | `pheragent-setupbench:setupbench-cassandra-base` | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 48416234c582 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19... |
| 5-7 | `00-preflight` | 0 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-001-base-workspace` |  |
| 8-10 | `10-system-deps` | 1 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-002-00-preflight-success` |  |
| 11-13 | `20-build-prep` | 2 | block#1=0 / validation#1=0 / finalize#1=0 |  | `pheragent-setupbench:setupbench-cassandra-003-10-system-deps-success` |  |
| 14-14 | `oracle` |  | oracle#1=1 | oracle#1=1 | `pheragent-setupbench:setupbench-cassandra-004-20-build-prep-success` | Error opening zip file or JAR manifest missing : bin/../lib/jamm-0.4.0.jar Error occurred during initialization of VM agent library failed to init: instrumen... |

