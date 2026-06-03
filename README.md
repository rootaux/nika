# Nika

## Overview

Nika is an open-source static application security testing (SAST) tool for backend codebases. It performs cross-file analysis to identify security vulnerabilities and can optionally run an LLM-assisted review stage to reduce false positives in reported findings.

Nika combines multiple open-source tools called engines in scan pipeline:

- Astrail for source discovery and data-flow analysis
- OpenGrep for sink discovery

Nika produces a scan report and is designed to be run either through Docker or through a native local environment.

## Core Capabilities

- Cross-file taint analysis for security vulnerability detection
- Config-driven vulnerability selection
- Optional LLM-powered finding review
- Native and Docker-based execution paths
- HTML report generation with scan summary information
- Extensible architecture for adding languages, engines, and vulnerability plugins

## Current Scope

At present, Nika supports:

- Language: Java
- Input: a local source directory or repository checkout
- Output: an HTML report file
- Optional branch inputs for PR review

## Requirements

### Runtime Requirements

- JDK 17 or later
- Python 3.10 or later
- 4 GB RAM minimum
- 8 GB RAM recommended for larger scans
- `coreutils`
- `curl` and `unzip` for native bootstrap flows
- macOS or Linux
- `x86_64` or `arm64`

### Docker Requirements

- Docker installed and available on `PATH`

## Installation Options

Nika supports two execution models:

1. Docker, which is the simplest option for most users.
2. Native execution, which is useful when you want local tool caching or direct environment control.

## Configuration

Nika loads its settings from YAML configuration.

- Default sample config: `config/crtConfig.yml`
- Native bootstrap config target: `config/native-crtConfig.yml`

The configuration controls scan behavior, enabled vulnerabilities, engine tool paths, and optional LLM review settings.

### Important Configuration Fields

1. `API_KEY`: API key for an OpenAI-compatible LLM provider.
2. `LLM_URL`: Base URL for the LLM endpoint or gateway.
3. `Model`: Model identifier used for LLM review.
4. `MAX_TOOL_CALLS`: Upper bound for agent tool execution.
5. `RECURSION_LIMIT`: Guardrail for agent recursion depth.
6. `llm_review_enabled`: Enables LLM-assisted false-positive review.
7. `aggressiveScan`: Enables a more aggressive reachability-oriented mode that may increase false positives.
8. `vulnerabilityConfig`: List of vulnerabilities to enable during a scan.
9. `sources.annotations`: Source annotations that should be treated as taint origins.
10. `vulnerabilityArgs`: Per-vulnerability arguments, such as keyword lists.
11. `tools`: Paths or tool configuration for engines such as Astrail and OpenGrep.

Use the sample config as the baseline and create an environment-specific variant when needed.

## Running Nika

### Option 1: Docker Workflow

Build the image:

```bash
./build.sh
```

Run a scan:

```bash
./run.sh --path /absolute/path/to/code --config /absolute/path/to/crtConfig.yml --output report.html
```

Notes:

- `--path` is required.
- `--config` is required for the Docker wrapper.
- If `--output` is omitted, the wrapper defaults to `./report.html`.
- Report will be available in scan path.

### Option 2: Native Workflow

Bootstrap the local environment:

```bash
./native-build.sh
```

Run a scan:

```bash
./native-run.sh --path /absolute/path/to/code --output /absolute/path/to/report.html
```

The native runner automatically uses the generated native configuration and can rerun bootstrap if required.

To force a fresh bootstrap before execution:

```bash
./native-run.sh --bootstrap --path /absolute/path/to/code --output report.html
```

## CLI Reference

The scanner entry point accepts the following primary arguments:

- `--path`: Path to the source directory or repository to analyze
- `--lang`: Programming language to analyze, defaults to `java`
- `--output`: Destination path for the generated HTML report, defaults to `report.html`
- `--config`: Path to the YAML configuration file, defaults to `config/crtConfig.yml`
- `--source_branch`: Optional source branch for branch-aware workflows
- `--target_branch`: Optional target branch for comparison workflows

Example direct invocation:

```bash
python main.py --path /absolute/path/to/code --config /absolute/path/to/crtConfig.yml --output report.html
```