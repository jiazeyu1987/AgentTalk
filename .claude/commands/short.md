# Short Reply Command Spec

Create a response constraint command that forces Claude Code to reply within a maximum word limit, using plain text only, and formatted into five numbered paragraphs.

---

## Command Name

`/short`

---

## Usage

```
/short-reply <max-words> [optional: extra-instruction]
```

---

## Purpose

This command constrains Claude Code’s response to:
- No more than `<max-words>` words (words are separated by whitespace; numbers count as words).
- Plain text only (no Markdown, no code blocks, no tables, no links).
- Exactly five paragraphs, numbered from 1 to 5.
- Each paragraph should contain one to three sentences unless limited by the word budget.

---

## Core Principles

- Brevity first: prioritize the most important information.
- Strict structure: always output exactly five numbered paragraphs.
- Text-only output: do not use formatting to compress information.
- Constraint compliance: if constraints conflict, apply this priority:
  1. Word limit  
  2. Text-only requirement  
  3. Five-paragraph structure  

---

## Mandatory Output Rules

### 1. Word Limit
- The full response must be less than or equal to `<max-words>`.
- If the request cannot be fully answered, provide a concise summary.

### 2. Text Only
- Do not use Markdown syntax, bullet points, headings, or inline code.
- Do not include code blocks, tables, or links.
- Do not embed JSON, YAML, or diagrams.

### 3. Five Numbered Paragraphs
- Output exactly five paragraphs.
- Each paragraph must begin with:
  - `1. `
  - `2. `
  - `3. `
  - `4. `
  - `5. `
- No additional text before or after these five paragraphs.

### 4. No Meta Commentary
- Do not mention the command or its rules in the response.
- Do not explain how constraints are being followed.

---

## Optional Extra Instruction

If an extra instruction is provided, incorporate it only if it does not violate any of the constraints above.

Example:
```
/short-reply 120 "Focus only on risks and mitigations"
```

---

## Failure Handling

If the assistant cannot fully satisfy the request within the constraints:
- Provide the best possible partial answer within the word limit.
- Use paragraph 5 to state what information was omitted or what follow-up is needed.

---

## Success Criteria

A successful response:
- Contains no more than `<max-words>` words.
- Uses plain text only.
- Is formatted into exactly five numbered paragraphs.
- Contains no references to the command or formatting rules.
