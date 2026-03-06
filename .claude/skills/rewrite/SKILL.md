---
name: rewrite
description: Rewrite text in the blog's style using the style guide directly (no API key needed)
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Glob
---

# Rewrite Skill

Rewrite text in the style of the gaming blog "Блог казуального геймера", using the style guide at `data/style_guide.md`.

## Instructions

1. **Read the style guide.**
   - Read `data/style_guide.md` to load the blog's voice, tone, lexicon, and formatting rules.

2. **Determine input.**
   - If `$ARGUMENTS` contains inline text (quoted or not), use it directly as input.
   - If `$ARGUMENTS` contains a file path, read that file.
   - If `$ARGUMENTS` is empty, look for `*.txt` and `*.md` files in `input_resources/`. If multiple files found, process each one and save results to `output_results/` with the same filename.
   - If no input found at all, ask the user to provide text or a file.

3. **Parse options from `$ARGUMENTS`.**
   - `light` / `medium` / `full` — rewrite intensity. Default: `medium`.
     - **light**: minimal changes — adjust tone and individual phrases, keep structure intact.
     - **medium**: noticeable stylization — rewrite sentences in blog style, adapt lexicon and rhythm, keep overall structure.
     - **full**: deep rewrite — freely restructure, add blog-typical elements (intro, transitions, conclusion).

4. **Rewrite the text.**
   Apply the style guide rules:
   - Use gaming slang naturally where appropriate (but match the source material's domain — don't force WoW jargon into EVE Online text, etc.)
   - Maintain factual accuracy — do not add or remove information
   - Write in Russian
   - Use short paragraphs (2-4 sentences), vary sentence length
   - Apply bold for game names, key terms, important numbers
   - Use characteristic phrases and transitions from the style guide
   - Add a personal, friendly-expert tone — not dry facts, not vulgar
   - Do NOT use profanity or vulgar expressions — convey emotion through irony, metaphors, and tone
   - End with a signature phrase like "Такие дела.", "Оставайтесь на линии." or similar

5. **Output the result.**
   - If processing a single text/file from arguments, output the rewritten text directly.
   - If batch-processing `input_resources/`, save each result to `output_results/<filename>` using Write, and print a summary.
