# novabucks

CLI tool for signing Maven artifacts through the RADAS signing service.

## Requirements

- Python 3.11+

## Installation

Install the package in editable mode:

```bash
pip install -e .
```

For development (includes pytest, ruff, etc.):

```bash
pip install -e ".[dev]"
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `defusedxml` | Secure XML parsing |
| `jinja2` | Maven metadata templating |
| `oras` | OCI Registry as Storage client |
| `python-qpid-proton` | AMQP messaging for UMB |

## Usage

```bash
novabucks --version
novabucks --help
```

### `sign-repo-url`

Sign all Maven artifacts in a repository URL through the RADAS signing service. Produces a JSON file containing the signing results.

```bash
novabucks sign-repo-url \
  https://example.com/maven/repo \
  --requester "user@redhat.com" \
  --result-path ./sign-result.json \
  --config radas_cfg.json \
  --sign-key "my-sign-key" \
  --ignore-patterns ".*\.md5$" \
  --ignore-patterns ".*\.sha1$"
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--requester` | `-r` | Yes | The requester who sends the signing request |
| `--result-path` | `-p` | Yes | Path to save the sign result JSON file |
| `--config` | `-c` | Yes | RADAS configuration file path (JSON) |
| `--sign-key` | `-k` | Yes | rpm-sign key to use |
| `--ignore-patterns` | `-i` | No | Regex patterns to exclude files from signing (repeatable) |
| `--debug` | `-D` | No | Enable debug logging |
| `--quiet` | `-q` | No | Suppress all logs except warnings and errors |

### `generate_sign_files`

Generate `.asc` signature files from the RADAS sign result JSON. Extracts ZIP archives, processes Maven metadata, and copies artifacts with their signatures to a destination directory.

```bash
novabucks generate_sign_files \
  https://example.com/archive1.zip \
  https://example.com/archive2.zip \
  --product "my-product" \
  --version "1.0.0" \
  --root_path "maven-repository" \
  --destination_dir ./signed-artifacts \
  --sign_result_file ./sign-result.json \
  --ignore_patterns ".*\.md5$"
```

| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--product` | `-p` | Yes | - | Product key, combined with version for metadata |
| `--version` | `-v` | Yes | - | Product version, combined with key for metadata |
| `--root_path` | `-r` | No | `maven-repository` | Root path in the tarball before real Maven paths |
| `--ignore_patterns` | `-i` | No | - | Regex patterns to exclude files (repeatable) |
| `--work_dir` | `-w` | No | auto | Temporary directory for archive extraction |
| `--destination_dir` | `-o` | No | `signed-artifacts` | Output directory for signed files |
| `--sign_result_file` | `-l` | No | - | Path to the RADAS signing result JSON file |
| `--debug` | `-D` | No | - | Enable debug logging |
| `--quiet` | `-q` | No | - | Suppress all logs except warnings and errors |

### RADAS Configuration

Both commands require a RADAS configuration file (`--config` / `--sign_result_file`) for communicating with the signing service over UMB (Unified Message Bus). Example `radas_cfg.json`:

```json
{
  "umb_host": "umb.stage.api.redhat.com",
  "result_queue": "Consumer.<consumer-name>.VirtualTopic.eng.robosignatory.mrrc.sign.>",
  "request_channel": "topic://VirtualTopic.eng.mrrc-signing-pipeline.mrrc.sign",
  "client_ca": "/path/to/client.crt",
  "client_key": "/path/to/client.pem",
  "client_key_pass_file": "/path/to/client.pw",
  "root_ca": "/path/to/ca-bundle.crt",
  "radas_receiver_timeout": 3600
}
```

| Field | Description |
|-------|-------------|
| `umb_host` | UMB message broker hostname |
| `result_queue` | AMQP queue for receiving signing results |
| `request_channel` | AMQP topic for sending signing requests |
| `client_ca` | Path to the client CA certificate |
| `client_key` | Path to the client private key |
| `client_key_pass_file` | Path to file containing the private key passphrase |
| `root_ca` | Path to the root CA bundle |
| `radas_receiver_timeout` | Timeout in seconds for waiting on signing results |

## Development

### Running Tests

```bash
pytest
```

Or via tox:

```bash
tox -e py311
```

### Code Standards

The project enforces the following standards, all configured with a **120-character line length** and targeting **Python 3.11**:

- **Black** -- Code formatter (skip string normalization with `-S`)
- **Ruff** -- Linter with rules: `E` (pycodestyle errors), `F` (pyflakes), `W` (pycodestyle warnings), `I` (import sorting)
- **Flake8** -- Additional style checking
- **Bandit** -- Security vulnerability scanning
- **pip-audit** -- Dependency vulnerability scanning

### Linting and Formatting

Check formatting (no changes applied):

```bash
tox -e black
```

Auto-format code:

```bash
tox -e black-format
```

Run ruff:

```bash
tox -e ruff
```

Run flake8:

```bash
tox -e flake8
```

### Security Checks

```bash
tox -e bandit
tox -e pip-audit
```

### Running All Checks

```bash
tox
```

This runs all environments: `py311`, `flake8`, `black`, `ruff`, `bandit`, `pip-audit`.

## License

Apache License 2.0
