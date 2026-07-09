# Final Heragent Failure Analysis

Generated at: 2026-06-27T14:11:54.860887+00:00

## Scope

- Total runs counted: 891
- Final ok: 668
- Final failed or incomplete: 223

相对 9 个目录复用 `statistic/all_trajectory_runs.csv`；绝对 repo2run 使用 manifest 粗扫，并对 47 个失败 run 补读对应 failed block 的 `last_error`。

## By Directory

| source_dir | total | ok | failed/incomplete | missing manifest | top categories |
| --- | ---: | ---: | ---: | ---: | --- |
| /sdb-disk/lix/love/pheragent/projects-repo2run | 415 | 368 | 47 | 0 | python_dependency_resolution:25; docker_or_container_runtime:13; python_runtime_or_venv:5; system_package_installation:4 |
| executionagent-runs-gpt4o | 50 | 38 | 12 | 0 | java_runtime_or_dependency:4; python_dependency_resolution:3; node_dependency_or_runtime:2; repo_layout_or_wrong_workdir:1; python_runtime_or_venv:1 |
| executionagent-runs-gpt54 | 50 | 43 | 7 | 0 | python_dependency_resolution:2; test_tooling_or_collection:2; docker_or_container_runtime:1; system_package_installation:1; java_runtime_or_dependency:1 |
| installamatic-runs | 40 | 20 | 20 | 0 | python_dependency_resolution:15; test_tooling_or_collection:5 |
| installamatic-runs-rerun-failures-2 | 20 | 8 | 12 | 0 | test_tooling_or_collection:6; python_dependency_resolution:6 |
| installamatic-runs-rerun-failures-3 | 12 | 2 | 10 | 0 | python_dependency_resolution:7; test_tooling_or_collection:3 |
| projects-repo2run | 212 | 142 | 70 | 4 | python_dependency_resolution:58; incomplete_or_missing_trace:4; docker_or_container_runtime:4; test_tooling_or_collection:3; llm_or_repair_generation:1 |
| setupbench-runs-all-gpt-4.1 | 54 | 28 | 26 | 0 | oracle_or_final_validation_failure:14; docker_or_container_runtime:9; python_dependency_resolution:1; system_package_installation:1; python_runtime_or_venv:1 |
| setupbench-runs-all-gpt-4.1-2rerun | 27 | 10 | 17 | 1 | oracle_or_final_validation_failure:10; docker_or_container_runtime:4; python_runtime_or_venv:1; test_tooling_or_collection:1; incomplete_or_missing_trace:1 |
| setupbench-runs-all-gpt-5.4-multiblock | 11 | 9 | 2 | 1 | incomplete_or_missing_trace:1; test_tooling_or_collection:1 |

## Failure Categories

