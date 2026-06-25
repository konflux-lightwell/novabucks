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

**Using a config file:**

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

**Using environment variables:**

```bash
export RADAS_UMB_HOST="umb.stage.api.redhat.com"
export RADAS_RESULT_QUEUE="Consumer.<name>.VirtualTopic.eng.robosignatory.mrrc.sign.>"
export RADAS_REQUEST_CHANNEL="topic://VirtualTopic.eng.mrrc-signing-pipeline.mrrc.sign"
export RADAS_CLIENT_CA="/path/to/client.crt"
export RADAS_CLIENT_KEY="/path/to/client.pem"
export RADAS_CLIENT_KEY_PASS_FILE="/path/to/client.pw"

novabucks sign-repo-url \
  https://example.com/maven/repo \
  --requester "user@redhat.com" \
  --result-path ./sign-result.json \
  --config-from-env \
  --sign-key "my-sign-key"
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--requester` | `-r` | Yes | The requester who sends the signing request |
| `--result-path` | `-p` | Yes | Path to save the sign result JSON file |
| `--config` | `-c` | No* | RADAS configuration file path (JSON) |
| `--config-from-env` | `-e` | No* | Read RADAS configuration from `RADAS_*` environment variables |
| `--sign-key` | `-k` | Yes | rpm-sign key to use |
| `--ignore-patterns` | `-i` | No | Regex patterns to exclude files from signing (repeatable) |
| `--debug` | `-D` | No | Enable debug logging |
| `--quiet` | `-q` | No | Suppress all logs except warnings and errors |

\* Exactly one of `--config` or `--config-from-env` must be provided. They are mutually exclusive.

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

The `sign-repo-url` command requires RADAS configuration for communicating with the signing service over UMB (Unified Message Bus). Configuration can be provided via a JSON file (`--config`) or environment variables (`--config-from-env`).

#### JSON file

Example `radas_cfg.json`:

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

The JSON file also supports a nested layout under a `"radas"` key, and may include an `"ignore_patterns"` list.

#### Environment variables

When using `--config-from-env`, each configuration field is read from a corresponding `RADAS_*` environment variable. Only set variables are included; unset variables fall back to their defaults.

| Environment Variable | JSON Field | Default | Description |
|---------------------|------------|---------|-------------|
| `RADAS_UMB_HOST` | `umb_host` | *(required)* | UMB message broker hostname |
| `RADAS_UMB_HOST_PORT` | `umb_host_port` | `5671` | UMB message broker port |
| `RADAS_RESULT_QUEUE` | `result_queue` | *(required)* | AMQP queue for receiving signing results |
| `RADAS_REQUEST_CHANNEL` | `request_channel` | *(required)* | AMQP topic for sending signing requests |
| `RADAS_CLIENT_CA` | `client_ca` | - | Path to the client CA certificate |
| `RADAS_CLIENT_KEY` | `client_key` | - | Path to the client private key |
| `RADAS_CLIENT_KEY_PASS_FILE` | `client_key_pass_file` | - | Path to file containing the private key passphrase |
| `RADAS_ROOT_CA` | `root_ca` | `/etc/pki/tls/certs/ca-bundle.crt` | Path to the root CA bundle |
| `RADAS_QUAY_REGISTRY_CONFIG` | `quay_radas_registry_config` | - | Path to quay registry config for ORAS |
| `RADAS_SIGN_TIMEOUT_RETRY_COUNT` | `radas_sign_timeout_retry_count` | `10` | Number of retry attempts on send failure |
| `RADAS_SIGN_TIMEOUT_RETRY_INTERVAL` | `radas_sign_timeout_retry_interval` | `60` | Seconds between retries |
| `RADAS_RECEIVER_TIMEOUT` | `radas_receiver_timeout` | `1800` | Timeout in seconds for waiting on signing results |

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
