# Trajectory Artifacts

Raw trajectory archives are published as GitHub Release assets instead of being
committed to this source repository. Derived statistics and analysis tables live
in `statistic/`.

## Installamatic

Release: https://github.com/BeeuniLab/pheragent/releases/tag/trajectories

| Asset | Contents | SHA256 |
| --- | --- | --- |
| [`installamatic-trajectories.zip`](https://github.com/BeeuniLab/pheragent/releases/download/trajectories/installamatic-trajectories.zip) | gpt-4o-mini Installamatic trajectories: initial 40-project batch plus failure rerun batches, 72 trajectory directories total. | `a56c3ac528ac7b7acd1edf00694cf62fc440ffad784d1bb59772cf7c4acc0bd1` |
| [`installamatic-trajectories-gpt54.zip`](https://github.com/BeeuniLab/pheragent/releases/download/trajectories/installamatic-trajectories-gpt54.zip) | gpt-5.4 Installamatic trajectories for the 40-project batch. | `0b55d06e1703d7f4ed49e89adab1487fc0b30fab5493d4fa404efbe1b64f8b70` |

Each archive expands to a top-level directory with the same base name as the
asset. The trajectory directories contain `manifest.json`, `blocks/*.json`, and
batch `summary*.json` files.

Download and verify:

```bash
gh release download trajectories \
  --repo BeeuniLab/pheragent \
  --pattern 'installamatic-trajectories*.zip' \
  --dir release-artifacts

sha256sum release-artifacts/installamatic-trajectories*.zip
```
