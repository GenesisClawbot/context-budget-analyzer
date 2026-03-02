#!/usr/bin/env python3
"""
context_budget.py — Context Budget Analyzer
Analyze the token cost of your CLAUDE.md before your agents do.

Usage:
  python3 context_budget.py path/to/CLAUDE.md
  python3 context_budget.py --url https://example.com/CLAUDE.md

No external dependencies. Stdlib only.
"""

import sys
import re
import os
import argparse
import urllib.request
import urllib.error
from collections import Counter


# ── Token estimation ──────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Simple word count * 1.3 proxy for token estimation."""
    words = len(text.split())
    return round(words * 1.3)


# ── Section parsing ───────────────────────────────────────────────────────────

def parse_sections(text: str) -> list[dict]:
    """
    Split markdown into sections by H1/H2/H3 headers.
    Returns list of {title, level, content, tokens}.
    """
    lines = text.split('\n')
    sections = []
    current_title = '(preamble)'
    current_level = 0
    current_lines = []

    for line in lines:
        m = re.match(r'^(#{1,3})\s+(.*)', line)
        if m:
            # flush current section
            if current_lines:
                content = '\n'.join(current_lines).strip()
                sections.append({
                    'title': current_title,
                    'level': current_level,
                    'content': content,
                    'tokens': estimate_tokens(content),
                })
            current_title = m.group(2).strip()
            current_level = len(m.group(1))
            current_lines = []
        else:
            current_lines.append(line)

    # flush last section
    if current_lines:
        content = '\n'.join(current_lines).strip()
        sections.append({
            'title': current_title,
            'level': current_level,
            'content': content,
            'tokens': estimate_tokens(content),
        })

    return [s for s in sections if s['content']]


# ── Boilerplate detection ─────────────────────────────────────────────────────

BOILERPLATE_PATTERNS = [
    r'\bdo not\b',
    r'\bdo NOT\b',
    r'\bnever\b',
    r'\balways\b',
    r'\bmust\b',
    r'\brequired\b',
    r'\bimportant\b',
    r'\bnote that\b',
    r'\bplease\b',
    r'\bensure\b',
    r'\bmake sure\b',
    r'\bremember\b',
    r'\byou (are|should|must|will|can)\b',
    r'\bif you\b',
    r'\bdo not forget\b',
]

BOILERPLATE_SECTION_KEYWORDS = [
    'rule', 'note', 'important', 'warning', 'caution',
    'always', 'never', 'must', 'required', 'mandatory',
    'reminder', 'step', 'instruction',
]

def classify_boilerplate(sections: list[dict]) -> tuple[int, int]:
    """
    Return (boilerplate_tokens, unique_tokens).
    Boilerplate = sections whose title or content are heavy with
    directive/warning language vs. actual config/spec content.
    """
    boilerplate_tokens = 0
    unique_tokens = 0

    for s in sections:
        title_lower = s['title'].lower()
        is_boilerplate = any(kw in title_lower for kw in BOILERPLATE_SECTION_KEYWORDS)

        if not is_boilerplate:
            # check content density of directive phrases
            content_lower = s['content'].lower()
            directive_matches = sum(
                1 for p in BOILERPLATE_PATTERNS
                if re.search(p, content_lower)
            )
            # if more than half the patterns match, likely boilerplate-heavy
            if directive_matches >= len(BOILERPLATE_PATTERNS) * 0.4:
                is_boilerplate = True

        if is_boilerplate:
            boilerplate_tokens += s['tokens']
        else:
            unique_tokens += s['tokens']

    return boilerplate_tokens, unique_tokens


# ── Flag: duplicate concepts ──────────────────────────────────────────────────

CONCEPT_PATTERNS = {
    '"do not"': r'\bdo not\b',
    '"never"': r'\bnever\b',
    '"always"': r'\balways\b',
    '"must"': r'\bmust\b',
    '"important"': r'\bimportant\b',
    '"you should"': r'\byou should\b',
    '"make sure"': r'\bmake sure\b',
    '"ensure"': r'\bensure\b',
    '"step"': r'\bstep\b',
    '"rule"': r'\brule\b',
}

def find_duplicate_concepts(text: str) -> list[tuple[str, int]]:
    """Find phrases/concepts repeated 10+ times. Returns [(concept, count)]."""
    findings = []
    text_lower = text.lower()
    for label, pattern in CONCEPT_PATTERNS.items():
        count = len(re.findall(pattern, text_lower))
        if count >= 10:
            findings.append((label, count))
    return sorted(findings, key=lambda x: -x[1])


