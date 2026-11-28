# Instructions for AI agents

## Rules

The shared rules in `+wit/AGENTS.md` (*Shared rules* section) apply.

- Never use `>nul`, `2>nul` or other `nul` redirects in shell commands — under Git Bash they create a literal `nul` file in the working directory. Use `>/dev/null` / `2>/dev/null` instead.