| category | subcategory | count | common blocks | examples |
| --- | --- | ---: | --- | --- |
| python_dependency_resolution | python-deps | 97 | 30-python-deps:79; 02-python-deps:16; 01-python-deps:1; 20-python-deps:1 | executionagent-runs-gpt4o:keras-team-keras:01-python-deps | executionagent-runs-gpt4o:ansible-ansible:30-python-deps | executionagent-runs-gpt54:keras-team-keras:02-python-deps | installamatic-runs:encode-starlette:30-python-deps | installamatic-runs:speechbrain-speechbrain:30-python-deps | installamatic-runs:vainf-torch-pruning:30-python-deps | installamatic-runs:cvhub520-x-anylabeling:30-python-deps | installamatic-runs:tiangolo-fastapi:30-python-deps | installamatic-runs:aimhubio-aim:30-python-deps | installamatic-runs:explosion-spacy:30-python-deps |
| docker_or_container_runtime | container_runtime | 31 | (blank):18; 30-python-deps:4; 50-test-tooling:1; 03-build-test-prep:1; 02-rust-setup:1; 01-system-deps:1; 03-pytest-collect:1; 01-system-node:1 | executionagent-runs-gpt54:django-django:50-test-tooling | setupbench-runs-all-gpt-4.1-2rerun:ta-lib-ta-lib-python: | setupbench-runs-all-gpt-4.1-2rerun:openai-openai-node: | setupbench-runs-all-gpt-4.1-2rerun:monero-project-monero: | setupbench-runs-all-gpt-4.1-2rerun:nedbat-coveragepy:03-build-test-prep | setupbench-runs-all-gpt-4.1:habitat-sh-habitat:02-rust-setup | setupbench-runs-all-gpt-4.1:johnpapa-vscode-angular-snippets: | setupbench-runs-all-gpt-4.1:reflex-dev-reflex:01-system-deps | setupbench-runs-all-gpt-4.1:falconry-falcon:03-pytest-collect | setupbench-runs-all-gpt-4.1:microsoft-typescript-vue-starter:01-system-node |
| oracle_or_final_validation_failure | oracle_validation_failed | 23 | (blank):23 | setupbench-runs-all-gpt-4.1-2rerun:dishait-tov-template: | setupbench-runs-all-gpt-4.1-2rerun:reflex-dev-reflex: | setupbench-runs-all-gpt-4.1-2rerun:pallets-click: | setupbench-runs-all-gpt-4.1-2rerun:testing-cabal-testtools: | setupbench-runs-all-gpt-4.1-2rerun:dstl-stone-soup: | setupbench-runs-all-gpt-4.1-2rerun:public-apis-public-apis: | setupbench-runs-all-gpt-4.1-2rerun:psf-black: | setupbench-runs-all-gpt-4.1-2rerun:servo-servo: | setupbench-runs-all-gpt-4.1-2rerun:ousret-charset-normalizer: | setupbench-runs-all-gpt-4.1:bolsote-isoduration: |
| test_tooling_or_collection | test-tooling | 18 | 50-test-tooling:18 | installamatic-runs:mandarons-icloud-drive-docker:50-test-tooling | installamatic-runs:python-mypy:50-test-tooling | installamatic-runs:sciphi-ai-r2r:50-test-tooling | installamatic-runs:soimort-you-get:50-test-tooling | installamatic-runs:tqdm-tqdm:50-test-tooling | installamatic-runs-rerun-failures-2:mandarons-icloud-drive-docker:50-test-tooling | installamatic-runs-rerun-failures-2:vainf-torch-pruning:50-test-tooling | installamatic-runs-rerun-failures-2:python-mypy:50-test-tooling | installamatic-runs-rerun-failures-2:sciphi-ai-r2r:50-test-tooling | installamatic-runs-rerun-failures-2:jxnl-instructor:50-test-tooling |
| python_dependency_resolution | language-deps | 10 | 02-language-deps:9; 20-language-deps:1 | executionagent-runs-gpt54:reactivex-rxjava:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:AlphaCodium:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:MultiModalMamba:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:UrbanGPT:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:contrastors:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:flash-diffusion:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:metavoice-src:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:mlx-engine:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:nexa-sdk:20-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:ragbuilder:02-language-deps |
| python_runtime_or_venv | venv_or_pip_or_tempdir | 8 | 02-language-deps:2; 03-build-test-prep:2; 10-system-packages:1; 01-system-python:1; 01-system-deps:1; 02-python-deps:1 | executionagent-runs-gpt4o:pallets-flask:10-system-packages | setupbench-runs-all-gpt-4.1-2rerun:aarora4-whisper:01-system-python | setupbench-runs-all-gpt-4.1:nedbat-coveragepy:01-system-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:FasterLivePortrait:02-python-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:IS-Fusion:02-language-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:TapeAgents:03-build-test-prep | /sdb-disk/lix/love/pheragent/projects-repo2run:sage:03-build-test-prep | /sdb-disk/lix/love/pheragent/projects-repo2run:yt2doc:02-language-deps |
| incomplete_or_missing_trace | missing_manifest | 6 | 50-test-tooling:2; 30-python-deps:2; 10-system-packages:1; 20-runtime-toolchain:1 | setupbench-runs-all-gpt-5.4-multiblock:aarora4-whisper:10-system-packages | setupbench-runs-all-gpt-4.1-2rerun:openai-whisper:20-runtime-toolchain | projects-repo2run:LaVague:50-test-tooling | projects-repo2run:ReAct:30-python-deps | projects-repo2run:Speech-AI-Forge:30-python-deps | projects-repo2run:CodeFuse-muAgent:50-test-tooling |
| system_package_installation | system-deps | 5 | 01-system-deps:4; 10-system-deps:1 | setupbench-runs-all-gpt-4.1:ta-lib-ta-lib-python:01-system-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:ComfyUI-DeepFuze:01-system-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:llama_parse:01-system-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:robocasa:01-system-deps | /sdb-disk/lix/love/pheragent/projects-repo2run:universal_manipulation_interface:10-system-deps |
| java_runtime_or_dependency | java-deps | 4 | 30-java-deps:3; 01-java-deps:1 | executionagent-runs-gpt4o:google-guava:01-java-deps | executionagent-runs-gpt4o:activiti-activiti:30-java-deps | executionagent-runs-gpt4o:apache-flink:30-java-deps | executionagent-runs-gpt54:activiti-activiti:30-java-deps |
| python_dependency_resolution | project-dependencies | 4 | 30-project-dependencies:4 | executionagent-runs-gpt4o:opencv-opencv:30-project-dependencies | installamatic-runs-rerun-failures-3:sciphi-ai-r2r:30-project-dependencies | projects-repo2run:gpustack:30-project-dependencies | projects-repo2run:flash-diffusion:30-project-dependencies |
| node_dependency_or_runtime | node-deps | 2 | 30-node-deps:2 | executionagent-runs-gpt4o:nestjs-nest:30-node-deps | executionagent-runs-gpt4o:webpack-webpack:30-node-deps |
| python_dependency_resolution | python-dependencies | 2 | 30-python-dependencies:2 | projects-repo2run:nano-graphrag:30-python-dependencies | projects-repo2run:hydra:30-python-dependencies |
| python_dependency_resolution | python-runtime | 2 | 20-python-runtime:2 | installamatic-runs:boto-boto3:20-python-runtime | installamatic-runs-rerun-failures-2:open-compass-opencompass:20-python-runtime |
| test_tooling_or_collection | build-test-prep | 2 | 03-build-test-prep:2 | executionagent-runs-gpt54:pandas-dev-pandas:03-build-test-prep | executionagent-runs-gpt54:scikit-learn-scikit-learn:03-build-test-prep |
| java_runtime_or_dependency | java-runtime | 1 | 21-java-runtime:1 | executionagent-runs-gpt4o:facebook-react-native:21-java-runtime |
| llm_or_repair_generation | llm_response_or_connection | 1 | (blank):1 | projects-repo2run:LazyLLM: |
| native_build_or_toolchain | rust-deps | 1 | 30-rust-deps:1 | executionagent-runs-gpt4o:denoland-deno:30-rust-deps |
| oracle_or_final_validation_failure | final_clean_replay_failed | 1 | (blank):1 | setupbench-runs-all-gpt-4.1-2rerun:apache-cassandra: |
| python_dependency_resolution | package_build_failure | 1 | 02-language-deps:1 | /sdb-disk/lix/love/pheragent/projects-repo2run:Speech-AI-Forge:02-language-deps |
| python_dependency_resolution | version_or_solver_conflict | 1 | 02-language-deps:1 | /sdb-disk/lix/love/pheragent/projects-repo2run:pi-nexus-autonomous-banking-network:02-language-deps |
| repo_layout_or_wrong_workdir | missing_expected_build_file | 1 | 20-native-build-config:1 | executionagent-runs-gpt4o:msgpack-msgpack-c:20-native-build-config |
| system_package_installation | system-packages | 1 | 10-system-packages:1 | executionagent-runs-gpt54:dmlc-xgboost:10-system-packages |
| test_tooling_or_collection | pytest-collect | 1 | 04-pytest-collect:1 | setupbench-runs-all-gpt-4.1-2rerun:nvbn-thefuck:04-pytest-collect |

