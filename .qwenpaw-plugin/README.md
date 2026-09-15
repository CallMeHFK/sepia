# Sepia — QwenPaw plugin

The fourth install target for [sepia](https://github.com/Nanako0129/sepia)
(alongside Claude `.claude-plugin/`, Codex `.codex-plugin/`, and Gemini
`.agents/`): a QwenPaw plugin that ships the sepia de-AI writing package —
the general `sepia` router plus the five operation skills
(`sepia-write`, `sepia-review`, `sepia-refactor`, `sepia-recreate`,
`sepia-hemingway`) — byte-identical to upstream, plus a `/sepia` slash
command as the single entry point.

## What it installs

| Piece | Source | Notes |
|---|---|---|
| `skills/sepia/` | upstream `skills/sepia/` | canonical router, incl. `references/**` and `agents/openai.yaml` |
| `skills/sepia-{write,review,refactor,recreate,hemingway}/` | upstream `skills/sepia-*/` | thin shells; resolve only `../sepia/SKILL.md` |
| `/sepia` command | `plugin.py` | composes a prompt for the host agent; no local LLM calls |

Skill frontmatter (`name / description / license`) is copied as-is —
the QwenPaw skill loader accepts it and ignores the unknown `license` key.

## Install

From a checkout of this repo:

```bash
cp -r .qwenpaw-plugin ~/.qwenpaw/plugins/sepia
qwenpaw plugin reload   # or restart QwenPaw
```

Or, if your QwenPaw build supports subdirectory installs from git:

```bash
qwenpaw plugin install https://github.com/Nanako0129/sepia --subdir .qwenpaw-plugin
```

After install, verify:

```bash
ls ~/.qwenpaw/workspaces/default/skills/ | grep sepia   # 6 entries
```

In any channel, `/sepia <text>` now routes through the canonical skill.

## Update

Upstream `skills/**` is the source of truth. After pulling upstream
changes, re-sync and verify byte parity:

```bash
python3 .qwenpaw-plugin/sync_skills.py        # sync + verify; non-zero on drift
python3 .qwenpaw-plugin/sync_skills.py --check  # verify only
```

CI (`.github/workflows/qwenpaw-sync.yml`) runs `--check` on every change
to `skills/**` so the QwenPaw bundle can never silently drift.

## Uninstall

```bash
qwenpaw plugin remove sepia
```

The host cleans up the workspace `skills/sepia*` copies and manifest
entries automatically (skills sourced from a plugin are tagged by
`source` and removed on uninstall).

## Versioning

`.qwenpaw-plugin/plugin.json` carries `version: 1.0.0`, identical to the
Claude/Codex manifests and the canonical SKILL.md, so
`scripts/check_versions.py` (which discovers every `plugin.json` in the
repo) stays green. `qwenpaw_version` is pinned to `2.1.0`–`2.99.0`.
