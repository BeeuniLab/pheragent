# 非相邻回溯案例时间线解析

Generated at: 2026-06-26T14:33:54.082429+00:00

数据口径：从每个项目目录下的 `blocks/*.json`、`executions.jsonl` 和 `logs/` 轨迹重放统计；没有使用会被覆盖的 results/summary 文件。时间顺序采用 `executions.jsonl` 行号；重复出现 `base-image/docker_build` 视为新的外层尝试 segment。

总体：输入 `rollback_non_adjacent_cases.csv` 有 16 条；按项目轨迹严格重算，15 条存在真实非相邻回溯边，1 条（projects-repo2run/instructlab）在原 CSV 中被标为非相邻，但实际 block order 下是相邻承接。

## 1. executionagent-runs-gpt4o / keras-team-keras

- 结果：ok=False；project_attempt_count=1；classification=failed_in_project_run。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-python-deps。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-python-deps:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-python-deps) | 10-system-packages->20-python-runtime:previous | 20-python-runtime->30-python-deps:previous。
- 最终错误摘要：ing database ... 30%\n(Reading database ... 35%\n(Reading database ... 40%\n(Reading database ... preflight-success

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `01-python-deps` | failed | 00-preflight | previous_block |  | 22/5/14 | ing database ... 30% (Reading database ... 35% (Reading database ... 40% (Reading database ... 45% (Reading database ... 50% (Reading dat... |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-python-deps | 3/0/0 |  |
| 20 | `20-python-runtime` | succeeded | 10-system-packages | previous_block |  | 3/0/0 |  |
| 30 | `30-python-deps` | failed | 20-python-runtime | previous_block |  | 16/4/12 | Looking in indexes: https://pypi.org/simple, https://download.pytorch.org/whl/cpu Ignoring tensorflow: markers 'sys_platform == "darwin"'... |
| 50 | `50-test-tooling` | planned | BASE/none | none |  | 0/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-keras-8434bdf7eb9d-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 66ba0723f2dd 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-da6f0e0875ca-001-base-workspace | [pheragent] preflight /workspace/repo Linux 66ba0723f2dd 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-5192bf6ea7de-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-38f75a221dd5-003-10-system-packages-success | [pheragent] ensuring python runtime Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (24.0) Collecting pip Downloading pi... |
| 1 | 12-27 | `30-python-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2=1 / llm_repair#2=1 | block#1=1 / repair#1=1 / probe#2=1 / llm_repair#2=1 | 12/11 | executionagent-gpt4o-keras-1f87d2a2a374-004-20-python-runtime-success | LLM repair returned no usable suggestions |
| 2 | 28-28 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 29-29 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-keras-8a87f0dbd68d-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 0efcc587a6bb 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 30-32 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-gpt4o-keras-774fd1a31f44-001-base-workspace | [pheragent] preflight /workspace/repo Linux 0efcc587a6bb 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 33-54 | `01-python-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / probe#1=127 / probe#1=0 / probe#1=1 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=1 / validation#2=0 / llm_probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0... | block#1=1 / probe#1=127 / probe#1=1 / block#2=1 / block#3=1 | 14/12 | executionagent-gpt4o-keras-4d5199288b19-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed ERROR: Could not open requirements file: [Errno 2] No such file or direct... |

## 2. executionagent-runs-gpt4o / google-guava

- 结果：ok=False；project_attempt_count=1；classification=failed_in_project_run。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-java-runtime skip=01-java-deps。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-java-deps:previous | 00-preflight->20-java-runtime:non_adjacent(skip=01-java-deps) | 20-java-runtime->30-java-deps:previous。
- 最终错误摘要：d package libmaven3-core-java. Preparing to unpack .../28-libmaven3-core-java_3.8.7-2_all.deb ... Unpacking libmaven3-core-java (3.8.7-2) ... Selecting previously unselected package libwagon-file-java. Preparing to un...

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `01-java-deps` | failed | 00-preflight | previous_block |  | 22/4/14 | d package libmaven3-core-java. Preparing to unpack .../28-libmaven3-core-java_3.8.7-2_all.deb ... Unpacking libmaven3-core-java (3.8.7-2)... |
| 20 | `20-java-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-java-deps | 13/5/7 |  |
| 30 | `30-java-deps` | failed | 20-java-runtime | previous_block |  | 5/4/1 | [pheragent] warming java dependencies [[1;31mERROR[m] Failed to execute goal [32morg.apache.maven.plugins:maven-dependency-plugin:3.8.... |
| 50 | `50-test-tooling` | planned | BASE/none | none |  | 0/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-guava-0beb4a213ac8-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 17a08bc326f9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-gpt4o-guava-3931051b6a64-001-base-workspace | [pheragent] preflight /workspace/repo Linux 17a08bc326f9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-18 | `20-java-runtime` | block#1=0 / validation#1=127 / llm_probe#1=0 / probe#1=0 / probe#1=2 / probe#1=127 / probe#1=127 / probe#1=127 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | validation#1=127 / probe#1=2 / probe#1=127 / probe#1=127 / probe#1=127 | 7/6 | executionagent-gpt4o-guava-60173be24458-002-00-preflight-success | /tmp/pheragent/blocks/20-java-runtime.sh: 31: java: not found /tmp/pheragent/blocks/20-java-runtime.sh: 32: mvn: not found |
| 1 | 19-23 | `30-java-deps` | block#1=1 / validation#1=0 / llm_probe#1=1 / llm_probe#2=1 / llm_repair#2=1 | block#1=1 / llm_probe#1=1 / llm_probe#2=1 / llm_repair#2=1 | 1/2 | executionagent-gpt4o-guava-3530e6af8aa4-003-20-java-runtime-repaired | LLM repair request failed: Connection error. |
| 2 | 24-24 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 25-25 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-gpt4o-guava-add9d05beb01-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux ffd1e0c40414 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 26-28 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-gpt4o-guava-c137b960fa2b-001-base-workspace | [pheragent] preflight /workspace/repo Linux ffd1e0c40414 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 29-50 | `01-java-deps` | block#1=127 / validation#1=127 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=1 / validation#2=0 / llm_probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2... | block#1=127 / validation#1=127 / block#2=1 / block#3=1 | 14/12 | executionagent-gpt4o-guava-4cebb941cb04-002-00-preflight-success | openjdk version "21.0.11" 2026-04-21 OpenJDK Runtime Environment (build 21.0.11+10-1-24.04.2-Ubuntu) OpenJDK 64-Bit Server VM (build 21.0.11+10-1-2... |

## 3. executionagent-runs-gpt54 / keras-team-keras

- 结果：ok=False；project_attempt_count=3；classification=failed_after_project_retries。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-system-deps;02-python-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-python-deps:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-system-deps,02-python-deps,03-build-test-prep) | 10-system-packages->20-python-runtime:previous | 20-python-runtime->30-python-deps:previous。
- 最终错误摘要：block failed: 30-python-deps

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-python-deps` | failed | 01-system-deps | previous_block |  | 5/3/2 | [pheragent] python dependencies Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (24.0) Collecting pip Download... |
| 3 | `03-build-test-prep` | planned | BASE/none | none |  | 0/0/0 |  |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 3/0/0 |  |
| 20 | `20-python-runtime` | succeeded | 10-system-packages | previous_block |  | 3/0/0 |  |
| 30 | `30-python-deps` | failed | 20-python-runtime | previous_block |  | 21/3/13 | [pheragent] repair: Ensure requirements-common.txt is copied for sanitized install [pheragent] repair: Copy requirements files for saniti... |
| 50 | `50-test-tooling` | planned | BASE/none | none |  | 0/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-keras-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 69d1ab542f42 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-keras-001-base-workspace | [pheragent] preflight /workspace/repo Linux 69d1ab542f42 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-keras-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-13 | `02-python-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / llm_repair#1=1 / llm_repair#2=1 | block#1=1 / llm_repair#1=1 / llm_repair#2=1 | 2/1 | executionagent-keras-003-01-system-deps-success | LLM repair returned no usable suggestions |
| 2 | 14-14 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 15-15 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-keras-473a82a8f2c0-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux cc8f8df2dc98 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 16-18 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-keras-9b71272e04c4-001-base-workspace | [pheragent] preflight /workspace/repo Linux cc8f8df2dc98 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 19-21 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-keras-79891575e969-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 22-24 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-keras-e8ba04970ec0-003-10-system-packages-success | [pheragent] ensuring python runtime Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (24.0) Collecting pip Downloading pi... |
| 2 | 25-45 | `30-python-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=1 / validation#2=0 / llm_probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 /... | block#1=1 / block#2=1 / block#3=1 | 13/11 | executionagent-keras-6ab04e4a84e6-004-20-python-runtime-success | ERROR: Could not open requirements file: [Errno 2] No such file or directory: '/tmp/pheragent-requirements-sanitized/requirements-common.txt' |

## 4. executionagent-runs-gpt54 / reactivex-rxjava

- 结果：ok=False；project_attempt_count=3；classification=failed_after_project_retries。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 10-system-packages->20-java-runtime:previous | 20-java-runtime->21-gradle-toolchain:previous | 21-gradle-toolchain->30-java-deps:previous。
- 最终错误摘要：block failed: 30-java-deps

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-language-deps` | failed | 01-system-deps | previous_block |  | 12/3/8 | build1) ... Setting up libxrender1:amd64 (1:0.9.10-1.1build1) ... Setting up x11-common (1:7.7+23ubuntu3) ... invoke-rc.d: could not dete... |
| 3 | `03-build-test-prep` | planned | BASE/none | none |  | 0/0/0 |  |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 3/0/0 |  |
| 20 | `20-java-runtime` | succeeded | 10-system-packages | previous_block |  | 3/0/0 |  |
| 21 | `21-gradle-toolchain` | succeeded | 20-java-runtime | previous_block |  | 12/3/6 |  |
| 30 | `30-java-deps` | failed | 21-gradle-toolchain | previous_block |  | 22/3/14 | To honour the JVM settings for this build a single-use Daemon process will be forked. For more on this, please refer to https://docs.grad... |
| 50 | `50-test-tooling` | planned | BASE/none | none |  | 0/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rxjava-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux cbfadbd0ec49 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rxjava-001-base-workspace | [pheragent] preflight /workspace/repo Linux cbfadbd0ec49 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rxjava-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-20 | `02-language-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_probe#2=0 / llm_repair#2=0 / repair#2=1 | block#1=1 / repair#1=1 / repair#2=1 | 8/6 | executionagent-rxjava-003-01-system-deps-success | debconf: delaying package configuration, since apt-utils is not installed FAILURE: Build failed with an exception. * What went wrong: A problem occ... |
| 2 | 21-21 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 22-22 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rxjava-696b105bc148-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 16d6d0e64b7c 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 23-25 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rxjava-7e0d9b86490c-001-base-workspace | [pheragent] preflight /workspace/repo Linux 16d6d0e64b7c 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 26-28 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rxjava-77789ab82e47-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 29-31 | `20-java-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rxjava-024883b263c0-003-10-system-packages-success | openjdk version "17.0.19" 2026-04-21 OpenJDK Runtime Environment (build 17.0.19+10-1-24.04.2-Ubuntu) OpenJDK 64-Bit Server VM (build 17.0.19+10-1-2... |
| 2 | 32-43 | `21-gradle-toolchain` | block#1=None / validation#1=0 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=127 / probe#1=2 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | block#1=None / probe#1=127 / probe#1=2 | 6/5 | executionagent-rxjava-65f75f02b2e9-004-20-java-runtime-success | ls -l ./gradlew // ls -l . // command -v gradle && gradle --version // ls -l gradle.zip // chmod +x ./gradlew && ./gradlew --version |
| 2 | 44-65 | `30-java-deps` | block#1=0 / validation#1=1 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=1 / llm_probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 /... | validation#1=1 / validation#2=1 / validation#3=1 | 14/11 | executionagent-rxjava-273285059abc-005-21-gradle-toolchain-repaired | FAILURE: Build failed with an exception. * What went wrong: A problem occurred configuring root project 'rxjava'. > Failed to calculate the value o... |

## 5. executionagent-runs-gpt54 / nestjs-nest

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-node-runtime skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 00-preflight->20-node-runtime:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 20-node-runtime->30-node-deps:previous | 30-node-deps->50-test-tooling:previous。
- 最终错误摘要：ng database ... 40% (Reading database ... 45% (Reading database ... 50% (Reading database ... 55% (Reading database ... 60% (Reading database ... 65% (Reading database ... 70% (Reading database ... 75% (Reading databa...

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 9/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-language-deps` | failed | 01-system-deps | previous_block |  | 13/5/7 | ng database ... 40% (Reading database ... 45% (Reading database ... 50% (Reading database ... 55% (Reading database ... 60% (Reading data... |
| 3 | `03-build-test-prep` | planned | BASE/none | none |  | 0/0/0 |  |
| 20 | `20-node-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |  |
| 30 | `30-node-deps` | succeeded | 20-node-runtime | previous_block |  | 16/2/7 |  |
| 50 | `50-test-tooling` | succeeded | 30-node-deps | previous_block |  | 6/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-nest-204173cf70cf-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux f390fd6e77f9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-nest-aaa7b7fa06e7-001-base-workspace | [pheragent] preflight /workspace/repo Linux f390fd6e77f9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-nest-502f14e79b58-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-21 | `02-language-deps` | block#1=1 / validation#1=1 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_probe#2=0 / llm_repair#2=0 / repair#2=0 / block#2=1 / validation#2=1 | block#1=1 / validation#1=1 / repair#1=1 / block#2=1 / validation#2=1 | 7/5 | executionagent-nest-78adfd561a2e-003-01-system-deps-success | npm ERR! code ERESOLVE npm ERR! ERESOLVE could not resolve npm ERR! npm ERR! While resolving: @nestjs/apollo@13.2.1 npm ERR! Found: @apollo/server@... |
| 2 | 22-22 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 23-23 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-nest-1b493427bb16-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 277780bc9e3f 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 24-26 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace | [pheragent] preflight /workspace/repo Linux 277780bc9e3f 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 27-29 | `20-node-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-nest-5ebee148b4f4-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 30-42 | `30-node-deps` | block#1=1 / validation#1=1 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | block#1=1 / validation#1=1 | 7/6 | executionagent-nest-5be1f63093d7-003-20-node-runtime-success | npm ERR! code ERESOLVE npm ERR! ERESOLVE could not resolve npm ERR! npm ERR! While resolving: @nestjs/apollo@13.2.1 npm ERR! Found: @apollo/server@... |
| 2 | 43-45 | `50-test-tooling` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-nest-543af816f6bf-004-30-node-deps-repaired | [pheragent] preparing node test tooling v18.19.1 9.2.0 |
| 2 | 46-48 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace | [pheragent] preflight /workspace/repo Linux 262ea7e2036a 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 49-51 | `20-node-runtime` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 52-54 | `30-node-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace | pported engine { npm WARN EBADENGINE package: '@azure/core-xml@1.5.0', npm WARN EBADENGINE required: { node: '>=20.0.0' }, npm WARN EBADENGINE curr... |
| 2 | 55-57 | `50-test-tooling` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-nest-8cb1dc6727b0-001-base-workspace | [pheragent] preparing node test tooling v18.19.1 9.2.0 |

## 6. executionagent-runs-gpt54 / pandas-dev-pandas

- 结果：ok=False；project_attempt_count=3；classification=failed_after_project_retries。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-python-runtime skip=01-system-deps;02-python-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-python-deps:previous | 02-python-deps->03-build-test-prep:previous | 00-preflight->20-python-runtime:non_adjacent(skip=01-system-deps,02-python-deps,03-build-test-prep) | 20-python-runtime->30-python-deps:previous | 30-python-deps->50-test-tooling:previous。
- 最终错误摘要：block failed: 50-test-tooling

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-python-deps` | succeeded | 01-system-deps | previous_block |  | 3/0/0 |  |
| 3 | `03-build-test-prep` | running | 02-python-deps | previous_block |  | 4/1/1 |  |
| 20 | `20-python-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 3/0/0 |  |
| 30 | `30-python-deps` | succeeded | 20-python-runtime | previous_block |  | 14/0/7 |  |
| 50 | `50-test-tooling` | failed | 30-python-deps | previous_block |  | 25/5/15 | _inner_run return self.run(options, args) ^^^^^^^^^^^^^^^^^^^^^^^ File "/workspace/repo/.venv/lib/python3.12/site-packages/pip/_internal/... |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pandas-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 2907e4bc471b 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pandas-001-base-workspace | [pheragent] preflight /workspace/repo Linux 2907e4bc471b 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pandas-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `02-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pandas-003-01-system-deps-success | WARNING: pandas 0+unknown does not provide the extra 'dev' |
| 1 | 12-15 | `03-build-test-prep` | block#1=0 / validation#1=4 / llm_probe#1=0 / llm_repair#1=0 | validation#1=4 | 1/1 | executionagent-pandas-004-02-python-deps-success | --- raw_llm_response --- {"repairs":[{"title":"install ninja for pandas editable loader rebuild","command":"sh -lc 'export DEBIAN_FRONTEND=noninter... |
| 2 | 16-16 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 17-17 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pandas-8c6326d75b3f-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 851a7744ee68 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 18-20 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pandas-8bd8ed53c116-001-base-workspace | [pheragent] preflight /workspace/repo Linux 851a7744ee68 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 21-23 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pandas-871d808fb840-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 24-26 | `30-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pandas-ac74ebd1c625-003-20-python-runtime-success | error: subprocess-exited-with-error × Preparing editable metadata (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [16 lines of output... |
| 2 | 27-28 | `50-test-tooling` | block#1=0 / validation#1=4 | validation#1=4 | 0/0 | executionagent-pandas-cfecb32c0351-004-30-python-deps-success | ImportError while loading conftest '/workspace/repo/pandas/conftest.py'. pandas/__init__.py:13: in <module> raise ImportError( E ImportError: Unabl... |
| 2 | 29-39 | `30-python-deps` | llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 |  | 7/6 | executionagent-pandas-ac74ebd1c625-003-20-python-runtime-success | .venv/bin/python -c "import numpy; print(numpy.__version__)" 2>&1 // echo '[pheragent] numpy not installed' // .venv/bin/pip list // grep numpy req... |
| 2 | 40-62 | `50-test-tooling` | block#2=0 / validation#2=4 / block#1=0 / validation#1=4 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=4 / llm_probe#2=0 / probe#2=0 / probe#... | validation#2=4 / validation#1=4 / validation#2=4 / repair#2=2 | 15/12 | executionagent-pandas-fe8ee60d9235-005-30-python-deps-repaired | ERROR: Exception: Traceback (most recent call last): File "/workspace/repo/.venv/lib/python3.12/site-packages/pip/_internal/cli/base_command.py", l... |

## 7. executionagent-runs-gpt54 / django-django

- 结果：ok=False；project_attempt_count=3；classification=failed_after_project_retries。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 02-language-deps->03-build-test-prep:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 10-system-packages->20-python-runtime:previous | 20-python-runtime->21-node-runtime:previous | 21-node-runtime->30-python-deps:previous | 30-python-deps->31-node-deps:previous | 31-node-deps->50-test-tooling:previous。
- 最终错误摘要：docker run failed:

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 9/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 6/0/0 |  |
| 2 | `02-language-deps` | succeeded | 01-system-deps | previous_block |  | 6/0/0 |  |
| 3 | `03-build-test-prep` | succeeded | 02-language-deps | previous_block |  | 13/1/4 |  |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 3/0/0 |  |
| 20 | `20-python-runtime` | succeeded | 10-system-packages | previous_block |  | 3/0/0 |  |
| 21 | `21-node-runtime` | succeeded | 20-python-runtime | previous_block |  | 3/0/0 |  |
| 30 | `30-python-deps` | succeeded | 21-node-runtime | previous_block |  | 3/0/0 |  |
| 31 | `31-node-deps` | succeeded | 30-python-deps | previous_block |  | 3/0/0 |  |
| 50 | `50-test-tooling` | running | 31-node-deps | previous_block |  | 3/1/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-django-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 17b47bac72c8 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-001-base-workspace | [pheragent] preflight /workspace/repo Linux 17b47bac72c8 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `02-language-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-003-01-system-deps-success | WARNING: django 6.1 does not provide the extra 'dev' |
| 1 | 12-21 | `03-build-test-prep` | block#1=0 / validation#1=2 / llm_probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | validation#1=2 | 4/3 | executionagent-django-004-02-language-deps-success | cd /workspace/repo && sed -n '1,220p' pyproject.toml && printf '\n--- tox.ini ---\n' && sed -n '1,220p' tox.ini 2>/dev/null // true // cd /workspac... |
| 1 | 22-24 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-django-001-base-workspace | [pheragent] preflight /workspace/repo Linux 267319af83ad 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 25-27 | `01-system-deps` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-django-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 28-30 | `02-language-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-django-001-base-workspace | WARNING: django 6.1 does not provide the extra 'dev' |
| 1 | 31-33 | `03-build-test-prep` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-django-001-base-workspace | [pheragent] repair: Use Django's own test runner for lightweight validation [pheragent] build/test prep pytest 9.1.1 |
| 1 | 34-34 | `oracle` | oracle#1=1 | oracle#1=1 | 0/0 | executionagent-django-006-final-clean-replay-clean-replay | Traceback (most recent call last): File "/workspace/repo/tests/runtests.py", line 17, in <module> import django ModuleNotFoundError: No module name... |
| 2 | 35-35 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 36-36 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-django-c09562525356-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 4a7e16d50ccd 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 37-39 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-e6f50ee84150-001-base-workspace | [pheragent] preflight /workspace/repo Linux 4a7e16d50ccd 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 40-42 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-984fd7bb8bbf-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 43-45 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-2bba1975674a-003-10-system-packages-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 46-48 | `21-node-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-23dd387db5ad-004-20-python-runtime-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 49-51 | `30-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-2fe185f7b5d6-005-21-node-runtime-success | WARNING: django 6.1 does not provide the extra 'dev' |
| 2 | 52-54 | `31-node-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-django-0d23027cacc7-006-30-python-deps-success | npm WARN deprecated inflight@1.0.6: This module is not supported, and leaks memory. Do not use it. Check out lru-cache if you want a good and teste... |
| 2 | 55-57 | `50-test-tooling` | block#1=0 / validation#1=2 / llm_probe#1=0 | validation#1=2 | 0/1 | executionagent-django-776b5fa1ddaa-007-31-node-deps-success | --- raw_llm_response --- { "probes": [ { "title": "Check pytest collection error details", "command": "head -40 /workspace/repo/.venv/lib/python3.1... |

## 8. executionagent-runs-gpt54 / mermaid-js-mermaid

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-node-runtime skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 00-preflight->20-node-runtime:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 20-node-runtime->30-node-deps:previous | 30-node-deps->50-test-tooling:previous。
- 最终错误摘要：: packages/examples/dist/mermaid-examples.core.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare: packages/examples/dist/mermaid-examples.esm.mjs 15.7kb . prepare: packages/examples/dist/mermaid-examples.esm.mjs.map 2...

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 9/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-language-deps` | failed | 01-system-deps | previous_block |  | 9/5/4 | : packages/examples/dist/mermaid-examples.core.mjs.map 24.8kb . prepare: ⚡ Done in 6ms . prepare: packages/examples/dist/mermaid-examples... |
| 3 | `03-build-test-prep` | planned | BASE/none | none |  | 0/0/0 |  |
| 20 | `20-node-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |  |
| 30 | `30-node-deps` | succeeded | 20-node-runtime | previous_block |  | 6/0/0 |  |
| 50 | `50-test-tooling` | succeeded | 30-node-deps | previous_block |  | 6/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-mermaid-68c7ab009c9b-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 7513060a48ed 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-mermaid-20e020656b9a-001-base-workspace | [pheragent] preflight /workspace/repo Linux 7513060a48ed 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-mermaid-5ed08c0d3cc4-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-17 | `02-language-deps` | block#1=1 / validation#1=1 / llm_probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_repair#2=0 / repair#2=0 / block#2=1 / validation#2=1 | block#1=1 / validation#1=1 / repair#1=1 / block#2=1 / validation#2=1 | 4/1 | executionagent-mermaid-fc59da1de26e-003-01-system-deps-success | ERROR: This version of pnpm requires at least Node.js v22.13 The current version of Node.js is v18.19.1 Visit https://r.pnpm.io/comp to see the lis... |
| 2 | 18-18 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 19-19 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-mermaid-526866b2ab14-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 9947a9fd62c9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 20-22 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace | [pheragent] preflight /workspace/repo Linux 9947a9fd62c9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 23-25 | `20-node-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-mermaid-e23b8e3f247d-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 26-28 | `30-node-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-mermaid-ed79553de2ff-003-20-node-runtime-success | m/chunk-6PHMZWEM.mjs 196.9kb . prepare: ...ges/mermaid/dist/chunks/mermaid.esm/sequenceDiagram-MB3FELIF.mjs 167.0kb . prepare: packages/mermaid/dis... |
| 2 | 29-31 | `50-test-tooling` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-mermaid-492cc5091570-004-30-node-deps-success | [pheragent] preparing node test tooling v18.19.1 9.2.0 9.15.9 |
| 2 | 32-34 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace | [pheragent] preflight /workspace/repo Linux 3db4c648979c 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 35-37 | `20-node-runtime` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 38-40 | `30-node-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace | st/chunks/mermaid.esm.min/blockDiagram-MFEFEJY7.mjs 70.4kb . prepare: packages/mermaid/dist/chunks/mermaid.esm.min/c4Diagram-Q5SP5FFD.mjs 68.9kb . ... |
| 2 | 41-43 | `50-test-tooling` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-mermaid-daf881e1bb0a-001-base-workspace | [pheragent] preparing node test tooling v18.19.1 9.2.0 9.15.9 |

## 9. executionagent-runs-gpt54 / dmlc-xgboost

- 结果：ok=False；project_attempt_count=3；classification=failed_after_project_retries。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=10-system-deps;20-language-deps;30-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->10-system-deps:previous | 10-system-deps->20-language-deps:previous | 20-language-deps->30-build-test-prep:previous | 00-preflight->10-system-packages:non_adjacent(skip=10-system-deps,20-language-deps,30-build-test-prep) | 10-system-packages->20-python-runtime:previous。
- 最终错误摘要：block failed: 20-python-runtime

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `10-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `20-language-deps` | succeeded | 10-system-deps | previous_block |  | 3/0/0 |  |
| 3 | `30-build-test-prep` | failed | 20-language-deps | previous_block |  | 13/3/9 | fatal: detected dubious ownership in repository at '/workspace/repo' To add an exception for this directory, call: git config --global --... |
| 10 | `10-system-packages` | planned | 00-preflight | non_adjacent_block | 10-system-deps;20-language-deps;30-build-test-prep | 18/6/13 |  |
| 20 | `20-python-runtime` | failed | 10-system-packages | previous_block |  | 2/2/0 |  |
| 30 | `30-python-dependencies` | planned | BASE/none | none |  | 0/0/0 |  |
| 40 | `40-native-build-config` | planned | BASE/none | none |  | 0/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-xgboost-975e57dcc926-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux b504687a9645 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-xgboost-bf82a28430e8-001-base-workspace | [pheragent] preflight /workspace/repo Linux b504687a9645 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `10-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-xgboost-4fc94ddada9f-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `20-language-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-xgboost-1f18ea28c8e0-003-10-system-deps-success | [pheragent] python dependencies Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (24.0) Collecting pip Downloading pip-26... |
| 1 | 12-24 | `30-build-test-prep` | block#1=0 / validation#1=1 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_probe#2=0 / llm_repair#2=0 / repair#2=128 | validation#1=1 / repair#1=1 / repair#2=128 | 9/7 | executionagent-xgboost-c948aa1a8cf5-004-20-language-deps-success | fatal: detected dubious ownership in repository at '/workspace/repo' To add an exception for this directory, call: git config --global --add safe.d... |
| 2 | 25-25 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 26-26 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-xgboost-334496418e9d-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 5aea2f7f65c9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 27-29 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-xgboost-270c9589e246-001-base-workspace | [pheragent] preflight /workspace/repo Linux 5aea2f7f65c9 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 30-32 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-xgboost-5807e5cb28d5-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 33-34 | `20-python-runtime` | block#1=1 / validation#1=1 | block#1=1 / validation#1=1 | 0/0 | executionagent-xgboost-1dbea192fff4-003-10-system-packages-success | /workspace/repo/.venv/bin/python: No module named pip |
| 2 | 35-49 | `10-system-packages` | llm_probe#1=0 / probe#1=1 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=127 / llm_probe#2=0 / probe#2=2 / probe#2=2 / probe#2=0 / probe#2=1 / probe#2=0 / llm_repair#2=0 / repair#2=127 | probe#1=1 / repair#1=127 / probe#2=2 / probe#2=2 / probe#2=1 / repair#2=127 | 13/11 | executionagent-xgboost-5807e5cb28d5-002-00-preflight-success | dpkg -l / grep -E '^ii' / grep python3.12-venv // dpkg -l / grep -E '^ii' / grep python3-venv // find /usr/lib/python3.12 -name venv -type d -maxde... |

## 10. executionagent-runs-gpt54 / apache-rocketmq

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 02-language-deps->03-build-test-prep:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 10-system-packages->20-java-runtime:previous | 20-java-runtime->30-java-deps:previous | 30-java-deps->50-test-tooling:previous。

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 12/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 6/0/0 |  |
| 2 | `02-language-deps` | succeeded | 01-system-deps | previous_block |  | 6/0/0 |  |
| 3 | `03-build-test-prep` | succeeded | 02-language-deps | previous_block |  | 6/0/0 |  |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |  |
| 20 | `20-java-runtime` | succeeded | 10-system-packages | previous_block |  | 6/0/0 |  |
| 30 | `30-java-deps` | succeeded | 20-java-runtime | previous_block |  | 6/0/0 |  |
| 50 | `50-test-tooling` | succeeded | 30-java-deps | previous_block |  | 6/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 DONE 0.0s #1 [internal... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rocketmq-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 6c7a22751011 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace | [pheragent] preflight /workspace/repo Linux 6c7a22751011 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed openjdk version "17.0.19" 2026-04-21 OpenJDK Runtime Environment (build 1... |
| 1 | 9-11 | `02-language-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-003-01-system-deps-success | Plugin Dependency Resolved: plexus-container-default-1.5.5.jar [INFO] Plugin Dependency Resolved: plexus-interactivity-api-1.0-alpha-6.jar [INFO] P... |
| 1 | 12-14 | `03-build-test-prep` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-004-02-language-deps-success | WARNING: A terminally deprecated method in java.lang.System has been called WARNING: System::setSecurityManager has been called by org.apache.tools... |
| 1 | 15-17 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace | [pheragent] preflight /workspace/repo Linux 735fffcc27a4 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 18-20 | `01-system-deps` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed openjdk version "17.0.19" 2026-04-21 OpenJDK Runtime Environment (build 1... |
| 1 | 21-23 | `02-language-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace | Plugin Dependency Resolved: plexus-container-default-1.5.5.jar [INFO] Plugin Dependency Resolved: plexus-interactivity-api-1.0-alpha-6.jar [INFO] P... |
| 1 | 24-26 | `03-build-test-prep` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-rocketmq-001-base-workspace | WARNING: A terminally deprecated method in java.lang.System has been called WARNING: System::setSecurityManager has been called by org.apache.tools... |
| 1 | 27-27 | `oracle` | oracle#1=1 | oracle#1=1 | 0/0 | executionagent-rocketmq-006-final-clean-replay-clean-replay | n.run(SSLEngineImpl.java:1278) at java.base/sun.security.ssl.SSLEngineImpl$DelegatedTask$DelegatedAction.run(SSLEngineImpl.java:1265) at java.base/... |
| 2 | 28-28 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 DONE 0.0s #1 [internal... |
| 2 | 29-29 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-rocketmq-4d3a285fa71e-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 9bd980a278b1 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 30-32 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace | [pheragent] preflight /workspace/repo Linux 9bd980a278b1 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 33-35 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-e6d11140151a-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 36-38 | `20-java-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-06a8682b834d-003-10-system-packages-success | openjdk version "11.0.31" 2026-04-21 OpenJDK Runtime Environment (build 11.0.31+11-post-1ubuntu1-24.04.2-Ubuntu) OpenJDK 64-Bit Server VM (build 11... |
| 2 | 39-41 | `30-java-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-f63ee0d64f98-004-20-java-runtime-success | [pheragent] warming java dependencies |
| 2 | 42-44 | `50-test-tooling` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-rocketmq-08bdf7981c41-005-30-java-deps-success | [pheragent] preparing java test tooling [java] JVM args ignored when same JVM is used. [java] JVM args ignored when same JVM is used. [java] JVM ar... |
| 2 | 45-47 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace | [pheragent] preflight /workspace/repo Linux aeb45a3e2065 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 48-50 | `10-system-packages` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 51-53 | `20-java-runtime` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace | openjdk version "11.0.31" 2026-04-21 OpenJDK Runtime Environment (build 11.0.31+11-post-1ubuntu1-24.04.2-Ubuntu) OpenJDK 64-Bit Server VM (build 11... |
| 2 | 54-56 | `30-java-deps` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace | [pheragent] warming java dependencies |
| 2 | 57-59 | `50-test-tooling` | clean_replay#5=0 / clean_replay_validation#5=0 / clean_replay_finalize#5=0 |  | 0/0 | executionagent-rocketmq-4b110f2f5ab9-001-base-workspace | [pheragent] preparing java test tooling [java] JVM args ignored when same JVM is used. [java] JVM args ignored when same JVM is used. [java] JVM ar... |

## 11. executionagent-runs-gpt54 / facebook-react

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-node-runtime skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 02-language-deps->03-build-test-prep:previous | 00-preflight->20-node-runtime:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 20-node-runtime->30-node-deps:previous | 30-node-deps->50-test-tooling:previous。

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 12/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 6/0/0 |  |
| 2 | `02-language-deps` | succeeded | 01-system-deps | previous_block |  | 6/0/0 |  |
| 3 | `03-build-test-prep` | succeeded | 02-language-deps | previous_block |  | 6/0/0 |  |
| 20 | `20-node-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |  |
| 30 | `30-node-deps` | succeeded | 20-node-runtime | previous_block |  | 6/0/0 |  |
| 50 | `50-test-tooling` | succeeded | 30-node-deps | previous_block |  | 6/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-react-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux dff7970df6f2 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-001-base-workspace | [pheragent] preflight /workspace/repo Linux dff7970df6f2 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `02-language-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-003-01-system-deps-success | warning Resolution field "jsdom@22.1.0" is incompatible with requested version "jsdom@^20.0.0" warning " > eslint-plugin-ft-flow@2.0.3" has unmet p... |
| 1 | 12-14 | `03-build-test-prep` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-004-02-language-deps-success | v18.19.1 9.2.0 1.22.22 package compiler-package |
| 1 | 15-17 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-react-001-base-workspace | [pheragent] preflight /workspace/repo Linux 42f2a1bdc6ea 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 18-20 | `01-system-deps` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-react-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 21-23 | `02-language-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-react-001-base-workspace | warning Resolution field "jsdom@22.1.0" is incompatible with requested version "jsdom@^20.0.0" warning " > eslint-plugin-ft-flow@2.0.3" has unmet p... |
| 1 | 24-26 | `03-build-test-prep` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-react-001-base-workspace | v18.19.1 9.2.0 1.22.22 package compiler-package |
| 1 | 27-29 | `oracle` | oracle#1=0 / oracle#2=0 / oracle#3=1 | oracle#3=1 | 0/0 | executionagent-react-006-final-clean-replay-clean-replay | eactProfilerComponent-test.internal.js PASS packages/react-test-renderer/src/__tests__/ReactTestRenderer-test.js PASS packages/react-dom/src/__test... |
| 2 | 30-30 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 31-31 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-react-5126dee87285-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 829d26e46cf2 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 32-34 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace | [pheragent] preflight /workspace/repo Linux 829d26e46cf2 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 35-37 | `20-node-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-422e91878e6e-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 38-40 | `30-node-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-92ff00afaf62-003-20-node-runtime-success | warning Resolution field "jsdom@22.1.0" is incompatible with requested version "jsdom@^20.0.0" warning " > eslint-plugin-ft-flow@2.0.3" has unmet p... |
| 2 | 41-43 | `50-test-tooling` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-react-871222bc8553-004-30-node-deps-success | [pheragent] preparing node test tooling v18.19.1 9.2.0 1.22.22 |
| 2 | 44-46 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace | [pheragent] preflight /workspace/repo Linux 9f4e848daf7e 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 47-49 | `20-node-runtime` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 50-52 | `30-node-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace | warning Resolution field "jsdom@22.1.0" is incompatible with requested version "jsdom@^20.0.0" warning " > eslint-plugin-ft-flow@2.0.3" has unmet p... |
| 2 | 53-55 | `50-test-tooling` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-react-034eacff459a-001-base-workspace | [pheragent] preparing node test tooling v18.19.1 9.2.0 1.22.22 |

## 12. executionagent-runs-gpt54 / scipy-scipy

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-system-deps;02-python-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-python-deps:previous | 02-python-deps->03-build-test-prep:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-system-deps,02-python-deps,03-build-test-prep) | 10-system-packages->20-python-runtime:previous | 20-python-runtime->30-python-deps:previous | 30-python-deps->50-test-tooling:previous。
- 最终错误摘要：: No module named 'scipy' During handling of the above exception, another exception occurred: Traceback (most recent call last): File "<frozen runpy>", line 198, in _run_module_as_main File "<frozen runpy>", line 88, ...

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 9/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-python-deps` | succeeded | 01-system-deps | previous_block |  | 3/0/0 |  |
| 3 | `03-build-test-prep` | failed | 02-python-deps | previous_block |  | 12/3/5 | : No module named 'scipy' During handling of the above exception, another exception occurred: Traceback (most recent call last): File "<f... |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 6/0/0 |  |
| 20 | `20-python-runtime` | succeeded | 10-system-packages | previous_block |  | 6/0/0 |  |
| 30 | `30-python-deps` | succeeded | 20-python-runtime | previous_block |  | 6/0/0 |  |
| 50 | `50-test-tooling` | succeeded | 30-python-deps | previous_block |  | 6/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scipy-3de87abd430b-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 03bc62f24408 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-050ae481e289-001-base-workspace | [pheragent] preflight /workspace/repo Linux 03bc62f24408 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-89f3c9d7b3dc-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `02-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-a937a9bb3ade-003-01-system-deps-success | error: subprocess-exited-with-error × Preparing editable metadata (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [38 lines of output... |
| 1 | 12-23 | `03-build-test-prep` | block#1=0 / validation#1=1 / llm_probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=1 / llm_repair#2=0 / repair_prep#2=0 / repair#2=0 / block#3=0 / validation#3=1 | validation#1=1 / validation#2=1 / validation#3=1 | 5/1 | executionagent-scipy-ea5492cfd2dc-004-02-python-deps-success | Traceback (most recent call last): File "/workspace/repo/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py", line 2232, in apply_warnin... |
| 2 | 24-24 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 25-25 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scipy-fc9f94497f5e-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 5e4e23516f4a 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 26-28 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace | [pheragent] preflight /workspace/repo Linux 5e4e23516f4a 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 29-31 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-57b5802152b5-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 32-34 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-ac40a63d2494-003-10-system-packages-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 35-37 | `30-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-5a0b93960389-004-20-python-runtime-success | error: subprocess-exited-with-error × Preparing editable metadata (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [16 lines of output... |
| 2 | 38-40 | `50-test-tooling` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scipy-2729ab86307e-005-30-python-deps-success | Traceback (most recent call last): File "/workspace/repo/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py", line 2232, in apply_warnin... |
| 2 | 41-43 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace | [pheragent] preflight /workspace/repo Linux 34eeedee802f 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 44-46 | `10-system-packages` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 47-49 | `20-python-runtime` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 50-52 | `30-python-deps` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace | error: subprocess-exited-with-error × Preparing editable metadata (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [16 lines of output... |
| 2 | 53-55 | `50-test-tooling` | clean_replay#5=0 / clean_replay_validation#5=0 / clean_replay_finalize#5=0 |  | 0/0 | executionagent-scipy-0b2618413103-001-base-workspace | Traceback (most recent call last): File "/workspace/repo/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py", line 2232, in apply_warnin... |

## 13. executionagent-runs-gpt54 / scikit-learn-scikit-learn

- 结果：ok=False；project_attempt_count=3；classification=failed_after_project_retries。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-python-runtime skip=01-system-deps;02-python-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-python-deps:previous | 02-python-deps->03-build-test-prep:previous | 00-preflight->20-python-runtime:non_adjacent(skip=01-system-deps,02-python-deps,03-build-test-prep) | 20-python-runtime->30-python-deps:previous | 30-python-deps->50-test-tooling:previous。
- 最终错误摘要：block failed: 50-test-tooling

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 6/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-python-deps` | succeeded | 01-system-deps | previous_block |  | 3/0/0 |  |
| 3 | `03-build-test-prep` | failed | 02-python-deps | previous_block |  | 10/3/5 | Requirement already satisfied: Cython in ./.venv/lib/python3.12/site-packages (3.2.5) Collecting meson-python Downloading meson_python-0.... |
| 20 | `20-python-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-python-deps;03-build-test-prep | 3/0/0 |  |
| 30 | `30-python-deps` | succeeded | 20-python-runtime | previous_block |  | 14/2/7 |  |
| 50 | `50-test-tooling` | failed | 30-python-deps | previous_block |  | 21/5/13 | Requirement already satisfied: meson-python in ./.venv/lib/python3.12/site-packages (0.20.0) Requirement already satisfied: meson>=1.2.3 ... |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scikit-learn-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 55bef814cd22 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scikit-learn-001-base-workspace | [pheragent] preflight /workspace/repo Linux 55bef814cd22 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scikit-learn-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `02-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scikit-learn-003-01-system-deps-success | WARNING: scikit-learn 1.9.dev0 does not provide the extra 'dev' |
| 1 | 12-21 | `03-build-test-prep` | block#1=0 / validation#1=1 / llm_probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=4 / llm_repair#2=0 / repair_prep#2=0 / repair#2=1 | validation#1=1 / validation#2=4 / repair#2=1 | 5/1 | executionagent-scikit-learn-004-02-python-deps-success | error: subprocess-exited-with-error × Preparing editable metadata (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [2 lines of output]... |
| 2 | 22-22 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 23-23 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-scikit-learn-dc2b73c790d0-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 825671f0447b 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 24-26 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scikit-learn-fa71d0da7a59-001-base-workspace | [pheragent] preflight /workspace/repo Linux 825671f0447b 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 27-29 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scikit-learn-463def3e485d-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 30-32 | `30-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-scikit-learn-2b7599eefe93-003-20-python-runtime-success | error: subprocess-exited-with-error × Preparing editable metadata (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [16 lines of output... |
| 2 | 33-34 | `50-test-tooling` | block#1=0 / validation#1=4 | validation#1=4 | 0/0 | executionagent-scikit-learn-6a24f113347a-004-30-python-deps-success | ImportError while loading conftest '/workspace/repo/sklearn/conftest.py'. sklearn/__init__.py:69: in <module> from sklearn import __check_build, _d... |
| 2 | 35-45 | `30-python-deps` | llm_probe#1=0 / probe#1=0 / probe#1=1 / probe#1=1 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | probe#1=1 / probe#1=1 | 7/6 | executionagent-scikit-learn-2b7599eefe93-003-20-python-runtime-success | command -v python3 && python3 --version // .venv/bin/python -c "import cython; print(cython.__version__)" 2>&1 // .venv/bin/python -c "import meson... |
| 2 | 46-64 | `50-test-tooling` | block#2=0 / validation#2=4 / block#1=0 / validation#1=4 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 / probe#2=0 /... | validation#2=4 / validation#1=4 / repair#1=1 / repair#2=1 | 13/11 | executionagent-scikit-learn-5c51ab8c178b-005-30-python-deps-repaired | Traceback (most recent call last): File "<string>", line 1, in <module> AttributeError: module 'mesonbuild' has no attribute '__version__' |

## 14. executionagent-runs-gpt54 / google-guava

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->10-system-packages skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 02-language-deps->03-build-test-prep:previous | 00-preflight->10-system-packages:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 10-system-packages->20-java-runtime:previous | 20-java-runtime->30-java-deps:previous | 30-java-deps->50-test-tooling:previous。

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 12/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 6/0/0 |  |
| 2 | `02-language-deps` | succeeded | 01-system-deps | previous_block |  | 11/1/2 |  |
| 3 | `03-build-test-prep` | succeeded | 02-language-deps | previous_block |  | 6/0/0 |  |
| 10 | `10-system-packages` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |  |
| 20 | `20-java-runtime` | succeeded | 10-system-packages | previous_block |  | 6/0/0 |  |
| 30 | `30-java-deps` | succeeded | 20-java-runtime | previous_block |  | 16/1/7 |  |
| 50 | `50-test-tooling` | succeeded | 30-java-deps | previous_block |  | 6/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-guava-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 62fba2f8766e 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-001-base-workspace | [pheragent] preflight /workspace/repo Linux 62fba2f8766e 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-16 | `02-language-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | block#1=1 | 2/1 | executionagent-guava-003-01-system-deps-success | cd /workspace/repo && mvn -B -q -DskipTests install -pl guava,guava-testlib,guava-tests -am && mvn -B -q -DskipTests dependency:go-offline -pl '!gu... |
| 1 | 17-19 | `03-build-test-prep` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-004-02-language-deps-repaired |  |
| 1 | 20-22 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-guava-001-base-workspace | [pheragent] preflight /workspace/repo Linux 73132e71a6e6 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 23-25 | `01-system-deps` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-guava-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 26-28 | `02-language-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-guava-001-base-workspace | [pheragent] repair: Build local snapshot modules before go-offline |
| 1 | 29-31 | `03-build-test-prep` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-guava-001-base-workspace |  |
| 1 | 32-32 | `oracle` | oracle#1=1 | oracle#1=1 | 0/0 | executionagent-guava-006-final-clean-replay-clean-replay | INFO] --- bundle:5.1.9:manifest (bundle-manifest) @ guava --- [INFO] No MANIFEST.MF file found, generating manifest. [INFO] Writing manifest: /work... |
| 2 | 33-33 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 34-34 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-guava-73ec38433bc4-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux e35898094afc 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 35-37 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace | [pheragent] preflight /workspace/repo Linux e35898094afc 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 38-40 | `10-system-packages` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-d65197352c5c-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 41-43 | `20-java-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-cbd9d55b2240-003-10-system-packages-success | openjdk version "17.0.19" 2026-04-21 OpenJDK Runtime Environment (build 17.0.19+10-1-24.04.2-Ubuntu) OpenJDK 64-Bit Server VM (build 17.0.19+10-1-2... |
| 2 | 44-56 | `30-java-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | block#1=1 | 7/6 | executionagent-guava-b609922d16a9-004-20-java-runtime-success | ls -l pom.xml && head -20 pom.xml // grep -E 'SNAPSHOT/<repository>/<repositories>' pom.xml / head -20 // find ~/.m2/repository/com/google/guava -n... |
| 2 | 57-59 | `50-test-tooling` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-guava-6f67e0c1b6f6-005-30-java-deps-repaired | [pheragent] preparing java test tooling |
| 2 | 60-62 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace | [pheragent] preflight /workspace/repo Linux 76718a0d612d 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 63-65 | `10-system-packages` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 66-68 | `20-java-runtime` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace | openjdk version "17.0.19" 2026-04-21 OpenJDK Runtime Environment (build 17.0.19+10-1-24.04.2-Ubuntu) OpenJDK 64-Bit Server VM (build 17.0.19+10-1-2... |
| 2 | 69-71 | `30-java-deps` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace | om central: https://repo.maven.apache.org/maven2/org/apache/struts/struts-core/1.3.8/struts-core-1.3.8.jar (329 kB at 53 kB/s) [INFO] Downloading f... |
| 2 | 72-74 | `50-test-tooling` | clean_replay#5=0 / clean_replay_validation#5=0 / clean_replay_finalize#5=0 |  | 0/0 | executionagent-guava-825deda2ccce-001-base-workspace | [pheragent] preparing java test tooling |

## 15. executionagent-runs-gpt54 / pytest-dev-pytest

- 结果：ok=True；project_attempt_count=3；classification=succeeded_after_project_retry。
- 严格重算：true_non_adjacent。
- 真实非相邻边：00-preflight->20-python-runtime skip=01-system-deps;02-language-deps;03-build-test-prep。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->01-system-deps:previous | 01-system-deps->02-language-deps:previous | 02-language-deps->03-build-test-prep:previous | 00-preflight->20-python-runtime:non_adjacent(skip=01-system-deps,02-language-deps,03-build-test-prep) | 20-python-runtime->30-python-deps:previous | 30-python-deps->50-test-tooling:previous。
- 最终错误摘要：5 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (1.6.0) Requirement already satisfied: pygments>=2.7.2 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (2.20.0) C...

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 9/0/0 |  |
| 1 | `01-system-deps` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `02-language-deps` | succeeded | 01-system-deps | previous_block |  | 3/0/0 |  |
| 3 | `03-build-test-prep` | failed | 02-language-deps | previous_block |  | 11/3/7 | 5 in ./.venv/lib/python3.12/site-packages (from pytest==0.1.dev1+gfa6a232d5) (1.6.0) Requirement already satisfied: pygments>=2.7.2 in ./... |
| 20 | `20-python-runtime` | succeeded | 00-preflight | non_adjacent_block | 01-system-deps;02-language-deps;03-build-test-prep | 6/0/0 |  |
| 30 | `30-python-deps` | succeeded | 20-python-runtime | previous_block |  | 17/4/7 |  |
| 50 | `50-test-tooling` | succeeded | 30-python-deps | previous_block |  | 19/3/6 | ERROR: /workspace/repo/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+gfa6a232d5' |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pytest-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 5e86e52f0a8a 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pytest-001-base-workspace | [pheragent] preflight /workspace/repo Linux 5e86e52f0a8a 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `01-system-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pytest-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-11 | `02-language-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pytest-003-01-system-deps-success | error: subprocess-exited-with-error × Getting requirements to build editable did not run successfully. │ exit code: 1 ╰─> [17 lines of output] /tmp... |
| 1 | 12-22 | `03-build-test-prep` | block#1=0 / validation#1=2 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=1 / llm_probe#2=0 / llm_repair#2=0 / repair#2=4 | validation#1=2 / repair#1=1 / repair#2=4 | 7/5 | executionagent-pytest-004-02-language-deps-success | ERROR: /workspace/repo/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+gfa6a232d5' |
| 2 | 23-23 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 2 | 24-24 | `container-preflight` | container_preflight#1=0 |  | 0/0 | executionagent-pytest-971e89d06c24-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux 21b75a668ac0 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 2 | 25-27 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace | [pheragent] preflight /workspace/repo Linux 21b75a668ac0 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 28-30 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pytest-97009fd00176-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 31-33 | `30-python-deps` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | executionagent-pytest-3921262c8ad9-003-20-python-runtime-success | [pheragent] python dependencies Requirement already satisfied: pip in ./.venv/lib/python3.12/site-packages (26.1.2) Requirement already satisfied: ... |
| 2 | 34-35 | `50-test-tooling` | block#1=0 / validation#1=4 | validation#1=4 | 0/0 | executionagent-pytest-c5b26770d2b0-004-30-python-deps-success | ERROR: /workspace/repo/pyproject.toml: 'minversion' requires pytest-2.0, actual pytest-0.1.dev1+gfa6a232d5' |
| 2 | 36-46 | `30-python-deps` | llm_probe#1=0 / probe#1=1 / probe#1=1 / probe#1=0 / probe#1=1 / probe#1=2 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | probe#1=1 / probe#1=1 / probe#1=1 / probe#1=2 | 7/6 | executionagent-pytest-3921262c8ad9-003-20-python-runtime-success | .venv/bin/python -m pytest --version // .venv/bin/pip list --format=columns / grep pytest // sed -n '/minversion/p' pyproject.toml // ls -1 . / gre... |
| 2 | 47-60 | `50-test-tooling` | block#2=0 / validation#2=4 / block#1=0 / validation#1=4 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=0 / repair#1=0 / block#2=0 / validation#2=0 / finalize#2=0 | validation#2=4 / validation#1=4 | 6/5 | executionagent-pytest-dfa57eb36063-005-30-python-deps-repaired | .venv/bin/python -m pip show pytest // .venv/bin/pip list --editable // sed -n '/pytest/p' pyproject.toml / head -20 // .venv/bin/pip freeze / grep... |
| 2 | 61-63 | `00-preflight` | clean_replay#1=0 / clean_replay_validation#1=0 / clean_replay_finalize#1=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace | [pheragent] preflight /workspace/repo Linux c31e26b93e78 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 2 | 64-66 | `20-python-runtime` | clean_replay#2=0 / clean_replay_validation#2=0 / clean_replay_finalize#2=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace | debconf: delaying package configuration, since apt-utils is not installed |
| 2 | 67-69 | `30-python-deps` | clean_replay#3=0 / clean_replay_validation#3=0 / clean_replay_finalize#3=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace | [pheragent] repair: Install pytest>=2.0 to satisfy minversion requirement Collecting pytest>=2.0 Downloading pytest-9.1.1-py3-none-any.whl.metadata... |
| 2 | 70-72 | `50-test-tooling` | clean_replay#4=0 / clean_replay_validation#4=0 / clean_replay_finalize#4=0 |  | 0/0 | executionagent-pytest-ca6decb619bd-001-base-workspace | [pheragent] repair: Force upgrade pytest to >=2.0 in venv Collecting pytest>=2.0 Using cached pytest-9.1.1-py3-none-any.whl.metadata (7.6 kB) Requi... |

## 16. projects-repo2run / instructlab

- 结果：ok=False；project_attempt_count=1；classification=failed_in_project_run。
- 严格重算：input_marked_non_adjacent_but_recomputed_previous_only。
- 真实非相邻边：无。
- 原输入 rollback_edges：BASE->00-preflight | 00-preflight->20-python-runtime:previous | 20-python-runtime->30-python-deps:non_adjacent(skip=50-test-tooling)。
- 备注：`blocks/*.json` 中 `20-python-runtime` 的 order=1、`30-python-deps` 的 order=2、`50-test-tooling` 的 order=3，因此 `20-python-runtime -> 30-python-deps` 是相邻承接；原 CSV 的非相邻标记来自输入统计口径差异，保留为待复核项。
- 最终错误摘要：block failed: 30-python-deps

### 最终 block/rollback 流

| order | block | final status | rollback source | edge | skipped | events/fails/repairs | last error |
|---:|---|---|---|---|---|---:|---|
| 0 | `00-preflight` | succeeded | BASE/none | base_workspace |  | 3/0/0 |  |
| 1 | `20-python-runtime` | succeeded | 00-preflight | previous_block |  | 3/0/0 |  |
| 2 | `30-python-deps` | failed | 20-python-runtime | previous_block |  | 72/28/50 | uirements.txt (line 9)) (3.5.2) Requirement already satisfied: llvmlite<0.48,>=0.47.0dev0 in ./.venv/lib/python3.12/site-packages (from n... |
| 3 | `50-test-tooling` | planned | BASE/none | none |  | 0/0/0 |  |

### 按时间顺序的执行片段

| seg | lines | block | phase/attempt/exit | failed phases | repair/probe | checkpoint before | error/repair hint |
|---:|---:|---|---|---|---:|---|---|
| 1 | 1-1 | `base-image` | docker_build#1=0 |  | 0/0 |  | #0 building with "default" instance using docker driver #1 [internal] load build definition from Dockerfile.heragent-thin #1 transferring dockerfil... |
| 1 | 2-2 | `container-preflight` | container_preflight#1=0 |  | 0/0 | repo2run-gpt-4o-20241120-instructlab-3e9bda1fd149-base | [pheragent] container preflight workdir=/workspace/repo user=root uid=0 gid=0 Linux ac9370ae71fe 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC ... |
| 1 | 3-5 | `00-preflight` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | repo2run-gpt-4o-20241120-instructlab-6149c9a58c18-001-base-workspace | [pheragent] preflight /workspace/repo Linux ac9370ae71fe 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_... |
| 1 | 6-8 | `20-python-runtime` | block#1=0 / validation#1=0 / finalize#1=0 |  | 0/0 | repo2run-gpt-4o-20241120-instructlab-7d5e818f54fe-002-00-preflight-success | debconf: delaying package configuration, since apt-utils is not installed |
| 1 | 9-80 | `30-python-deps` | block#1=1 / validation#1=0 / llm_probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / probe#1=0 / llm_repair#1=1 / llm_probe#2=0 / probe#2=2 / probe#2=1 / probe#2=0 / probe#2=0 / llm_repair#2=1 / llm_probe#3=0 / probe#3=2 / probe#3=... | block#1=1 / llm_repair#1=1 / probe#2=2 / probe#2=1 / llm_repair#2=1 / probe#3=2 / llm_repair#3=1 / probe#4=127 / probe#4=None / probe#4=1... | 50/29 | repo2run-gpt-4o-20241120-instructlab-42f3f38cda80-003-20-python-runtime-success | File "<stdin>", line 6 . = Path(sys.argv[1]) ^ SyntaxError: invalid syntax |