## Final Failed Blocks

| block | count | categories | sources |
| --- | ---: | --- | --- |
| 30-python-deps | 85 | python_dependency_resolution:79; docker_or_container_runtime:4; incomplete_or_missing_trace:2 | projects-repo2run:60; installamatic-runs:14; installamatic-runs-rerun-failures-2:5; installamatic-runs-rerun-failures-3:5; executionagent-runs-gpt4o:1 |
| (blank) | 43 | oracle_or_final_validation_failure:24; docker_or_container_runtime:18; llm_or_repair_generation:1 | setupbench-runs-all-gpt-4.1:16; setupbench-runs-all-gpt-4.1-2rerun:13; /sdb-disk/lix/love/pheragent/projects-repo2run:13; projects-repo2run:1 |
| 50-test-tooling | 21 | test_tooling_or_collection:18; incomplete_or_missing_trace:2; docker_or_container_runtime:1 | installamatic-runs-rerun-failures-2:6; installamatic-runs:5; projects-repo2run:5; installamatic-runs-rerun-failures-3:3; executionagent-runs-gpt54:1; setupbench-runs-all-gpt-5.4-multiblock:1 |
| 02-python-deps | 18 | python_dependency_resolution:16; docker_or_container_runtime:1; python_runtime_or_venv:1 | /sdb-disk/lix/love/pheragent/projects-repo2run:15; setupbench-runs-all-gpt-4.1:2; executionagent-runs-gpt54:1 |
| 02-language-deps | 13 | python_dependency_resolution:11; python_runtime_or_venv:2 | /sdb-disk/lix/love/pheragent/projects-repo2run:12; executionagent-runs-gpt54:1 |
| 01-system-deps | 6 | system_package_installation:4; docker_or_container_runtime:1; python_runtime_or_venv:1 | setupbench-runs-all-gpt-4.1:3; /sdb-disk/lix/love/pheragent/projects-repo2run:3 |
| 03-build-test-prep | 5 | test_tooling_or_collection:2; python_runtime_or_venv:2; docker_or_container_runtime:1 | executionagent-runs-gpt54:2; /sdb-disk/lix/love/pheragent/projects-repo2run:2; setupbench-runs-all-gpt-4.1-2rerun:1 |
| 30-project-dependencies | 4 | python_dependency_resolution:4 | projects-repo2run:2; executionagent-runs-gpt4o:1; installamatic-runs-rerun-failures-3:1 |
| 10-system-packages | 3 | python_runtime_or_venv:1; system_package_installation:1; incomplete_or_missing_trace:1 | executionagent-runs-gpt4o:1; executionagent-runs-gpt54:1; setupbench-runs-all-gpt-5.4-multiblock:1 |
| 30-java-deps | 3 | java_runtime_or_dependency:3 | executionagent-runs-gpt4o:2; executionagent-runs-gpt54:1 |
| 10-system-deps | 2 | docker_or_container_runtime:1; system_package_installation:1 | setupbench-runs-all-gpt-4.1:1; /sdb-disk/lix/love/pheragent/projects-repo2run:1 |
| 20-python-runtime | 2 | python_dependency_resolution:2 | installamatic-runs:1; installamatic-runs-rerun-failures-2:1 |
| 30-node-deps | 2 | node_dependency_or_runtime:2 | executionagent-runs-gpt4o:2 |
| 30-python-dependencies | 2 | python_dependency_resolution:2 | projects-repo2run:2 |
| 00-preflight | 1 | docker_or_container_runtime:1 | setupbench-runs-all-gpt-4.1:1 |
| 01-java-deps | 1 | java_runtime_or_dependency:1 | executionagent-runs-gpt4o:1 |
| 01-python-deps | 1 | python_dependency_resolution:1 | executionagent-runs-gpt4o:1 |
| 01-system-node | 1 | docker_or_container_runtime:1 | setupbench-runs-all-gpt-4.1:1 |
| 01-system-python | 1 | python_runtime_or_venv:1 | setupbench-runs-all-gpt-4.1-2rerun:1 |
| 02-rust-setup | 1 | docker_or_container_runtime:1 | setupbench-runs-all-gpt-4.1:1 |
| 03-pytest-collect | 1 | docker_or_container_runtime:1 | setupbench-runs-all-gpt-4.1:1 |
| 04-pytest-collect | 1 | test_tooling_or_collection:1 | setupbench-runs-all-gpt-4.1-2rerun:1 |
| 20-language-deps | 1 | python_dependency_resolution:1 | /sdb-disk/lix/love/pheragent/projects-repo2run:1 |
| 20-native-build-config | 1 | repo_layout_or_wrong_workdir:1 | executionagent-runs-gpt4o:1 |
| 20-python-deps | 1 | python_dependency_resolution:1 | installamatic-runs-rerun-failures-3:1 |
| 20-runtime-toolchain | 1 | incomplete_or_missing_trace:1 | setupbench-runs-all-gpt-4.1-2rerun:1 |
| 21-java-runtime | 1 | java_runtime_or_dependency:1 | executionagent-runs-gpt4o:1 |
| 30-rust-deps | 1 | native_build_or_toolchain:1 | executionagent-runs-gpt4o:1 |

## Notes

- `reported_failed_block` 对相对目录来自现有统计表的 `first_failed_block`；对外部 repo2run 来自 manifest 的 `block failed: ...`。
- `error_signature`/`error_excerpt` 是失败原因归类的证据；详见 `final_heragent_failure_by_run.csv`。
- 由于直接全量读取 run artifact 会在当前磁盘上卡入 D 状态，本报告避免重扫全部 `blocks/` 和 `executions.jsonl`。
