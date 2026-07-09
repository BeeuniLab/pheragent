# Non-Adjacent Rollback Case Details

Generated at: 2026-06-26T14:27:59.018793+00:00

Input: `statistic/rollback_non_adjacent_cases.csv`. Time order is the line order in each `executions.jsonl`; each repeated `base-image/docker_build` starts a new outer-attempt segment.

## 1. executionagent-runs-gpt4o / keras-team-keras

- run_dir: `executionagent-runs-gpt4o/state/keras-team-keras/keras/runs/executionagent-gpt4o-keras`
- final: ok=False / project_attempt_count=1 / classification=failed_in_project_run
- executions: 54 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-python-deps)
- final error: ing database ... 30%\n(Reading database ... 35%\n(Reading database ... 40%\n(Reading database ... preflight-success

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `01-python-deps` | failed | 2 | 00-preflight | previous_block |  | 22/5/14 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-python-deps | 3/0/0 |
| 20 | `20-python-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 3/0/0 |
| 30 | `30-python-deps` | failed | 0 | 20-python-runtime | previous_block |  | 16/4/12 |
| 50 | `50-test-tooling` | planned | 0 | none | none |  | 0/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-keras-8434bdf7eb9d-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-da6f0e0875ca-001-base-workspace |
| 1 | 6-8 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-5192bf6ea7de-002-00-preflight-success |
| 1 | 9-11 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-38f75a221dd5-003-10-system-packages-success |
| 1 | 12-27 | `30-python-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=1 | llm_repair#2=1 | block#1=1 | repair#1=1 | probe#2=1 | llm_repair#2=1 | 12/11 | executionagent-gpt4o-keras-1f87d2a2a374-004-20-python-runtime-success |
| 2 | 28-28 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 29-29 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-keras-8a87f0dbd68d-base |
| 2 | 30-32 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-774fd1a31f44-001-base-workspace |
| 2 | 33-54 | `01-python-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | probe#1=127 | probe#1=0 | probe#1=1 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=1 | validation#2=0 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | llm_repair#2=0 | repair#2=0 | block#3=1 | validation#3=0 | block#1=1 | probe#1=127 | probe#1=1 | block#2=1 | block#3=1 | 14/12 | executionagent-gpt4o-keras-4d5199288b19-002-00-preflight-success |

## 2. executionagent-runs-gpt4o / google-guava

- run_dir: `executionagent-runs-gpt4o/state/google-guava/guava/runs/executionagent-gpt4o-guava`
- final: ok=False / project_attempt_count=1 / classification=failed_in_project_run
- executions: 50 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-java-runtime (skipped: 01-java-deps)
- final error: d package libmaven3-core-java. Preparing to unpack .../28-libmaven3-core-java_3.8.7-2_all.deb ... Unpacking libmaven3-core-java (3.8.7-2) ... Selecting previously unselected package libwagon-file-java. Preparing to unpack .../29-libwagon-file-java_3.5.3-1_a...

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `01-java-deps` | failed | 2 | 00-preflight | previous_block |  | 22/4/14 |
| 20 | `20-java-runtime` | succeeded | 1 | 00-preflight | non_adjacent_block | 01-java-deps | 13/5/7 |
| 30 | `30-java-deps` | failed | 0 | 20-java-runtime | previous_block |  | 5/4/1 |
| 50 | `50-test-tooling` | planned | 0 | none | none |  | 0/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-guava-0beb4a213ac8-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-gpt4o-guava-3931051b6a64-001-base-workspace |
| 1 | 6-18 | `20-java-runtime` | block#1=0 | validation#1=127 | llm_probe#1=0 | probe#1=0 | probe#1=2 | probe#1=127 | probe#1=127 | probe#1=127 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | validation#1=127 | probe#1=2 | probe#1=127 | probe#1=127 | probe#1=127 | 7/6 | executionagent-gpt4o-guava-60173be24458-002-00-preflight-success |
| 1 | 19-23 | `30-java-deps` | block#1=1 | validation#1=0 | llm_probe#1=1 | llm_probe#2=1 | llm_repair#2=1 | block#1=1 | llm_probe#1=1 | llm_probe#2=1 | llm_repair#2=1 | 1/2 | executionagent-gpt4o-guava-3530e6af8aa4-003-20-java-runtime-repaired |
| 2 | 24-24 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 25-25 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-guava-add9d05beb01-base |
| 2 | 26-28 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-gpt4o-guava-c137b960fa2b-001-base-workspace |
| 2 | 29-50 | `01-java-deps` | block#1=127 | validation#1=127 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=1 | validation#2=0 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | llm_repair#2=0 | repair#2=0 | block#3=1 | validation#3=0 | block#1=127 | validation#1=127 | block#2=1 | block#3=1 | 14/12 | executionagent-gpt4o-guava-4cebb941cb04-002-00-preflight-success |

## 3. executionagent-runs-gpt54 / keras-team-keras

- run_dir: `executionagent-runs-gpt54/state/keras-team-keras/keras/runs/executionagent-keras`
- final: ok=False / project_attempt_count=3 / classification=failed_after_project_retries
- executions: 45 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-system-deps;02-python-deps;03-build-test-prep)
- final error: block failed: 30-python-deps

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-python-deps` | failed | 0 | 01-system-deps | previous_block |  | 5/3/2 |
| 3 | `03-build-test-prep` | planned | 0 | none | none |  | 0/0/0 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 3/0/0 |
| 20 | `20-python-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 3/0/0 |
| 30 | `30-python-deps` | failed | 2 | 20-python-runtime | previous_block |  | 21/3/13 |
| 50 | `50-test-tooling` | planned | 0 | none | none |  | 0/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-keras-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-keras-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-keras-002-00-preflight-success |
| 1 | 9-13 | `02-python-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | llm_repair#1=1 | llm_repair#2=1 | block#1=1 | llm_repair#1=1 | llm_repair#2=1 | 2/1 | executionagent-keras-003-01-system-deps-success |
| 2 | 14-14 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 15-15 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-keras-473a82a8f2c0-base |
| 2 | 16-18 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-keras-9b71272e04c4-001-base-workspace |
| 2 | 19-21 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-keras-79891575e969-002-00-preflight-success |
| 2 | 22-24 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-keras-e8ba04970ec0-003-10-system-packages-success |
| 2 | 25-45 | `30-python-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=1 | validation#2=0 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | llm_repair#2=0 | repair#2=0 | block#3=1 | validation#3=0 | block#1=1 | block#2=1 | block#3=1 | 13/11 | executionagent-keras-6ab04e4a84e6-004-20-python-runtime-success |

## 4. executionagent-runs-gpt54 / reactivex-rxjava

- run_dir: `executionagent-runs-gpt54/state/reactivex-rxjava/RxJava/runs/executionagent-rxjava`
- final: ok=False / project_attempt_count=3 / classification=failed_after_project_retries
- executions: 65 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-system-deps;02-language-deps;03-build-test-prep)
- final error: block failed: 30-java-deps

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-language-deps` | failed | 0 | 01-system-deps | previous_block |  | 12/3/8 |
| 3 | `03-build-test-prep` | planned | 0 | none | none |  | 0/0/0 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 3/0/0 |
| 20 | `20-java-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 3/0/0 |
| 21 | `21-gradle-toolchain` | succeeded | 1 | 20-java-runtime | previous_block |  | 12/3/6 |
| 30 | `30-java-deps` | failed | 2 | 21-gradle-toolchain | previous_block |  | 22/3/14 |
| 50 | `50-test-tooling` | planned | 0 | none | none |  | 0/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rxjava-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rxjava-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rxjava-002-00-preflight-success |
| 1 | 9-20 | `02-language-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_probe#2=0 | llm_repair#2=0 | repair#2=1 | block#1=1 | repair#1=1 | repair#2=1 | 8/6 | executionagent-rxjava-003-01-system-deps-success |
| 2 | 21-21 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 22-22 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rxjava-696b105bc148-base |
| 2 | 23-25 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rxjava-7e0d9b86490c-001-base-workspace |
| 2 | 26-28 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rxjava-77789ab82e47-002-00-preflight-success |
| 2 | 29-31 | `20-java-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rxjava-024883b263c0-003-10-system-packages-success |
| 2 | 32-43 | `21-gradle-toolchain` | block#1=None | validation#1=0 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=127 | probe#1=2 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | block#1=None | probe#1=127 | probe#1=2 | 6/5 | executionagent-rxjava-65f75f02b2e9-004-20-java-runtime-success |
| 2 | 44-65 | `30-java-deps` | block#1=0 | validation#1=1 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=1 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | llm_repair#2=0 | repair_prep#2=0 | repair#2=0 | block#3=0 | validation#3=1 | validation#1=1 | validation#2=1 | validation#3=1 | 14/11 | executionagent-rxjava-273285059abc-005-21-gradle-toolchain-repaired |

## 5. executionagent-runs-gpt54 / nestjs-nest

- run_dir: `executionagent-runs-gpt54/state/nestjs-nest/nest/runs/executionagent-nest`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 57 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-node-runtime (skipped: 01-system-deps;02-language-deps;03-build-test-prep)
- final error: ng database ... 40% (Reading database ... 45% (Reading database ... 50% (Reading database ... 55% (Reading database ... 60% (Reading database ... 65% (Reading database ... 70% (Reading database ... 75% (Reading database ... 80% (Reading database ... 85% (Re...

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 9/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-language-deps` | failed | 1 | 01-system-deps | previous_block |  | 13/5/7 |
| 3 | `03-build-test-prep` | planned | 0 | none | none |  | 0/0/0 |
| 20 | `20-node-runtime` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |
| 30 | `30-node-deps` | succeeded | 1 | 20-node-runtime | previous_block |  | 16/2/7 |
| 50 | `50-test-tooling` | succeeded | 0 | 30-node-deps | previous_block |  | 6/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-nest-204173cf70cf-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-nest-aaa7b7fa06e7-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-nest-502f14e79b58-002-00-preflight-success |
| 1 | 9-21 | `02-language-deps` | block#1=1 | validation#1=1 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_probe#2=0 | llm_repair#2=0 | repair#2=0 | block#2=1 | validation#2=1 | block#1=1 | validation#1=1 | repair#1=1 | block#2=1 | validation#2=1 | 7/5 | executionagent-nest-78adfd561a2e-003-01-system-deps-success |
| 2 | 22-22 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 23-23 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-nest-1b493427bb16-base |
| 2 | 24-26 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace |
| 2 | 27-29 | `20-node-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-nest-5ebee148b4f4-002-00-preflight-success |
| 2 | 30-42 | `30-node-deps` | block#1=1 | validation#1=1 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | block#1=1 | validation#1=1 | 7/6 | executionagent-nest-5be1f63093d7-003-20-node-runtime-success |
| 2 | 43-45 | `50-test-tooling` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-nest-543af816f6bf-004-30-node-deps-repaired |
| 2 | 46-48 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace |
| 2 | 49-51 | `20-node-runtime` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace |
| 2 | 52-54 | `30-node-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace |
| 2 | 55-57 | `50-test-tooling` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace |

## 6. executionagent-runs-gpt54 / pandas-dev-pandas

- run_dir: `executionagent-runs-gpt54/state/pandas-dev-pandas/pandas/runs/executionagent-pandas`
- final: ok=False / project_attempt_count=3 / classification=failed_after_project_retries
- executions: 62 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-python-runtime (skipped: 01-system-deps;02-python-deps;03-build-test-prep)
- final error: block failed: 50-test-tooling

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-python-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 3/0/0 |
| 3 | `03-build-test-prep` | running | 0 | 02-python-deps | previous_block |  | 4/1/1 |
| 20 | `20-python-runtime` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 3/0/0 |
| 30 | `30-python-deps` | succeeded | 1 | 20-python-runtime | previous_block |  | 14/0/7 |
| 50 | `50-test-tooling` | failed | 1 | 30-python-deps | previous_block |  | 25/5/15 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pandas-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pandas-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pandas-002-00-preflight-success |
| 1 | 9-11 | `02-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pandas-003-01-system-deps-success |
| 1 | 12-15 | `03-build-test-prep` | block#1=0 | validation#1=4 | llm_probe#1=0 | llm_repair#1=0 | validation#1=4 | 1/1 | executionagent-pandas-004-02-python-deps-success |
| 2 | 16-16 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 17-17 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pandas-8c6326d75b3f-base |
| 2 | 18-20 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pandas-8bd8ed53c116-001-base-workspace |
| 2 | 21-23 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pandas-871d808fb840-002-00-preflight-success |
| 2 | 24-26 | `30-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pandas-ac74ebd1c625-003-20-python-runtime-success |
| 2 | 27-28 | `50-test-tooling` | block#1=0 | validation#1=4 | validation#1=4 | 0/0 | executionagent-pandas-cfecb32c0351-004-30-python-deps-success |
| 2 | 29-39 | `30-python-deps` | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 |  | 7/6 | executionagent-pandas-ac74ebd1c625-003-20-python-runtime-success |
| 2 | 40-62 | `50-test-tooling` | block#2=0 | validation#2=4 | block#1=0 | validation#1=4 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=4 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | llm_repair#2=0 | repair_prep#2=0 | repair#2=2 | validation#2=4 | validation#1=4 | validation#2=4 | repair#2=2 | 15/12 | executionagent-pandas-fe8ee60d9235-005-30-python-deps-repaired |

## 7. executionagent-runs-gpt54 / django-django

- run_dir: `executionagent-runs-gpt54/state/django-django/django/runs/executionagent-django`
- final: ok=False / project_attempt_count=3 / classification=failed_after_project_retries
- executions: 57 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-system-deps;02-language-deps;03-build-test-prep)
- final error: docker run failed:

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 9/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 6/0/0 |
| 2 | `02-language-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 6/0/0 |
| 3 | `03-build-test-prep` | succeeded | 1 | 02-language-deps | previous_block |  | 13/1/4 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 3/0/0 |
| 20 | `20-python-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 3/0/0 |
| 21 | `21-node-runtime` | succeeded | 0 | 20-python-runtime | previous_block |  | 3/0/0 |
| 30 | `30-python-deps` | succeeded | 0 | 21-node-runtime | previous_block |  | 3/0/0 |
| 31 | `31-node-deps` | succeeded | 0 | 30-python-deps | previous_block |  | 3/0/0 |
| 50 | `50-test-tooling` | running | 0 | 31-node-deps | previous_block |  | 3/1/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-django-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-002-00-preflight-success |
| 1 | 9-11 | `02-language-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-003-01-system-deps-success |
| 1 | 12-21 | `03-build-test-prep` | block#1=0 | validation#1=2 | llm_probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | validation#1=2 | 4/3 | executionagent-django-004-02-language-deps-success |
| 1 | 22-24 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-django-001-base-workspace |
| 1 | 25-27 | `01-system-deps` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-django-001-base-workspace |
| 1 | 28-30 | `02-language-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-django-001-base-workspace |
| 1 | 31-33 | `03-build-test-prep` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-django-001-base-workspace |
| 1 | 34-34 | `oracle` | oracle#1=1 | oracle#1=1 | 0/0 | executionagent-django-006-final-clean-replay-clean-replay |
| 2 | 35-35 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 36-36 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-django-c09562525356-base |
| 2 | 37-39 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-e6f50ee84150-001-base-workspace |
| 2 | 40-42 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-984fd7bb8bbf-002-00-preflight-success |
| 2 | 43-45 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-2bba1975674a-003-10-system-packages-success |
| 2 | 46-48 | `21-node-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-23dd387db5ad-004-20-python-runtime-success |
| 2 | 49-51 | `30-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-2fe185f7b5d6-005-21-node-runtime-success |
| 2 | 52-54 | `31-node-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-django-0d23027cacc7-006-30-python-deps-success |
| 2 | 55-57 | `50-test-tooling` | block#1=0 | validation#1=2 | llm_probe#1=0 | validation#1=2 | 0/1 | executionagent-django-776b5fa1ddaa-007-31-node-deps-success |

## 8. executionagent-runs-gpt54 / mermaid-js-mermaid

- run_dir: `executionagent-runs-gpt54/state/mermaid-js-mermaid/mermaid/runs/executionagent-mermaid`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 43 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-node-runtime (skipped: 01-system-deps;02-language-deps;03-build-test-prep)
- final error: : packages/examples/dist/mermaid-examples.core.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare: packages/examples/dist/mermaid-examples.esm.mjs 15.7kb . prepare: packages/examples/dist/mermaid-examples.esm.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare...

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 9/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-language-deps` | failed | 1 | 01-system-deps | previous_block |  | 9/5/4 |
| 3 | `03-build-test-prep` | planned | 0 | none | none |  | 0/0/0 |
| 20 | `20-node-runtime` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |
| 30 | `30-node-deps` | succeeded | 0 | 20-node-runtime | previous_block |  | 6/0/0 |
| 50 | `50-test-tooling` | succeeded | 0 | 30-node-deps | previous_block |  | 6/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-mermaid-68c7ab009c9b-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-mermaid-20e020656b9a-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-mermaid-5ed08c0d3cc4-002-00-preflight-success |
| 1 | 9-17 | `02-language-deps` | block#1=1 | validation#1=1 | llm_probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_repair#2=0 | repair#2=0 | block#2=1 | validation#2=1 | block#1=1 | validation#1=1 | repair#1=1 | block#2=1 | validation#2=1 | 4/1 | executionagent-mermaid-fc59da1de26e-003-01-system-deps-success |
| 2 | 18-18 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 19-19 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-mermaid-526866b2ab14-base |
| 2 | 20-22 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace |
| 2 | 23-25 | `20-node-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-mermaid-e23b8e3f247d-002-00-preflight-success |
| 2 | 26-28 | `30-node-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-mermaid-ed79553de2ff-003-20-node-runtime-success |
| 2 | 29-31 | `50-test-tooling` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-mermaid-492cc5091570-004-30-node-deps-success |
| 2 | 32-34 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace |
| 2 | 35-37 | `20-node-runtime` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace |
| 2 | 38-40 | `30-node-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace |
| 2 | 41-43 | `50-test-tooling` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace |

## 9. executionagent-runs-gpt54 / dmlc-xgboost

- run_dir: `executionagent-runs-gpt54/state/dmlc-xgboost/xgboost/runs/executionagent-xgboost`
- final: ok=False / project_attempt_count=3 / classification=failed_after_project_retries
- executions: 49 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 10-system-deps;20-language-deps;30-build-test-prep)
- final error: block failed: 20-python-runtime

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `10-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `20-language-deps` | succeeded | 0 | 10-system-deps | previous_block |  | 3/0/0 |
| 3 | `30-build-test-prep` | failed | 0 | 20-language-deps | previous_block |  | 13/3/9 |
| 10 | `10-system-packages` | planned | 0 | 00-preflight | non_adjacent_block | 10-system-deps;20-language-deps;30-build-test-prep | 18/6/13 |
| 20 | `20-python-runtime` | failed | 0 | 10-system-packages | previous_block |  | 2/2/0 |
| 30 | `30-python-dependencies` | planned | 0 | none | none |  | 0/0/0 |
| 40 | `40-native-build-config` | planned | 0 | none | none |  | 0/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-xgboost-975e57dcc926-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-xgboost-bf82a28430e8-001-base-workspace |
| 1 | 6-8 | `10-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-xgboost-4fc94ddada9f-002-00-preflight-success |
| 1 | 9-11 | `20-language-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-xgboost-1f18ea28c8e0-003-10-system-deps-success |
| 1 | 12-24 | `30-build-test-prep` | block#1=0 | validation#1=1 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_probe#2=0 | llm_repair#2=0 | repair#2=128 | validation#1=1 | repair#1=1 | repair#2=128 | 9/7 | executionagent-xgboost-c948aa1a8cf5-004-20-language-deps-success |
| 2 | 25-25 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 26-26 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-xgboost-334496418e9d-base |
| 2 | 27-29 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-xgboost-270c9589e246-001-base-workspace |
| 2 | 30-32 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-xgboost-5807e5cb28d5-002-00-preflight-success |
| 2 | 33-34 | `20-python-runtime` | block#1=1 | validation#1=1 | block#1=1 | validation#1=1 | 0/0 | executionagent-xgboost-1dbea192fff4-003-10-system-packages-success |
| 2 | 35-49 | `10-system-packages` | llm_probe#1=0 | probe#1=1 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=127 | llm_probe#2=0 | probe#2=2 | probe#2=2 | probe#2=0 | probe#2=1 | probe#2=0 | llm_repair#2=0 | repair#2=127 | probe#1=1 | repair#1=127 | probe#2=2 | probe#2=2 | probe#2=1 | repair#2=127 | 13/11 | executionagent-xgboost-5807e5cb28d5-002-00-preflight-success |

## 10. executionagent-runs-gpt54 / apache-rocketmq

- run_dir: `executionagent-runs-gpt54/state/apache-rocketmq/rocketmq/runs/executionagent-rocketmq`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 59 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-system-deps;02-language-deps;03-build-test-prep)

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 12/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 6/0/0 |
| 2 | `02-language-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 6/0/0 |
| 3 | `03-build-test-prep` | succeeded | 0 | 02-language-deps | previous_block |  | 6/0/0 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |
| 20 | `20-java-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 6/0/0 |
| 30 | `30-java-deps` | succeeded | 0 | 20-java-runtime | previous_block |  | 6/0/0 |
| 50 | `50-test-tooling` | succeeded | 0 | 30-java-deps | previous_block |  | 6/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rocketmq-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-002-00-preflight-success |
| 1 | 9-11 | `02-language-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-003-01-system-deps-success |
| 1 | 12-14 | `03-build-test-prep` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-004-02-language-deps-success |
| 1 | 15-17 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace |
| 1 | 18-20 | `01-system-deps` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace |
| 1 | 21-23 | `02-language-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace |
| 1 | 24-26 | `03-build-test-prep` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace |
| 1 | 27-27 | `oracle` | oracle#1=1 | oracle#1=1 | 0/0 | executionagent-rocketmq-006-final-clean-replay-clean-replay |
| 2 | 28-28 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 29-29 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rocketmq-4d3a285fa71e-base |
| 2 | 30-32 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace |
| 2 | 33-35 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-e6d11140151a-002-00-preflight-success |
| 2 | 36-38 | `20-java-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-06a8682b834d-003-10-system-packages-success |
| 2 | 39-41 | `30-java-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-f63ee0d64f98-004-20-java-runtime-success |
| 2 | 42-44 | `50-test-tooling` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-rocketmq-08bdf7981c41-005-30-java-deps-success |
| 2 | 45-47 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace |
| 2 | 48-50 | `10-system-packages` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace |
| 2 | 51-53 | `20-java-runtime` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace |
| 2 | 54-56 | `30-java-deps` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace |
| 2 | 57-59 | `50-test-tooling` | clean_replay#5=0 | clean_replay_validation#5=0 | clean_replay_finalize#5=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace |

## 11. executionagent-runs-gpt54 / facebook-react

- run_dir: `executionagent-runs-gpt54/state/facebook-react/react/runs/executionagent-react`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 55 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-node-runtime (skipped: 01-system-deps;02-language-deps;03-build-test-prep)

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 12/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 6/0/0 |
| 2 | `02-language-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 6/0/0 |
| 3 | `03-build-test-prep` | succeeded | 0 | 02-language-deps | previous_block |  | 6/0/0 |
| 20 | `20-node-runtime` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |
| 30 | `30-node-deps` | succeeded | 0 | 20-node-runtime | previous_block |  | 6/0/0 |
| 50 | `50-test-tooling` | succeeded | 0 | 30-node-deps | previous_block |  | 6/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-react-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-002-00-preflight-success |
| 1 | 9-11 | `02-language-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-003-01-system-deps-success |
| 1 | 12-14 | `03-build-test-prep` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-004-02-language-deps-success |
| 1 | 15-17 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-react-001-base-workspace |
| 1 | 18-20 | `01-system-deps` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-react-001-base-workspace |
| 1 | 21-23 | `02-language-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-react-001-base-workspace |
| 1 | 24-26 | `03-build-test-prep` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-react-001-base-workspace |
| 1 | 27-29 | `oracle` | oracle#1=0 | oracle#2=0 | oracle#3=1 | oracle#3=1 | 0/0 | executionagent-react-006-final-clean-replay-clean-replay |
| 2 | 30-30 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 31-31 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-react-5126dee87285-base |
| 2 | 32-34 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace |
| 2 | 35-37 | `20-node-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-422e91878e6e-002-00-preflight-success |
| 2 | 38-40 | `30-node-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-92ff00afaf62-003-20-node-runtime-success |
| 2 | 41-43 | `50-test-tooling` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-react-871222bc8553-004-30-node-deps-success |
| 2 | 44-46 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace |
| 2 | 47-49 | `20-node-runtime` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace |
| 2 | 50-52 | `30-node-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace |
| 2 | 53-55 | `50-test-tooling` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace |

## 12. executionagent-runs-gpt54 / scipy-scipy

- run_dir: `executionagent-runs-gpt54/state/scipy-scipy/scipy/runs/executionagent-scipy`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 55 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-system-deps;02-python-deps;03-build-test-prep)
- final error: : No module named 'scipy' During handling of the above exception, another exception occurred: Traceback (most recent call last): File "<frozen runpy>", line 198, in _run_module_as_main File "<frozen runpy>", line 88, in _run_code File "/workspace/repo/.venv...

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 9/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-python-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 3/0/0 |
| 3 | `03-build-test-prep` | failed | 2 | 02-python-deps | previous_block |  | 12/3/5 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 6/0/0 |
| 20 | `20-python-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 6/0/0 |
| 30 | `30-python-deps` | succeeded | 0 | 20-python-runtime | previous_block |  | 6/0/0 |
| 50 | `50-test-tooling` | succeeded | 0 | 30-python-deps | previous_block |  | 6/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scipy-3de87abd430b-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-050ae481e289-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-89f3c9d7b3dc-002-00-preflight-success |
| 1 | 9-11 | `02-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-a937a9bb3ade-003-01-system-deps-success |
| 1 | 12-23 | `03-build-test-prep` | block#1=0 | validation#1=1 | llm_probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=1 | llm_repair#2=0 | repair_prep#2=0 | repair#2=0 | block#3=0 | validation#3=1 | validation#1=1 | validation#2=1 | validation#3=1 | 5/1 | executionagent-scipy-ea5492cfd2dc-004-02-python-deps-success |
| 2 | 24-24 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 25-25 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scipy-fc9f94497f5e-base |
| 2 | 26-28 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace |
| 2 | 29-31 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-57b5802152b5-002-00-preflight-success |
| 2 | 32-34 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-ac40a63d2494-003-10-system-packages-success |
| 2 | 35-37 | `30-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-5a0b93960389-004-20-python-runtime-success |
| 2 | 38-40 | `50-test-tooling` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scipy-2729ab86307e-005-30-python-deps-success |
| 2 | 41-43 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace |
| 2 | 44-46 | `10-system-packages` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace |
| 2 | 47-49 | `20-python-runtime` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace |
| 2 | 50-52 | `30-python-deps` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace |
| 2 | 53-55 | `50-test-tooling` | clean_replay#5=0 | clean_replay_validation#5=0 | clean_replay_finalize#5=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace |

## 13. executionagent-runs-gpt54 / scikit-learn-scikit-learn

- run_dir: `executionagent-runs-gpt54/state/scikit-learn-scikit-learn/scikit-learn/runs/executionagent-scikit-learn`
- final: ok=False / project_attempt_count=3 / classification=failed_after_project_retries
- executions: 64 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-python-runtime (skipped: 01-system-deps;02-python-deps;03-build-test-prep)
- final error: block failed: 50-test-tooling

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 6/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-python-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 3/0/0 |
| 3 | `03-build-test-prep` | failed | 1 | 02-python-deps | previous_block |  | 10/3/5 |
| 20 | `20-python-runtime` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 3/0/0 |
| 30 | `30-python-deps` | succeeded | 1 | 20-python-runtime | previous_block |  | 14/2/7 |
| 50 | `50-test-tooling` | failed | 0 | 30-python-deps | previous_block |  | 21/5/13 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scikit-learn-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scikit-learn-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scikit-learn-002-00-preflight-success |
| 1 | 9-11 | `02-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scikit-learn-003-01-system-deps-success |
| 1 | 12-21 | `03-build-test-prep` | block#1=0 | validation#1=1 | llm_probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=4 | llm_repair#2=0 | repair_prep#2=0 | repair#2=1 | validation#1=1 | validation#2=4 | repair#2=1 | 5/1 | executionagent-scikit-learn-004-02-python-deps-success |
| 2 | 22-22 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 23-23 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scikit-learn-dc2b73c790d0-base |
| 2 | 24-26 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scikit-learn-fa71d0da7a59-001-base-workspace |
| 2 | 27-29 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scikit-learn-463def3e485d-002-00-preflight-success |
| 2 | 30-32 | `30-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-scikit-learn-2b7599eefe93-003-20-python-runtime-success |
| 2 | 33-34 | `50-test-tooling` | block#1=0 | validation#1=4 | validation#1=4 | 0/0 | executionagent-scikit-learn-6a24f113347a-004-30-python-deps-success |
| 2 | 35-45 | `30-python-deps` | llm_probe#1=0 | probe#1=0 | probe#1=1 | probe#1=1 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | probe#1=1 | probe#1=1 | 7/6 | executionagent-scikit-learn-2b7599eefe93-003-20-python-runtime-success |
| 2 | 46-64 | `50-test-tooling` | block#2=0 | validation#2=4 | block#1=0 | validation#1=4 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | probe#2=0 | llm_repair#2=0 | repair#2=1 | validation#2=4 | validation#1=4 | repair#1=1 | repair#2=1 | 13/11 | executionagent-scikit-learn-5c51ab8c178b-005-30-python-deps-repaired |

## 14. executionagent-runs-gpt54 / google-guava

- run_dir: `executionagent-runs-gpt54/state/google-guava/guava/runs/executionagent-guava`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 74 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 10-system-packages (skipped: 01-system-deps;02-language-deps;03-build-test-prep)

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 12/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 6/0/0 |
| 2 | `02-language-deps` | succeeded | 1 | 01-system-deps | previous_block |  | 11/1/2 |
| 3 | `03-build-test-prep` | succeeded | 0 | 02-language-deps | previous_block |  | 6/0/0 |
| 10 | `10-system-packages` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |
| 20 | `20-java-runtime` | succeeded | 0 | 10-system-packages | previous_block |  | 6/0/0 |
| 30 | `30-java-deps` | succeeded | 1 | 20-java-runtime | previous_block |  | 16/1/7 |
| 50 | `50-test-tooling` | succeeded | 0 | 30-java-deps | previous_block |  | 6/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-guava-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-002-00-preflight-success |
| 1 | 9-16 | `02-language-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | block#1=1 | 2/1 | executionagent-guava-003-01-system-deps-success |
| 1 | 17-19 | `03-build-test-prep` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-004-02-language-deps-repaired |
| 1 | 20-22 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-guava-001-base-workspace |
| 1 | 23-25 | `01-system-deps` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-guava-001-base-workspace |
| 1 | 26-28 | `02-language-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-guava-001-base-workspace |
| 1 | 29-31 | `03-build-test-prep` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-guava-001-base-workspace |
| 1 | 32-32 | `oracle` | oracle#1=1 | oracle#1=1 | 0/0 | executionagent-guava-006-final-clean-replay-clean-replay |
| 2 | 33-33 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 34-34 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-guava-73ec38433bc4-base |
| 2 | 35-37 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace |
| 2 | 38-40 | `10-system-packages` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-d65197352c5c-002-00-preflight-success |
| 2 | 41-43 | `20-java-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-cbd9d55b2240-003-10-system-packages-success |
| 2 | 44-56 | `30-java-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | block#1=1 | 7/6 | executionagent-guava-b609922d16a9-004-20-java-runtime-success |
| 2 | 57-59 | `50-test-tooling` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-guava-6f67e0c1b6f6-005-30-java-deps-repaired |
| 2 | 60-62 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace |
| 2 | 63-65 | `10-system-packages` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace |
| 2 | 66-68 | `20-java-runtime` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace |
| 2 | 69-71 | `30-java-deps` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace |
| 2 | 72-74 | `50-test-tooling` | clean_replay#5=0 | clean_replay_validation#5=0 | clean_replay_finalize#5=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace |

## 15. executionagent-runs-gpt54 / pytest-dev-pytest

- run_dir: `executionagent-runs-gpt54/state/pytest-dev-pytest/pytest/runs/executionagent-pytest`
- final: ok=True / project_attempt_count=3 / classification=succeeded_after_project_retry
- executions: 72 events, outer-attempt segments seen: 2
- non-adjacent edge(s): 00-preflight -> 20-python-runtime (skipped: 01-system-deps;02-language-deps;03-build-test-prep)
- final error: 5 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (1.6.0) Requirement already satisfied: pygments>=2.7.2 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (2.20.0) Collecting argcomplete (from pytest==0.1....

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 9/0/0 |
| 1 | `01-system-deps` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `02-language-deps` | succeeded | 0 | 01-system-deps | previous_block |  | 3/0/0 |
| 3 | `03-build-test-prep` | failed | 0 | 02-language-deps | previous_block |  | 11/3/7 |
| 20 | `20-python-runtime` | succeeded | 0 | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |
| 30 | `30-python-deps` | succeeded | 1 | 20-python-runtime | previous_block |  | 17/4/7 |
| 50 | `50-test-tooling` | succeeded | 1 | 30-python-deps | previous_block |  | 19/3/6 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pytest-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pytest-001-base-workspace |
| 1 | 6-8 | `01-system-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pytest-002-00-preflight-success |
| 1 | 9-11 | `02-language-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pytest-003-01-system-deps-success |
| 1 | 12-22 | `03-build-test-prep` | block#1=0 | validation#1=2 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=1 | llm_probe#2=0 | llm_repair#2=0 | repair#2=4 | validation#1=2 | repair#1=1 | repair#2=4 | 7/5 | executionagent-pytest-004-02-language-deps-success |
| 2 | 23-23 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 2 | 24-24 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pytest-971e89d06c24-base |
| 2 | 25-27 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace |
| 2 | 28-30 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pytest-97009fd00176-002-00-preflight-success |
| 2 | 31-33 | `30-python-deps` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | executionagent-pytest-3921262c8ad9-003-20-python-runtime-success |
| 2 | 34-35 | `50-test-tooling` | block#1=0 | validation#1=4 | validation#1=4 | 0/0 | executionagent-pytest-c5b26770d2b0-004-30-python-deps-success |
| 2 | 36-46 | `30-python-deps` | llm_probe#1=0 | probe#1=1 | probe#1=1 | probe#1=0 | probe#1=1 | probe#1=2 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | probe#1=1 | probe#1=1 | probe#1=1 | probe#1=2 | 7/6 | executionagent-pytest-3921262c8ad9-003-20-python-runtime-success |
| 2 | 47-60 | `50-test-tooling` | block#2=0 | validation#2=4 | block#1=0 | validation#1=4 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=0 | repair#1=0 | block#2=0 | validation#2=0 | finalize#2=0 | validation#2=4 | validation#1=4 | 6/5 | executionagent-pytest-dfa57eb36063-005-30-python-deps-repaired |
| 2 | 61-63 | `00-preflight` | clean_replay#1=0 | clean_replay_validation#1=0 | clean_replay_finalize#1=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace |
| 2 | 64-66 | `20-python-runtime` | clean_replay#2=0 | clean_replay_validation#2=0 | clean_replay_finalize#2=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace |
| 2 | 67-69 | `30-python-deps` | clean_replay#3=0 | clean_replay_validation#3=0 | clean_replay_finalize#3=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace |
| 2 | 70-72 | `50-test-tooling` | clean_replay#4=0 | clean_replay_validation#4=0 | clean_replay_finalize#4=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace |

## 16. projects-repo2run / instructlab

- run_dir: `projects-repo2run/instructlab/.pheragent/runs/repo2run-gpt-4o-20241120-instructlab`
- final: ok=False / project_attempt_count=1 / classification=failed_in_project_run
- executions: 80 events, outer-attempt segments seen: 1
- non-adjacent edge(s): 
- final error: block failed: 30-python-deps

### Block Flow

| order | block | final status | repairs | rollback source | edge | skipped | events/fails/repair-events |
|---:|---|---|---:|---|---|---|---:|
| 0 | `00-preflight` | succeeded | 0 | base_workspace | base_workspace |  | 3/0/0 |
| 1 | `20-python-runtime` | succeeded | 0 | 00-preflight | previous_block |  | 3/0/0 |
| 2 | `30-python-deps` | failed | 7 | 20-python-runtime | previous_block |  | 72/28/50 |
| 3 | `50-test-tooling` | planned | 0 | none | none |  | 0/0/0 |

### Chronological Block Segments

| segment | lines | block | phase/attempt/exit sequence | failed phases | repairs/probes | checkpoint before |
|---:|---:|---|---|---|---:|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | repo2run-gpt-4o-20241120-instructlab-3e9bda1fd149-base |
| 1 | 3-5 | `00-preflight` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | repo2run-gpt-4o-20241120-instructlab-6149c9a58c18-001-base-workspace |
| 1 | 6-8 | `20-python-runtime` | block#1=0 | validation#1=0 | finalize#1=0 |  | 0/0 | repo2run-gpt-4o-20241120-instructlab-7d5e818f54fe-002-00-preflight-success |
| 1 | 9-80 | `30-python-deps` | block#1=1 | validation#1=0 | llm_probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | probe#1=0 | llm_repair#1=1 | llm_probe#2=0 | probe#2=2 | probe#2=1 | probe#2=0 | probe#2=0 | llm_repair#2=1 | llm_probe#3=0 | probe#3=2 | probe#3=0 | probe#3=0 | probe#3=0 | probe#3=0 | llm_repair#3=1 | llm_probe#4=0 | probe#4=127 | probe#4=None | probe#4=0 | probe#4=127 | probe#4=127 | llm_repair#4=1 | llm_probe#5=0 | probe#5=0 | probe#5=0 | probe#5=0 | probe#5=0 | probe#5=0 | llm_repair#5=1 | llm_probe#6=0 | llm_repair#6=1 | llm_repair#7=1 | llm_repair#8=1 | llm_repair#9=1 | llm_repair#10=0 | repair#10=0 | block#2=1 | validation#2=0 | llm_repair#11=0 | repair#11=0 | block#3=1 | validation#3=0 | llm_repair#12=1 | llm_repair#13=1 | llm_repair#14=1 | llm_repair#15=0 | repair#15=0 | block#4=1 | validation#4=0 | llm_repair#16=0 | repair#16=0 | block#5=1 | validation#5=0 | llm_repair#17=1 | llm_repair#18=0 | repair#18=0 | block#6=1 | validation#6=0 | llm_repair#19=0 | repair#19=0 | block#7=1 | validation#7=0 | llm_repair#20=0 | repair#20=0 | block#8=1 | validation#8=0 | block#1=1 | llm_repair#1=1 | probe#2=2 | probe#2=1 | llm_repair#2=1 | probe#3=2 | llm_repair#3=1 | probe#4=127 | probe#4=None | probe#4=127 | probe#4=127 | llm_repair#4=1 | llm_repair#5=1 | llm_repair#6=1 | llm_repair#7=1 | llm_repair#8=1 | llm_repair#9=1 | block#2=1 | block#3=1 | llm_repair#12=1 | llm_repair#13=1 | llm_repair#14=1 | block#4=1 | block#5=1 | llm_repair#17=1 | block#6=1 | block#7=1 | block#8=1 | 50/29 | repo2run-gpt-4o-20241120-instructlab-42f3f38cda80-003-20-python-runtime-success |

