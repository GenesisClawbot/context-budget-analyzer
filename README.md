# context-budget-analyzer

Analyze the token cost of your CLAUDE.md before your agents do.

Every word in your CLAUDE.md gets read on every single agent call. A 4,000-token instruction file costs you 4,000 tokens of context before the agent has done anything. Most of them are bloated. This tool tells you where.

## What it does

- Estimates total token cost (word count * 1.3 — good enough for planning)
- Shows top 5 sections by token cost, so you know what's eating budget
- Classifies content as boilerplate/directive vs. actual config (the ratio matters)
- Flags sections over 500 tokens (bloat risk)
- Spots duplicate concepts — if "do not" appears 40 times, you've over-specified
- Checks for missing critical sections: identity, tool list, output format, memory, rules

No pip install. No API key. Stdlib only.

## Install

```bash
git clone https://github.com/GenesisClawbot/context-budget-analyzer.git
cd context-budget-analyzer
```

Done.

## Usage

```bash
# Analyze a local file
python3 context_budget.py CLAUDE.md

# Analyze a remote file
python3 context_budget.py --url https://raw.githubusercontent.com/user/repo/main/CLAUDE.md

# Pipe it
cat CLAUDE.md | python3 context_budget.py
```

## Example output

```
╔══════════════════════════════════════════════════╗
║       Context Budget Analyzer — Report           ║
╚══════════════════════════════════════════════════╝
  Source: CLAUDE.md

  TOTAL TOKEN ESTIMATE
  3,847 tokens  ████████████████████████░░░░░░░░░░░░░░░░
  !! This file is expensive. Trim before deploying.

  TOP 5 SECTIONS BY TOKEN COST
  1.  1,204 tok  ████████████████████████████  Heartbeat Loop
  2.    634 tok  █████████████░░░░░░░░░░░░░░░  Hard Rules
  3.    489 tok  ██████████░░░░░░░░░░░░░░░░░░  Tool List
  4.    312 tok  ██████░░░░░░░░░░░░░░░░░░░░░░  Memory
  5.    198 tok  ████░░░░░░░░░░░░░░░░░░░░░░░░  Identity

  CONTENT BREAKDOWN
  Boilerplate / directive text:  62%  ████████████░░░░░░░░
  Unique config / spec content:  38%  ████████░░░░░░░░░░░░
  !! Over half your file is rules/warnings. Agents read this every call.
     Consider moving stable rules to a separate shared file.

  FLAGS
  [BLOAT RISK]  2 section(s) exceed 500 tokens:
    - "Heartbeat Loop" (1204 tok)
    - "Hard Rules" (634 tok)

  [DUPLICATE CONCEPTS]  These phrases repeat 10+ times:
    - "do not" appears 34x
    - "must" appears 22x
    - "always" appears 17x

  RECOMMENDATIONS
  1. Split this file. Move stable rules to a shared include file.
  2. High boilerplate ratio. Extract repeated directives into a single Rules section.
  3. "do not" appears 34x. Consolidate into one Rules block.
  4. "Heartbeat Loop" (1204 tok) is your biggest cost. Trim or split it.
```

## Templates

The `templates/` directory has three starter files:

- `templates/minimal-claude.md` — bare-bones CLAUDE.md for simple agents, under 200 words
- `templates/production-claude.md` — full production template with all sections, 400-800 tokens
- `templates/swarm-orchestrator.md` — for meta-orchestrator agents managing a sub-swarm

These are based on patterns from 218 production agent runs. Not filler.

## Paid templates bundle

The free templates cover structure. The paid bundle covers the actual content patterns that have worked in production: memory schemas, tool manifest formats, session budget strategies, multi-agent coordination patterns.

[Context Templates Bundle — buy.stripe.com/COMING_SOON]

---

Built by Jamie Cole. MIT license.
