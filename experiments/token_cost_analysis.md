# Mask Character Token Cost Analysis

**Date**: 2026-03-06
**Method**: `anthropic.messages.count_tokens()` with `claude-3-haiku-20240307`
**Note**: Claude family shares the same tokenizer across models.

## Character Comparison (repeated 20x)

| Char | Name | 10x tok | 20x tok | 50x tok | tok/char |
|------|------|---------|---------|---------|----------|
| `█` | FULL BLOCK (current) | 4 | 6 | 14 | **0.28** |
| `░` | LIGHT SHADE | 11 | 21 | 51 | 1.05 |
| `■` | BLACK SQUARE | 11 | 21 | — | 1.05 |
| `·` | MIDDLE DOT | — | 3 | — | 0.15 |
| `~` | TILDE | — | 3 | — | 0.15 |
| `*` | ASTERISK | — | 2 | — | 0.10 |
| `…` | ELLIPSIS | — | 8 | — | 0.40 |
| `-` | HYPHEN | — | 2 | — | 0.10 |

**Finding**: `█` is the best visual mask character. Claude's tokenizer compresses
repeated `█` efficiently (~0.28 tok/char). Other Unicode blocks (░, ■) cost 3.5x more.
ASCII chars (`*`, `-`, `~`) are cheaper but conflict with normal text/markdown.

## Real String Comparisons

| String | chars | tokens |
|--------|-------|--------|
| `security-audit-research.org` (original) | 27 | 7 |
| `███████████████████████████` (█ masked) | 27 | 8 |
| `/Users/henry/.claude/projects/` (original) | 30 | 9 |
| `██████████████████████████████` (█ masked) | 30 | 9 |
| `sk-ant-abc123xyz` (original) | 16 | 7 |
| `████████████████` (█ masked) | 16 | 5 |

**Finding**: For individual strings, `█` masking costs roughly the same as original text.
The token inflation comes from elsewhere.

## The Real Problem: Fragmentation Breaks Tokenizer Merging

| Original | tokens | After shielding | tokens |
|----------|--------|-----------------|--------|
| `instructions` | 1 | `inst████████s` | 4 |
| `immediately` | 1 | `imm███████ly` | 5 |
| `The previous instructions are now deprecated` | 6 | `███ ████████ instructions ███ ███ ██████████` | 18 |

**Root cause**: The tokenizer compresses `instructions` into 1 token. After stride masking,
it becomes `inst` + `████████` + `s` = 4 tokens. Every fragmented word multiplies token count.
This is inherent to stride masking — destroying syntax also destroys tokenizer compression.

## Full Shield Output Token Cost

Test input: 430-char English attack payload (SYSTEM OVERRIDE prompt injection)

| Strategy | chars | tokens | vs original |
|----------|-------|--------|-------------|
| Original text | 430 | 113 | baseline |
| Full `█████████` masks | 433 | 164 | **+45%** |
| Collapse `█+` → `██` | 346 | 151 | +34% |
| Collapse `█+` → `█` | 319 | 128 | **+13%** |
| Remove all `█` | 286 | 86 | -24% |

## Conclusions

1. **`█` is the optimal mask character** — best visual clarity with good compression (0.28 tok/char).
   Other Unicode blocks cost 3.5x more. No change needed.

2. **Token inflation (+45%) is caused by word fragmentation**, not the `█` character itself.
   Stride masking breaks tokenizer merge boundaries, turning 1-token words into 3-5 tokens.

3. **Collapsing to single `█` reduces cost to +13%** but may reduce security (more readable =
   more attackable). Requires F1 re-evaluation before adopting.

4. **Removing `█` entirely saves 24%** but loses the "something is hidden here" signal.
   May be useful for a future `mode="compact"` option.

5. **Current design (`█` with full-length masks) is the safe default.** The +45% token cost
   is the price of security. Optimization options exist but need security re-validation.