# ── Flag: missing critical sections ──────────────────────────────────────────

CRITICAL_SECTIONS = {
    'system prompt / identity': [
        r'(system prompt|who you are|identity|persona|role:)',
        r'(you are|you\'re) (a |an |the )?\w+',
    ],
    'tool list': [
        r'(tool|function|command|script|api)',
        r'(available|use|allowed)\s+(tools|functions|commands)',
    ],
    'output format': [
        r'(output format|response format|format:|how to respond)',
        r'(reply|respond|write|format) (as|with|in)',
    ],
    'memory / state': [
        r'(memory|state|persist|remember|session)',
    ],
    'safety / rules': [
        r'(do not|never|hard rule|forbidden|prohibited|must not)',
    ],
}

def check_missing_sections(text: str) -> list[str]:
    """Return list of critical section names that appear absent."""
    text_lower = text.lower()
    missing = []
    for section_name, patterns in CRITICAL_SECTIONS.items():
        found = any(re.search(p, text_lower) for p in patterns)
        if not found:
            missing.append(section_name)
    return missing


# ── Terminal formatting ───────────────────────────────────────────────────────

BOLD = '\033[1m'
RED = '\033[91m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
CYAN = '\033[96m'
DIM = '\033[2m'
RESET = '\033[0m'

def bar(value: int, max_value: int, width: int = 30, color: str = CYAN) -> str:
    if max_value == 0:
        filled = 0
    else:
        filled = round((value / max_value) * width)
    return color + '█' * filled + DIM + '░' * (width - filled) + RESET

def token_risk_color(tokens: int) -> str:
    if tokens > 1000:
        return RED
    if tokens > 500:
        return YELLOW
    return GREEN


# ── Main report ───────────────────────────────────────────────────────────────

