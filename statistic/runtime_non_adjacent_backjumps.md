# Runtime non-adjacent backjump scan

Generated at: 2026-06-26T15:41:27.926807+00:00

口径：逐个读取 run 目录的 `executions.jsonl` 和 `blocks/*.json`；按时间线聚合连续相同 block；忽略 `base-image`、`container-preflight`、`oracle` 和 `clean_replay*`；当前 block rank 小于上一个实际 block rank，且中间隔了至少一个 block，记为 runtime 非相邻回跳。

- runs indexed: 476
- runs processed: 470
- scan errors: 6
- runtime non-adjacent backjumps: 19
- missed by previous final checkpoint graph list: 19

## Distribution

- all / executionagent-runs-gpt4o: 7
- all / installamatic-runs: 2
- all / projects-repo2run: 8
- all / setupbench-runs-all-gpt-5.4-multiblock: 2
- missed / executionagent-runs-gpt4o: 7
- missed / installamatic-runs: 2
- missed / projects-repo2run: 8
- missed / setupbench-runs-all-gpt-5.4-multiblock: 2

## Missed Runtime Non-Adjacent Backjumps

### 1. executionagent-runs-gpt4o / reactivex-rxjava

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `20-java-runtime` rank=3 order=20 lines 6-7 -> `00-preflight` rank=1 order=0 lines 8-10
- skipped: `01-java-deps`
- from failed phases: `validation#1=127`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-rxjava-067877599e8d-001-base-workspace`
- failure hint: `/tmp/pheragent/blocks/20-java-runtime.sh: 31: java: not found ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. Please set the JAVA_HOME variable in...`
- repair hint: `LLM probe request failed: Connection error.`
- run_dir: `executionagent-runs-gpt4o/state/reactivex-rxjava/RxJava/runs/executionagent-gpt4o-rxjava`

### 2. executionagent-runs-gpt4o / msgpack-msgpack-c

- result: ok=False; trajectory=failed_in_project_run; project_attempt=failed_in_project_run
- jump: `20-native-build-config` rank=3 order=20 lines 8-9 -> `00-preflight` rank=1 order=0 lines 10-20
- skipped: `10-system-packages`
- from failed phases: `block#1=1 | validation#1=1`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-msgpack-c-718ee62d5bd8-001-base-workspace`
- failure hint: `CMake Warning: Ignoring extra path from command line: "." CMake Error: The source directory "/workspace/repo" does not appear to contain CMakeLists.txt. Specify --help for usage...`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "List files in the repo", "command": "ls -la /workspace/repo" }, { "title": "Check for CMakeLists.txt", "command": "find /works...`
- run_dir: `executionagent-runs-gpt4o/state/msgpack-msgpack-c/msgpack-c/runs/executionagent-gpt4o-msgpack-c`

### 3. executionagent-runs-gpt4o / facebook-react-native

- result: ok=False; trajectory=failed_in_project_run; project_attempt=failed_in_project_run
- jump: `21-java-runtime` rank=4 order=21 lines 12-13 -> `10-system-packages` rank=2 order=10 lines 14-24
- skipped: `20-node-runtime`
- from failed phases: `validation#1=127`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-react-native-72b53bb70f61-002-00-preflight-success`
- failure hint: `/tmp/pheragent/blocks/21-java-runtime.sh: 31: java: not found`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Python and Pip Presence", "command": "command -v python3 >/dev/null 2>&1 && command -v pip3 >/dev/null 2>&1" }, { "title": "No...`
- run_dir: `executionagent-runs-gpt4o/state/facebook-react-native/react-native/runs/executionagent-gpt4o-react-native`

### 4. executionagent-runs-gpt4o / facebook-react-native

- result: ok=False; trajectory=failed_in_project_run; project_attempt=failed_in_project_run
- jump: `21-java-runtime` rank=4 order=21 lines 60-61 -> `10-system-packages` rank=2 order=10 lines 62-72
- skipped: `20-node-runtime`
- from failed phases: `validation#1=127`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-react-native-3d8c9fd9f08b-002-00-preflight-success`
- failure hint: `/tmp/pheragent/blocks/21-java-runtime.sh: 31: java: not found`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check for python", "command": "command -v python3 >/dev/null 2>&1 || true" }, { "title": "Check for pip", "command": "command ...`
- run_dir: `executionagent-runs-gpt4o/state/facebook-react-native/react-native/runs/executionagent-gpt4o-react-native`

### 5. executionagent-runs-gpt4o / spring-projects-spring-security

- result: ok=True; trajectory=clean_one_shot_success; project_attempt=one_project_attempt_success
- jump: `20-java-runtime` rank=3 order=20 lines 6-7 -> `00-preflight` rank=1 order=0 lines 8-10
- skipped: `10-system-packages`
- from failed phases: `validation#1=127`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-spring-security-d18dc3408331-001-base-workspace`
- failure hint: `/tmp/pheragent/blocks/20-java-runtime.sh: 31: java: not found ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. Please set the JAVA_HOME variable in...`
- repair hint: `LLM probe request failed: Connection error.`
- run_dir: `executionagent-runs-gpt4o/state/spring-projects-spring-security/spring-security/runs/executionagent-gpt4o-spring-security`

### 6. executionagent-runs-gpt4o / mybatis-mybatis-3

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `20-java-runtime` rank=3 order=20 lines 6-7 -> `00-preflight` rank=1 order=0 lines 8-18
- skipped: `01-java-deps`
- from failed phases: `validation#1=127`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-mybatis-3-963c9f12fc65-001-base-workspace`
- failure hint: `/tmp/pheragent/blocks/20-java-runtime.sh: 31: java: not found /tmp/pheragent/blocks/20-java-runtime.sh: 32: mvn: not found`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check for Java installation", "command": "command -v java" }, { "title": "Check for Maven installation", "command": "command -...`
- run_dir: `executionagent-runs-gpt4o/state/mybatis-mybatis-3/mybatis-3/runs/executionagent-gpt4o-mybatis-3`

### 7. executionagent-runs-gpt4o / python-cpython

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `30-project-dependencies` rank=5 order=30 lines 56-57 -> `10-system-packages` rank=2 order=10 lines 58-68
- skipped: `20-python-runtime;20-runtime-toolchain`
- from failed phases: `block#1=1 | validation#1=1`
- to first phase/checkpoint: `llm_probe` / `pheragent-executionagent-gpt4o:executionagent-gpt4o-cpython-69f8e79d2a8d-002-00-preflight-success`
- failure hint: `error: externally-managed-environment × This environment is externally managed ╰─> To install Python packages system-wide, try apt install python3-xyz, where xyz is the package ...`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check Python 3 Installation", "command": "command -v python3" }, { "title": "Check CMake Installation", "command": "command -v...`
- run_dir: `executionagent-runs-gpt4o/state/python-cpython/cpython/runs/executionagent-gpt4o-cpython`

### 8. installamatic-runs / nonebot-nonebot2

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=7 order=50 lines 21-22 -> `30-python-deps` rank=5 order=30 lines 23-33
- skipped: `31-node-deps`
- from failed phases: `validation#1=4`
- to first phase/checkpoint: `llm_probe` / `pheragent-installamatic:installamatic-nonebot2-e473921e5767-005-21-node-runtime-success`
- failure hint: `[pheragent] preparing python test tooling [pheragent] preparing node test tooling v18.19.1 9.2.0`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check installed Python packages", "command": ".venv/bin/python -m pip list" }, { "title": "Check specific Python import", "com...`
- run_dir: `installamatic-runs/state/nonebot-nonebot2/nonebot2/runs/installamatic-nonebot2`

### 9. installamatic-runs / sciphi-ai-r2r

- result: ok=False; trajectory=failed_in_project_run; project_attempt=failed_in_project_run
- jump: `50-test-tooling` rank=5 order=50 lines 28-29 -> `20-python-runtime` rank=3 order=20 lines 30-40
- skipped: `30-project-dependencies`
- from failed phases: `validation#1=127`
- to first phase/checkpoint: `llm_probe` / `pheragent-installamatic:installamatic-r2r-316da1e37621-004-10-system-packages-repaired`
- failure hint: `/tmp/pheragent/blocks/50-test-tooling.sh: 31: pytest: not found`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check Python version", "command": "command -v python3" }, { "title": "List virtual environment directory", "command": "ls -l ....`
- run_dir: `installamatic-runs/state/sciphi-ai-r2r/R2R/runs/installamatic-r2r`

### 10. setupbench-runs-all-gpt-5.4-multiblock / habitat-sh-habitat

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=5 order=50 lines 15-16 -> `10-system-packages` rank=2 order=10 lines 17-21
- skipped: `20-rust-runtime;30-project-dependencies`
- from failed phases: `block#1=101 | validation#1=127`
- to first phase/checkpoint: `llm_repair` / `pheragent-setupbench:setupbench-habitat-b139753dcc27-002-00-preflight-success`
- failure hint: `Compiling proc-macro2 v1.0.93 Compiling unicode-ident v1.0.16 Compiling libc v0.2.171 Compiling cfg-if v1.0.0 Compiling serde v1.0.218 Compiling memchr v2.7.4 Compiling shlex v1...`
- repair hint: `--- raw_llm_response --- {"repairs":[{"title":"Install protobuf compiler for Rust prost builds","command":"export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get ins...`
- run_dir: `setupbench-runs-all-gpt-5.4-multiblock/state/habitat-sh-habitat/habitat/runs/setupbench-habitat`

### 11. setupbench-runs-all-gpt-5.4-multiblock / apache-cassandra

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=6 order=50 lines 52-53 -> `30-project-dependencies` rank=4 order=30 lines 54-62
- skipped: `40-native-build-config`
- from failed phases: `block#1=1 | validation#1=1`
- to first phase/checkpoint: `llm_repair` / `pheragent-setupbench:setupbench-cassandra-7bf452af301e-004-20-runtime-toolchain-success`
- repair hint: `--- raw_llm_response --- {"repairs":[{"title":"sanitize pylib requirements and build Cassandra jars/tools","command":"cd /workspace/repo && . /workspace/repo/.venv/bin/activate ...`
- run_dir: `setupbench-runs-all-gpt-5.4-multiblock/state/apache-cassandra/cassandra/runs/setupbench-cassandra`

### 12. projects-repo2run / denser-retriever

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=7 order=50 lines 21-22 -> `30-python-deps` rank=5 order=30 lines 23-33
- skipped: `31-node-deps`
- from failed phases: `validation#1=2`
- to first phase/checkpoint: `llm_probe` / `pheragent:repo2run-gpt-4o-20241120-denser-retriever-4f0d59e79091-005-21-node-runtime-success`
- failure hint: `[pheragent] preparing python test tooling [pheragent] preparing node test tooling v18.19.1 9.2.0`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check existence of 'langchain_core' package", "command": ".venv/bin/python -c \"import importlib; print(importlib.util.find_sp...`
- run_dir: `projects-repo2run/denser-retriever/.pheragent/runs/repo2run-gpt-4o-20241120-denser-retriever`

### 13. projects-repo2run / DTrOCR

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=4 order=50 lines 5-6 -> `00-preflight` rank=1 order=0 lines 7-9
- skipped: `20-python-runtime;30-python-deps`
- from failed phases: `llm_repair#1=1`
- to first phase/checkpoint: `block` / `pheragent:repo2run-gpt-4o-20241120-dtrocr-e0a0fe0ffc4b-001-base-workspace`
- failure hint: `--- raw_llm_response --- { "probes": [] } --- parse_diagnostics --- probes list is empty`
- repair hint: `[pheragent] preflight /workspace/repo Linux d70466c6dfff 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux PRETTY_NAM...`
- run_dir: `projects-repo2run/DTrOCR/.pheragent/runs/repo2run-gpt-4o-20241120-dtrocr`

### 14. projects-repo2run / DTrOCR

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=4 order=50 lines 10-10 -> `20-python-runtime` rank=2 order=20 lines 11-14
- skipped: `30-python-deps`
- from failed phases: ``
- to first phase/checkpoint: `block` / `pheragent:repo2run-gpt-4o-20241120-dtrocr-9013698b6c96-002-00-preflight-success`
- failure hint: `--- raw_llm_response --- { "repairs": [ { "title": "Ensure isolated Python environment usability for pytest", "command": ".venv/bin/python -m pip install pytest && .venv/bin/pyt...`
- repair hint: `Error response from daemon: No such container: pheragent-repo2run-gpt-4o-20241120-dtrocr-c1`
- run_dir: `projects-repo2run/DTrOCR/.pheragent/runs/repo2run-gpt-4o-20241120-dtrocr`

### 15. projects-repo2run / Verbiverse

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=4 order=50 lines 12-13 -> `20-python-runtime` rank=2 order=20 lines 14-24
- skipped: `30-python-deps`
- from failed phases: `validation#1=2`
- to first phase/checkpoint: `llm_probe` / `pheragent:repo2run-gpt-4o-20241120-verbiverse-07d825368509-002-00-preflight-success`
- failure hint: `[pheragent] preparing python test tooling`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check for libglib2.0 presence", "command": "ldconfig -p | grep libglib-2.0.so" }, { "title": "Check for libGL presence", "comm...`
- run_dir: `projects-repo2run/Verbiverse/.pheragent/runs/repo2run-gpt-4o-20241120-verbiverse`

### 16. projects-repo2run / fastagency

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=7 order=50 lines 21-22 -> `30-python-deps` rank=5 order=30 lines 23-33
- skipped: `31-node-deps`
- from failed phases: `validation#1=4`
- to first phase/checkpoint: `llm_probe` / `pheragent:repo2run-gpt-4o-20241120-fastagency-96648a303212-005-21-node-runtime-success`
- failure hint: `[pheragent] preparing python test tooling [pheragent] preparing node test tooling v18.19.1 9.2.0`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check if fastapi is listed in pyproject.toml", "command": "grep -i 'fastapi' /workspace/repo/pyproject.toml || true" }, { "tit...`
- run_dir: `projects-repo2run/fastagency/.pheragent/runs/repo2run-gpt-4o-20241120-fastagency`

### 17. projects-repo2run / VideoFusion

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `30-python-deps` rank=5 order=30 lines 15-16 -> `20-python-runtime` rank=3 order=20 lines 17-35
- skipped: `21-node-runtime`
- from failed phases: `block#1=1`
- to first phase/checkpoint: `llm_probe` / `pheragent:repo2run-gpt-4o-20241120-videofusion-798dd62ce544-003-10-system-packages-success`
- failure hint: `error: subprocess-exited-with-error × Building wheel for diffq (pyproject.toml) did not run successfully. │ exit code: 1 ╰─> [31 lines of output] running bdist_wheel running bui...`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check presence of Python.h in system directories", "command": "find /usr/include -name Python.h -type f -print -quit" }, { "ti...`
- run_dir: `projects-repo2run/VideoFusion/.pheragent/runs/repo2run-gpt-4o-20241120-videofusion`

### 18. projects-repo2run / VideoFusion

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=7 order=50 lines 57-58 -> `10-system-packages` rank=2 order=10 lines 59-92
- skipped: `20-python-runtime;21-node-runtime;30-python-deps;31-node-deps`
- from failed phases: `validation#1=2`
- to first phase/checkpoint: `llm_probe` / `pheragent:repo2run-gpt-4o-20241120-videofusion-e859976f2087-002-00-preflight-success`
- failure hint: `[pheragent] preparing python test tooling [pheragent] preparing node test tooling v18.19.1 9.2.0 9.15.9`
- repair hint: `--- raw_llm_response --- { "probes": [ { "title": "Check if libglib-2.0.so.0 is available", "command": "ls /usr/lib | grep libglib-2.0.so.0 || ls /lib | grep libglib-2.0.so.0" }...`
- run_dir: `projects-repo2run/VideoFusion/.pheragent/runs/repo2run-gpt-4o-20241120-videofusion`

### 19. projects-repo2run / cogvideox-factory

- result: ok=True; trajectory=succeeded_after_internal_repair; project_attempt=one_project_attempt_success
- jump: `50-test-tooling` rank=4 order=50 lines 4-4 -> `00-preflight` rank=1 order=0 lines 5-7
- skipped: `20-python-runtime;30-python-deps`
- from failed phases: `validation#6=2`
- to first phase/checkpoint: `block` / `pheragent:repo2run-gpt-4o-20241120-cogvideox-factory-c210752e0983-001-base-workspace`
- failure hint: `tests/test_dataset.py::test_video_dataset tests/test_dataset.py::test_video_dataset_with_resizing tests/test_dataset.py::test_video_dataset_with_bucket_sampler =================...`
- repair hint: `[pheragent] preflight /workspace/repo Linux 07d753e1a33d 6.8.0-110-generic #110-Ubuntu SMP PREEMPT_DYNAMIC Thu Mar 19 15:09:20 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux PRETTY_NAM...`
- run_dir: `projects-repo2run/cogvideox-factory/.pheragent/runs/repo2run-gpt-4o-20241120-cogvideox-factory`

## All Runtime Non-Adjacent Backjumps

1. `missed` executionagent-runs-gpt4o / reactivex-rxjava: `20-java-runtime`(3) -> `00-preflight`(1), skipped `01-java-deps`, lines 6-7 -> 8-10
2. `missed` executionagent-runs-gpt4o / msgpack-msgpack-c: `20-native-build-config`(3) -> `00-preflight`(1), skipped `10-system-packages`, lines 8-9 -> 10-20
3. `missed` executionagent-runs-gpt4o / facebook-react-native: `21-java-runtime`(4) -> `10-system-packages`(2), skipped `20-node-runtime`, lines 12-13 -> 14-24
4. `missed` executionagent-runs-gpt4o / facebook-react-native: `21-java-runtime`(4) -> `10-system-packages`(2), skipped `20-node-runtime`, lines 60-61 -> 62-72
5. `missed` executionagent-runs-gpt4o / spring-projects-spring-security: `20-java-runtime`(3) -> `00-preflight`(1), skipped `10-system-packages`, lines 6-7 -> 8-10
6. `missed` executionagent-runs-gpt4o / mybatis-mybatis-3: `20-java-runtime`(3) -> `00-preflight`(1), skipped `01-java-deps`, lines 6-7 -> 8-18
7. `missed` executionagent-runs-gpt4o / python-cpython: `30-project-dependencies`(5) -> `10-system-packages`(2), skipped `20-python-runtime;20-runtime-toolchain`, lines 56-57 -> 58-68
8. `missed` installamatic-runs / nonebot-nonebot2: `50-test-tooling`(7) -> `30-python-deps`(5), skipped `31-node-deps`, lines 21-22 -> 23-33
9. `missed` installamatic-runs / sciphi-ai-r2r: `50-test-tooling`(5) -> `20-python-runtime`(3), skipped `30-project-dependencies`, lines 28-29 -> 30-40
10. `missed` setupbench-runs-all-gpt-5.4-multiblock / habitat-sh-habitat: `50-test-tooling`(5) -> `10-system-packages`(2), skipped `20-rust-runtime;30-project-dependencies`, lines 15-16 -> 17-21
11. `missed` setupbench-runs-all-gpt-5.4-multiblock / apache-cassandra: `50-test-tooling`(6) -> `30-project-dependencies`(4), skipped `40-native-build-config`, lines 52-53 -> 54-62
12. `missed` projects-repo2run / denser-retriever: `50-test-tooling`(7) -> `30-python-deps`(5), skipped `31-node-deps`, lines 21-22 -> 23-33
13. `missed` projects-repo2run / DTrOCR: `50-test-tooling`(4) -> `00-preflight`(1), skipped `20-python-runtime;30-python-deps`, lines 5-6 -> 7-9
14. `missed` projects-repo2run / DTrOCR: `50-test-tooling`(4) -> `20-python-runtime`(2), skipped `30-python-deps`, lines 10-10 -> 11-14
15. `missed` projects-repo2run / Verbiverse: `50-test-tooling`(4) -> `20-python-runtime`(2), skipped `30-python-deps`, lines 12-13 -> 14-24
16. `missed` projects-repo2run / fastagency: `50-test-tooling`(7) -> `30-python-deps`(5), skipped `31-node-deps`, lines 21-22 -> 23-33
17. `missed` projects-repo2run / VideoFusion: `30-python-deps`(5) -> `20-python-runtime`(3), skipped `21-node-runtime`, lines 15-16 -> 17-35
18. `missed` projects-repo2run / VideoFusion: `50-test-tooling`(7) -> `10-system-packages`(2), skipped `20-python-runtime;21-node-runtime;30-python-deps;31-node-deps`, lines 57-58 -> 59-92
19. `missed` projects-repo2run / cogvideox-factory: `50-test-tooling`(4) -> `00-preflight`(1), skipped `20-python-runtime;30-python-deps`, lines 4-4 -> 5-7

## Scan Errors

- `setupbench-runs-all-gpt-4.1-2rerun/state/ta-lib-ta-lib-python/ta-lib-python/runs/setupbench-ta-lib-python`: missing blocks
- `setupbench-runs-all-gpt-4.1-2rerun/state/openai-openai-node/openai-node/runs/setupbench-openai-node`: missing blocks
- `setupbench-runs-all-gpt-4.1-2rerun/state/monero-project-monero/monero/runs/setupbench-monero`: missing blocks
- `setupbench-runs-all-gpt-4.1/state/johnpapa-vscode-angular-snippets/vscode-angular-snippets/runs/setupbench-vscode-angular-snippets`: missing blocks
- `setupbench-runs-all-gpt-4.1/state/servo-servo/servo/runs/setupbench-servo`: missing blocks
- `projects-repo2run/LazyLLM/.pheragent/runs/repo2run-gpt-4o-20241120-lazyllm`: missing blocks
