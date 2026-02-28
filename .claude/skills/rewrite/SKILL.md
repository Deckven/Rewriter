---
name: rewrite
description: Batch rewrite files from input_resources/ to output_results/ using the rewriter CLI
user-invocable: true
allowed-tools:
  - Bash
  - Glob
  - Read
---

# Batch Rewrite Skill

Rewrite all source files from `input_resources/` using the `rewriter rewrite` CLI and save results to `output_results/`.

## Instructions

1. **Parse intensity from `$ARGUMENTS`.**
   - The first argument is the rewrite intensity: `light`, `medium`, or `full`.
   - If `$ARGUMENTS` is empty or does not contain a valid intensity, ask the user which intensity to use (light / medium / full).

2. **Discover input files.**
   - Use Glob to find all `*.txt` and `*.md` files in `input_resources/`.
   - If no files are found, inform the user: "No .txt or .md files found in input_resources/. Add files and try again." Then stop.

3. **Rewrite each file.**
   - For each discovered file, run:
     ```
     source .venv/bin/activate && rewriter rewrite "<file_path>" --intensity <intensity> --output "output_results/<filename>"
     ```
   - After each file, report whether it succeeded or failed.

4. **Print summary.**
   - List total files processed, how many succeeded, and how many failed.
   - Example:
     ```
     Rewrite complete: 3/3 succeeded (intensity: medium)
     ```