def run_analysis(text: str, source_label: str):
    total_tokens = estimate_tokens(text)
    sections = parse_sections(text)
    top5 = sorted(sections, key=lambda s: -s['tokens'])[:5]
    boilerplate_tokens, unique_tokens = classify_boilerplate(sections)
    total_classified = boilerplate_tokens + unique_tokens
    bp_pct = round((boilerplate_tokens / total_classified) * 100) if total_classified else 0
    uq_pct = 100 - bp_pct

    dupes = find_duplicate_concepts(text)
    missing = check_missing_sections(text)
    bloat_sections = [s for s in sections if s['tokens'] > 500]

    # ── Header ────────────────────────────────────────────────────────────────
    print()
    print(BOLD + '╔══════════════════════════════════════════════════╗' + RESET)
    print(BOLD + '║       Context Budget Analyzer — Report           ║' + RESET)
    print(BOLD + '╚══════════════════════════════════════════════════╝' + RESET)
    print(DIM + f'  Source: {source_label}' + RESET)
    print()

    # ── Total token cost ──────────────────────────────────────────────────────
    risk_col = token_risk_color(total_tokens)
    print(BOLD + '  TOTAL TOKEN ESTIMATE' + RESET)
    print(f'  {risk_col}{BOLD}{total_tokens:,} tokens{RESET}  {bar(min(total_tokens, 8000), 8000, 40, risk_col)}')
    if total_tokens > 4000:
        print(f'  {RED}  !! This file is expensive. Trim before deploying.{RESET}')
    elif total_tokens > 2000:
        print(f'  {YELLOW}  ⚠  Getting heavy. Consider splitting into focused files.{RESET}')
    else:
        print(f'  {GREEN}  ✓ Reasonable size. Under 2k tokens.{RESET}')
    print()

    # ── Top 5 sections by token cost ─────────────────────────────────────────
    print(BOLD + '  TOP 5 SECTIONS BY TOKEN COST' + RESET)
    if not top5:
        print('  (no sections found — is this a markdown file?)')
    else:
        max_sec_tokens = top5[0]['tokens']
        for i, s in enumerate(top5, 1):
            col = token_risk_color(s['tokens'])
            indent = '  ' * (s['level'] - 1) if s['level'] > 0 else ''
            title = indent + s['title'][:50]
            print(f'  {i}. {col}{s["tokens"]:>5} tok{RESET}  {bar(s["tokens"], max_sec_tokens, 25, col)}  {title}')
    print()

    # ── Boilerplate vs unique ─────────────────────────────────────────────────
    print(BOLD + '  CONTENT BREAKDOWN' + RESET)
    print(f'  Boilerplate / directive text:  {YELLOW}{bp_pct}%{RESET}  {bar(bp_pct, 100, 20, YELLOW)}')
    print(f'  Unique config / spec content:  {GREEN}{uq_pct}%{RESET}  {bar(uq_pct, 100, 20, GREEN)}')
    if bp_pct > 50:
        print(f'  {RED}  !! Over half your file is rules/warnings. Agents read this every call.{RESET}')
        print(f'  {DIM}     Consider moving stable rules to a separate shared file.{RESET}')
    print()

    # ── Flags ─────────────────────────────────────────────────────────────────
    flags = []

    if bloat_sections:
        flags.append(('BLOAT RISK', RED,
            f'{len(bloat_sections)} section(s) exceed 500 tokens:',
            [f'  - "{s["title"]}" ({s["tokens"]} tok)' for s in bloat_sections[:5]]
        ))

    if dupes:
        lines = [f'  - {label} appears {count}x' for label, count in dupes[:6]]
        flags.append(('DUPLICATE CONCEPTS', YELLOW,
            'These phrases repeat 10+ times (likely over-specified):',
            lines
        ))

    if missing:
        flags.append(('MISSING SECTIONS', YELLOW,
            'Expected sections not detected:',
            [f'  - {m}' for m in missing]
        ))

    if flags:
        print(BOLD + '  FLAGS' + RESET)
        for flag_name, col, summary, detail_lines in flags:
            print(f'  {col}{BOLD}[{flag_name}]{RESET}  {summary}')
            for dl in detail_lines:
                print(f'  {DIM}{dl}{RESET}')
            print()
    else:
        print(f'  {GREEN}  ✓ No major flags. File looks clean.{RESET}')
        print()

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = []

    if total_tokens > 3000:
        recs.append('Split this file. Move stable rules to a shared include file.')
    if bp_pct > 60:
        recs.append('High boilerplate ratio. Extract repeated directives into a single Rules section.')
    if dupes:
        top_dupe = dupes[0]
        recs.append(f'{top_dupe[0]} appears {top_dupe[1]}x. Consolidate into one Rules block.')
    if bloat_sections:
        recs.append(f'"{bloat_sections[0]["title"]}" ({bloat_sections[0]["tokens"]} tok) is your biggest cost. Trim or split it.')
    if missing:
        recs.append(f'Add missing: {", ".join(missing[:2])}. Agents perform better with explicit specs.')
    if not recs:
        recs.append('Looks good. Keep sections tight as the file grows.')

    print(BOLD + '  RECOMMENDATIONS' + RESET)
    for i, r in enumerate(recs, 1):
        print(f'  {i}. {r}')
    print()

    # ── Footer ────────────────────────────────────────────────────────────────
    print(DIM + '  ─────────────────────────────────────────────────' + RESET)
    print(DIM + '  Token estimate = word_count * 1.3. Actual may vary by model.' + RESET)
    print(DIM + '  Paid template bundle: buy.stripe.com/COMING_SOON' + RESET)
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def fetch_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'context-budget-analyzer/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        print(f'HTTP error fetching URL: {e.code} {e.reason}', file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f'Failed to fetch URL: {e.reason}', file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze the token cost of your CLAUDE.md before your agents do.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  python3 context_budget.py CLAUDE.md
  python3 context_budget.py path/to/AGENTS.md
  python3 context_budget.py --url https://raw.githubusercontent.com/user/repo/main/CLAUDE.md
''',
    )
    parser.add_argument('file', nargs='?', help='Path to markdown file to analyze')
    parser.add_argument('--url', metavar='URL', help='Fetch and analyze a remote markdown file')

    args = parser.parse_args()

    if args.url and args.file:
        parser.error('Provide either a file path or --url, not both.')

    if args.url:
        text = fetch_url(args.url)
        source_label = args.url
    elif args.file:
        if not os.path.exists(args.file):
            print(f'File not found: {args.file}', file=sys.stderr)
            sys.exit(1)
        with open(args.file, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        source_label = args.file
    else:
        # read from stdin if piped
        if not sys.stdin.isatty():
            text = sys.stdin.read()
            source_label = '(stdin)'
        else:
            parser.print_help()
            sys.exit(0)

    if not text.strip():
        print('File is empty.', file=sys.stderr)
        sys.exit(1)

    run_analysis(text, source_label)


if __name__ == '__main__':
    main()
