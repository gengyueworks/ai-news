# _flow：候选信号派生区

本目录是**候选信号派生区**，不是任何目标数据的存放地。

> **EN —** This directory is a **derived candidate-signal area**: it holds **no target data** and is **not an SSOT** (Single Source of Truth). Signals staged here are candidates only.

## 本目录的用途

1. 存放从日报中产出的候选信号（signal），供人工评审。
2. 候选信号在此等待终审；终审通过（`accepted` / `enrich_existing`）后，才允许写入主源。
3. 评审记录和归档信号保留在本目录，不删除。

> **EN —** Candidate signals produced from the daily brief are staged here and **await human final review**. Only after a signal is approved (`accepted` / `enrich_existing`) may it be written into the master source. Review records and archived signals stay here and are never deleted.

## 规则与 SSOT 指向

本目录不重复定义规则。实际契约、校验、选题标准和主源清单以本地 `_flow` 目录为准：

| 文件 | 作用 |
| --- | --- |
| `signal-contract-v1.md` | 信号字段结构、生命周期和写入规则 |
| `signal.schema.json` | 单条信号的结构校验（draft 2020-12） |
| `selection-standard-v1.md` | 时间轴与词典的硬门槛、打分和排除项 |
| `ssot-manifest.md` | 主源、派生副本、历史副本、写入方向和禁止事项 |

以上四份文件的权威路径：

```
/Volumes/拓展坞 1T2022/2 Codex-Workspace/Codex-Workspace-Main/32-AI高质量阅读库/05-情报与深读系统/AI精华情报与深读操作台/10-源头网站活文件/00-站点根文件/_flow/
```

> **EN —** This directory does not redefine rules. The authoritative contract, validation, selection standards and master-source list live in the local `_flow` directory at the **absolute path above** — that path is the single source of truth for rules; always read them from there.

## 禁止事项

- **禁止在此直接修改目标数据**。时间轴和词典的主源数据不在这里，也不要在这里创建「看起来像最终数据」的副本。
- 禁止把候选信号直接写入主源，必须先过人工终审。
- 本目录内的候选信号不代表已入库；「候选不等于入库」是底线原则。

> **EN —** Do **not** modify target data here: timeline and dictionary master data do not live in this directory, and do not create copies that look like final data. Do not write candidate signals straight into the master source — **human final review is mandatory**. Signals in this directory are not yet ingested: candidate ≠ ingested.
