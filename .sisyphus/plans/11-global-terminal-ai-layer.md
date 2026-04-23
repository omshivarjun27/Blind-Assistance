# Plan 11 - User-Scoped Global AI Tooling Layer

## Summary

Create a single user-scoped control plane at `C:\Users\HP\.ai-global` and generate native configs from it for `claude`, `opencode`, `codex`, `gemini`, and `cn`. The shared layer should only globalize the portable pieces that work across terminal agents: MCP server definitions, secret handling through Windows user environment variables, CLI bootstrap/repair, and shared PATH-level LSP binaries.

## Machine facts to preserve

- `claude` and `opencode` already work and should not be reinstalled unless verification fails.
- `codex` and `gemini` shims currently exist but are broken.
- `cn` is not currently installed.
- Docker is available on Windows, so GitHub's official MCP server can use the Docker path.
- `C:\Users\HP\.ai-global` does not exist yet.
- `TAVILY_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`, and `CONTEXT7_API_KEY` are not set as Windows user env vars at planning time.
- Assistant memory files such as `GEMINI.md` are not a source of truth.

## Managed interfaces

- Create `C:\Users\HP\.ai-global\manifest.json` as the control-plane manifest.
- Create `C:\Users\HP\.ai-global\mcp\servers.json` as the canonical shared MCP registry.
- Create `C:\Users\HP\.ai-global\lsp\packages.json` for shared PATH-level LSP packages/binaries.
- Create `C:\Users\HP\.ai-global\env\required-vars.json` with required secret names only.
- Create `C:\Users\HP\.ai-global\reports\compatibility.json` classifying discovered features as `portable`, `tool_specific`, `future_equivalent`, or `unsupported`.
- Create `C:\Users\HP\.ai-global\sync.ps1` with `-Mode DryRun|Apply -Targets claude,opencode,codex,gemini,continue`.
- Create `C:\Users\HP\.ai-global\validate.ps1` with the same targets and per-check timeouts.

## Implementation

### 1. Bootstrap the Windows CLI layer

- Repair `@openai/codex@latest` so `codex --help` works.
- Repair `@google/gemini-cli@latest` so `gemini --help` and `gemini mcp list` work.
- Install `@continuedev/cli@latest` so `cn --version` works.
- Keep the working global `claude` and `opencode` installs unless integrity checks fail.

### 2. Standardize secrets at user scope

- Promote `GITHUB_PERSONAL_ACCESS_TOKEN`, `TAVILY_API_KEY`, and `CONTEXT7_API_KEY` to Windows user environment variables when values can be sourced from the current machine.
- Remove inline secret literals from active managed configs and from generated shared configs.
- Do not destructively rewrite tool-managed history, backup, cache, or transcript files in this rollout.
- Record historical secret exposure in the final report and require token rotation after migration.

### 3. Create a curated shared MCP baseline

The globally managed MCP bundle is:

- `openai-docs` -> remote HTTP `https://developers.openai.com/mcp`
- `github` -> official GitHub MCP server via Docker using `ghcr.io/github/github-mcp-server`
- `tavily` -> `npx -y tavily-mcp`
- `context7` -> `npx -y @upstash/context7-mcp@latest`
- `sequential-thinking` -> `npx -y @modelcontextprotocol/server-sequential-thinking`
- `playwright` -> `npx -y @playwright/mcp@latest`

Do not put `filesystem`, `git`, or `sqlite` into the managed global baseline because they are either redundant with native capabilities or too project-specific.

### 4. Generate native adapters

- Claude: manage user-scope MCP via official Claude MCP commands and preserve existing plugin/workflow settings.
- OpenCode: merge shared MCP servers into `~/.config/opencode/opencode.json`, keep `oh-my-openagent`, keep current agents/hooks/categories/routes, and extend the existing LSP block.
- Codex: write shared MCP servers into `~/.codex/config.toml` using native Codex MCP configuration while preserving existing model/features settings.
- Gemini: merge shared MCP servers into `~/.gemini/settings.json` and avoid using runtime/cache files as the source of truth.
- Continue: install `cn` and materialize shared MCP definitions into `~/.continue/mcpServers/`; keep `config.yaml` minimal unless a safe compatibility tweak is required.

### 5. Upgrade the shared PATH-level LSP set

Keep:

- `bash-language-server`
- `pyright`
- `remark-language-server`
- `vscode-langservers-extracted`
- `yaml-language-server`

Add:

- `typescript-language-server`
- `@tailwindcss/language-server`

Wire the shared LSP bundle into OpenCode only. Do not force LSP into tools that do not expose a stable native LSP config surface.

### 6. Keep tool-native extras native

- Preserve Claude plugins as-is.
- Preserve OpenCode agents/hooks/categories/routes as-is.
- Preserve existing Codex skills and only repair/relink them if a repaired Codex install breaks them.
- Do not promote `CLAUDE.md`, `GEMINI.md`, or similar assistant memory files into the shared layer.
- Use `reports\compatibility.json` to show what stayed tool-specific.

## Verification

- `where claude`, `where opencode`, `where codex`, `where gemini`, `where cn`
- `claude --version`, `opencode --version`, `codex --help`, `gemini --help`, `cn --version`
- `docker run --rm ghcr.io/github/github-mcp-server tool-search "issue" --max-results 1`
- `npx -y tavily-mcp --list-tools`
- `npx -y @upstash/context7-mcp@latest --help`
- `npx -y @modelcontextprotocol/server-sequential-thinking --help`
- `npx -y @playwright/mcp@latest --help`
- `claude mcp list`
- `opencode debug config` and `npx oh-my-opencode doctor --json`
- `codex mcp list`
- `gemini mcp list`
- `cn --version` and a config-parse smoke test
- PATH discovery for the managed LSP binaries
- JSON/TOML/YAML parsing for generated config files
- Validation must use timeouts so one bad MCP server cannot hang the whole run

## Assumptions

- Scope is user-home only, not `C:\Program Files` or `C:\ProgramData`.
- "Most important" means a curated stable set, not every possible tool.
- "Global" means one shared control plane plus generated native adapters, not a single config file shared directly by every CLI.
- No new SaaS accounts are added in this rollout.
- Continue runtime verification beyond install/config parsing depends on existing Continue auth.
- Existing historical secret exposure must be fixed through rotation after migration, not through destructive cache/history rewrites.
