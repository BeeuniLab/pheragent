# 非相邻回溯成功/失败轨迹

Generated at: 2026-06-26T14:40:33.639451+00:00

口径：读取 `statistic/rollback_non_adjacent_case_chronology_summary.csv`，其上游来自各项目目录的 `blocks/*.json` 和 `executions.jsonl`。

## Benchmark 分布

- 成功 7 条：executionagent-runs-gpt54=7
- 失败 9 条：executionagent-runs-gpt4o=2；executionagent-runs-gpt54=6；projects-repo2run=1

## 最终成功案例

### Case 5 - executionagent-runs-gpt54 / nestjs-nest

- owner_repo: `nestjs/nest`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-node-runtime skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:failed | 03-build-test-prep:planned | 20-node-runtime:succeeded | 30-node-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 00-preflight->20-node-runtime 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 20-node-runtime->30-node-deps 相邻承接 | 30-node-deps->50-test-tooling 相邻承接`
- repair_blocks: `02-language-deps:failed, events=13, failed_events=5, repairs=1, repair_events=7, error=ng database ... 40% (Reading database ... 45% (Reading database ... 50% (Reading database ... 55% (Reading database ....; 30-node-deps:succeeded, events=16, failed_events=2, repairs=1, repair_events=7`
- final_error: `ng database ... 40% (Reading database ... 45% (Reading database ... 50% (Reading database ... 55% (Reading database ... 60% (Reading database ... 65% (Reading database ... 70% (Reading database ... 75% (Reading database ... 80% (Reading database ... 85% (Re...`
- run_dir: `executionagent-runs-gpt54/state/nestjs-nest/nest/runs/executionagent-nest`

### Case 8 - executionagent-runs-gpt54 / mermaid-js-mermaid

- owner_repo: `mermaid-js/mermaid`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-node-runtime skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:failed | 03-build-test-prep:planned | 20-node-runtime:succeeded | 30-node-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 00-preflight->20-node-runtime 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 20-node-runtime->30-node-deps 相邻承接 | 30-node-deps->50-test-tooling 相邻承接`
- repair_blocks: `02-language-deps:failed, events=9, failed_events=5, repairs=1, repair_events=4, error=: packages/examples/dist/mermaid-examples.core.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare: packages/examples/d...`
- final_error: `: packages/examples/dist/mermaid-examples.core.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare: packages/examples/dist/mermaid-examples.esm.mjs 15.7kb . prepare: packages/examples/dist/mermaid-examples.esm.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare...`
- run_dir: `executionagent-runs-gpt54/state/mermaid-js-mermaid/mermaid/runs/executionagent-mermaid`

### Case 10 - executionagent-runs-gpt54 / apache-rocketmq

- owner_repo: `apache/rocketmq`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:succeeded | 03-build-test-prep:succeeded | 10-system-packages:succeeded | 20-java-runtime:succeeded | 30-java-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 02-language-deps->03-build-test-prep 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 10-system-packages->20-java-runtime 相邻承接 | 20-java-runtime->30-java-deps 相邻承接 | 30-java-deps->50-test-tooling 相邻承接`
- repair_blocks: `无 block 级修复事件`
- run_dir: `executionagent-runs-gpt54/state/apache-rocketmq/rocketmq/runs/executionagent-rocketmq`

### Case 11 - executionagent-runs-gpt54 / facebook-react

- owner_repo: `facebook/react`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-node-runtime skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:succeeded | 03-build-test-prep:succeeded | 20-node-runtime:succeeded | 30-node-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 02-language-deps->03-build-test-prep 相邻承接 | 00-preflight->20-node-runtime 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 20-node-runtime->30-node-deps 相邻承接 | 30-node-deps->50-test-tooling 相邻承接`
- repair_blocks: `无 block 级修复事件`
- run_dir: `executionagent-runs-gpt54/state/facebook-react/react/runs/executionagent-react`

### Case 12 - executionagent-runs-gpt54 / scipy-scipy

- owner_repo: `scipy/scipy`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-system-deps;02-python-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-python-deps:succeeded | 03-build-test-prep:failed | 10-system-packages:succeeded | 20-python-runtime:succeeded | 30-python-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-python-deps 相邻承接 | 02-python-deps->03-build-test-prep 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-system-deps;02-python-deps;03-build-test-prep | 10-system-packages->20-python-runtime 相邻承接 | 20-python-runtime->30-python-deps 相邻承接 | 30-python-deps->50-test-tooling 相邻承接`
- repair_blocks: `03-build-test-prep:failed, events=12, failed_events=3, repairs=2, repair_events=5, error=: No module named 'scipy' During handling of the above exception, another exception occurred: Traceback (most recent ...`
- final_error: `: No module named 'scipy' During handling of the above exception, another exception occurred: Traceback (most recent call last): File "<frozen runpy>", line 198, in _run_module_as_main File "<frozen runpy>", line 88, in _run_code File "/workspace/repo/.venv...`
- run_dir: `executionagent-runs-gpt54/state/scipy-scipy/scipy/runs/executionagent-scipy`

### Case 14 - executionagent-runs-gpt54 / google-guava

- owner_repo: `google/guava`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:succeeded | 03-build-test-prep:succeeded | 10-system-packages:succeeded | 20-java-runtime:succeeded | 30-java-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 02-language-deps->03-build-test-prep 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 10-system-packages->20-java-runtime 相邻承接 | 20-java-runtime->30-java-deps 相邻承接 | 30-java-deps->50-test-tooling 相邻承接`
- repair_blocks: `02-language-deps:succeeded, events=11, failed_events=1, repairs=1, repair_events=2; 30-java-deps:succeeded, events=16, failed_events=1, repairs=1, repair_events=7`
- run_dir: `executionagent-runs-gpt54/state/google-guava/guava/runs/executionagent-guava`

### Case 15 - executionagent-runs-gpt54 / pytest-dev-pytest

- owner_repo: `pytest-dev/pytest`
- project_attempt_count: 3; classification: `succeeded_after_project_retry`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-python-runtime skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:succeeded | 03-build-test-prep:failed | 20-python-runtime:succeeded | 30-python-deps:succeeded | 50-test-tooling:succeeded`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 02-language-deps->03-build-test-prep 相邻承接 | 00-preflight->20-python-runtime 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 20-python-runtime->30-python-deps 相邻承接 | 30-python-deps->50-test-tooling 相邻承接`
- repair_blocks: `03-build-test-prep:failed, events=11, failed_events=3, repairs=0, repair_events=7, error=5 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (1.6.0) Requirement already satisfied: p...; 30-python-deps:succeeded, events=17, failed_events=4, repairs=1, repair_events=7; 50-test-tooling:succeeded, events=19, failed_events=3, repairs=1, repair_events=6, error=ERROR: /workspace/repo/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+gfa6a232d5'`
- final_error: `5 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (1.6.0) Requirement already satisfied: pygments>=2.7.2 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (2.20.0) Collecting argcomplete (from pytest==0.1....`
- run_dir: `executionagent-runs-gpt54/state/pytest-dev-pytest/pytest/runs/executionagent-pytest`

## 最终失败案例

### Case 1 - executionagent-runs-gpt4o / keras-team-keras

- owner_repo: `keras-team/keras`
- project_attempt_count: 1; classification: `failed_in_project_run`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-python-deps`
- final_status_sequence: `00-preflight:succeeded | 01-python-deps:failed | 10-system-packages:succeeded | 20-python-runtime:succeeded | 30-python-deps:failed | 50-test-tooling:planned`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-python-deps 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-python-deps | 10-system-packages->20-python-runtime 相邻承接 | 20-python-runtime->30-python-deps 相邻承接`
- repair_blocks: `01-python-deps:failed, events=22, failed_events=5, repairs=2, repair_events=14, error=ing database ... 30% (Reading database ... 35% (Reading database ... 40% (Reading database ... 45% (Reading database ...; 30-python-deps:failed, events=16, failed_events=4, repairs=0, repair_events=12, error=Looking in indexes: https://pypi.org/simple, https://download.pytorch.org/whl/cpu Ignoring tensorflow: markers 'sys_p...`
- final_error: `ing database ... 30%\n(Reading database ... 35%\n(Reading database ... 40%\n(Reading database ... preflight-success`
- run_dir: `executionagent-runs-gpt4o/state/keras-team-keras/keras/runs/executionagent-gpt4o-keras`

### Case 2 - executionagent-runs-gpt4o / google-guava

- owner_repo: `google/guava`
- project_attempt_count: 1; classification: `failed_in_project_run`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-java-runtime skip=01-java-deps`
- final_status_sequence: `00-preflight:succeeded | 01-java-deps:failed | 20-java-runtime:succeeded | 30-java-deps:failed | 50-test-tooling:planned`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-java-deps 相邻承接 | 00-preflight->20-java-runtime 非相邻回溯，跳过 01-java-deps | 20-java-runtime->30-java-deps 相邻承接`
- repair_blocks: `01-java-deps:failed, events=22, failed_events=4, repairs=2, repair_events=14, error=d package libmaven3-core-java. Preparing to unpack .../28-libmaven3-core-java_3.8.7-2_all.deb ... Unpacking libmaven3...; 20-java-runtime:succeeded, events=13, failed_events=5, repairs=1, repair_events=7; 30-java-deps:failed, events=5, failed_events=4, repairs=0, repair_events=1, error=[pheragent] warming java dependencies [[1;31mERROR[m] Failed to execute goal [32morg.apache.maven.plugins:maven-de...`
- final_error: `d package libmaven3-core-java. Preparing to unpack .../28-libmaven3-core-java_3.8.7-2_all.deb ... Unpacking libmaven3-core-java (3.8.7-2) ... Selecting previously unselected package libwagon-file-java. Preparing to unpack .../29-libwagon-file-java_3.5.3-1_a...`
- run_dir: `executionagent-runs-gpt4o/state/google-guava/guava/runs/executionagent-gpt4o-guava`

### Case 3 - executionagent-runs-gpt54 / keras-team-keras

- owner_repo: `keras-team/keras`
- project_attempt_count: 3; classification: `failed_after_project_retries`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-system-deps;02-python-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-python-deps:failed | 03-build-test-prep:planned | 10-system-packages:succeeded | 20-python-runtime:succeeded | 30-python-deps:failed | 50-test-tooling:planned`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-python-deps 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-system-deps;02-python-deps;03-build-test-prep | 10-system-packages->20-python-runtime 相邻承接 | 20-python-runtime->30-python-deps 相邻承接`
- repair_blocks: `02-python-deps:failed, events=5, failed_events=3, repairs=0, repair_events=2, error=[pheragent] python dependencies Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (24.0) Col...; 30-python-deps:failed, events=21, failed_events=3, repairs=2, repair_events=13, error=[pheragent] repair: Ensure requirements-common.txt is copied for sanitized install [pheragent] repair: Copy requireme...`
- final_error: `block failed: 30-python-deps`
- run_dir: `executionagent-runs-gpt54/state/keras-team-keras/keras/runs/executionagent-keras`

### Case 4 - executionagent-runs-gpt54 / reactivex-rxjava

- owner_repo: `ReactiveX/RxJava`
- project_attempt_count: 3; classification: `failed_after_project_retries`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:failed | 03-build-test-prep:planned | 10-system-packages:succeeded | 20-java-runtime:succeeded | 21-gradle-toolchain:succeeded | 30-java-deps:failed | 50-test-tooling:planned`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 10-system-packages->20-java-runtime 相邻承接 | 20-java-runtime->21-gradle-toolchain 相邻承接 | 21-gradle-toolchain->30-java-deps 相邻承接`
- repair_blocks: `02-language-deps:failed, events=12, failed_events=3, repairs=0, repair_events=8, error=build1) ... Setting up libxrender1:amd64 (1:0.9.10-1.1build1) ... Setting up x11-common (1:7.7+23ubuntu3) ... invoke-...; 21-gradle-toolchain:succeeded, events=12, failed_events=3, repairs=1, repair_events=6; 30-java-deps:failed, events=22, failed_events=3, repairs=2, repair_events=14, error=To honour the JVM settings for this build a single-use Daemon process will be forked. For more on this, please refer ...`
- final_error: `block failed: 30-java-deps`
- run_dir: `executionagent-runs-gpt54/state/reactivex-rxjava/RxJava/runs/executionagent-rxjava`

### Case 6 - executionagent-runs-gpt54 / pandas-dev-pandas

- owner_repo: `pandas-dev/pandas`
- project_attempt_count: 3; classification: `failed_after_project_retries`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-python-runtime skip=01-system-deps;02-python-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-python-deps:succeeded | 03-build-test-prep:running | 20-python-runtime:succeeded | 30-python-deps:succeeded | 50-test-tooling:failed`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-python-deps 相邻承接 | 02-python-deps->03-build-test-prep 相邻承接 | 00-preflight->20-python-runtime 非相邻回溯，跳过 01-system-deps;02-python-deps;03-build-test-prep | 20-python-runtime->30-python-deps 相邻承接 | 30-python-deps->50-test-tooling 相邻承接`
- repair_blocks: `03-build-test-prep:running, events=4, failed_events=1, repairs=0, repair_events=1; 30-python-deps:succeeded, events=14, failed_events=0, repairs=1, repair_events=7; 50-test-tooling:failed, events=25, failed_events=5, repairs=1, repair_events=15, error=_inner_run return self.run(options, args) ^^^^^^^^^^^^^^^^^^^^^^^ File "/workspace/repo/.venv/lib/python3.12/site-pac...`
- final_error: `block failed: 50-test-tooling`
- run_dir: `executionagent-runs-gpt54/state/pandas-dev-pandas/pandas/runs/executionagent-pandas`

### Case 7 - executionagent-runs-gpt54 / django-django

- owner_repo: `django/django`
- project_attempt_count: 3; classification: `failed_after_project_retries`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-language-deps:succeeded | 03-build-test-prep:succeeded | 10-system-packages:succeeded | 20-python-runtime:succeeded | 21-node-runtime:succeeded | 30-python-deps:succeeded | 31-node-deps:succeeded | 50-test-tooling:running`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-language-deps 相邻承接 | 02-language-deps->03-build-test-prep 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 01-system-deps;02-language-deps;03-build-test-prep | 10-system-packages->20-python-runtime 相邻承接 | 20-python-runtime->21-node-runtime 相邻承接 | 21-node-runtime->30-python-deps 相邻承接 | 30-python-deps->31-node-deps 相邻承接 | 31-node-deps->50-test-tooling 相邻承接`
- repair_blocks: `03-build-test-prep:succeeded, events=13, failed_events=1, repairs=1, repair_events=4`
- final_error: `docker run failed:`
- run_dir: `executionagent-runs-gpt54/state/django-django/django/runs/executionagent-django`

### Case 9 - executionagent-runs-gpt54 / dmlc-xgboost

- owner_repo: `dmlc/xgboost`
- project_attempt_count: 3; classification: `failed_after_project_retries`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->10-system-packages skip=10-system-deps;20-language-deps;30-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 10-system-deps:succeeded | 20-language-deps:succeeded | 30-build-test-prep:failed | 10-system-packages:planned | 20-python-runtime:failed | 30-python-dependencies:planned | 40-native-build-config:planned`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->10-system-deps 相邻承接 | 10-system-deps->20-language-deps 相邻承接 | 20-language-deps->30-build-test-prep 相邻承接 | 00-preflight->10-system-packages 非相邻回溯，跳过 10-system-deps;20-language-deps;30-build-test-prep | 10-system-packages->20-python-runtime 相邻承接`
- repair_blocks: `30-build-test-prep:failed, events=13, failed_events=3, repairs=0, repair_events=9, error=fatal: detected dubious ownership in repository at '/workspace/repo' To add an exception for this directory, call: gi...; 10-system-packages:planned, events=18, failed_events=6, repairs=0, repair_events=13`
- final_error: `block failed: 20-python-runtime`
- run_dir: `executionagent-runs-gpt54/state/dmlc-xgboost/xgboost/runs/executionagent-xgboost`

### Case 13 - executionagent-runs-gpt54 / scikit-learn-scikit-learn

- owner_repo: `scikit-learn/scikit-learn`
- project_attempt_count: 3; classification: `failed_after_project_retries`
- strict_classification: `true_non_adjacent`
- recomputed_non_adjacent_edges: `00-preflight->20-python-runtime skip=01-system-deps;02-python-deps;03-build-test-prep`
- final_status_sequence: `00-preflight:succeeded | 01-system-deps:succeeded | 02-python-deps:succeeded | 03-build-test-prep:failed | 20-python-runtime:succeeded | 30-python-deps:succeeded | 50-test-tooling:failed`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->01-system-deps 相邻承接 | 01-system-deps->02-python-deps 相邻承接 | 02-python-deps->03-build-test-prep 相邻承接 | 00-preflight->20-python-runtime 非相邻回溯，跳过 01-system-deps;02-python-deps;03-build-test-prep | 20-python-runtime->30-python-deps 相邻承接 | 30-python-deps->50-test-tooling 相邻承接`
- repair_blocks: `03-build-test-prep:failed, events=10, failed_events=3, repairs=1, repair_events=5, error=Requirement already satisfied: Cython in ./.venv/lib/python3.12/site-packages (3.2.5) Collecting meson-python Downloa...; 30-python-deps:succeeded, events=14, failed_events=2, repairs=1, repair_events=7; 50-test-tooling:failed, events=21, failed_events=5, repairs=0, repair_events=13, error=Requirement already satisfied: meson-python in ./.venv/lib/python3.12/site-packages (0.20.0) Requirement already sati...`
- final_error: `block failed: 50-test-tooling`
- run_dir: `executionagent-runs-gpt54/state/scikit-learn-scikit-learn/scikit-learn/runs/executionagent-scikit-learn`

### Case 16 - projects-repo2run / instructlab

- owner_repo: ``
- project_attempt_count: 1; classification: `failed_in_project_run`
- strict_classification: `input_marked_non_adjacent_but_recomputed_previous_only`
- recomputed_non_adjacent_edges: `<严格重算无真实非相邻边>`
- final_status_sequence: `00-preflight:succeeded | 20-python-runtime:succeeded | 30-python-deps:failed | 50-test-tooling:planned`
- rollback_sequence: `BASE->00-preflight 基线工作区 | 00-preflight->20-python-runtime 相邻承接 | 20-python-runtime->30-python-deps 相邻承接`
- repair_blocks: `30-python-deps:failed, events=72, failed_events=28, repairs=7, repair_events=50, error=uirements.txt (line 9)) (3.5.2) Requirement already satisfied: llvmlite<0.48,>=0.47.0dev0 in ./.venv/lib/python3.12/s...`
- final_error: `block failed: 30-python-deps`
- run_dir: `projects-repo2run/instructlab/.pheragent/runs/repo2run-gpt-4o-20241120-instructlab`

