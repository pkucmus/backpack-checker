# Backpack Checker

<div align="center">
    <img src="https://github.com/pkucmus/backpack-checker/raw/main/assets/screenshot.png" alt="Logo" width="100%" role="img">
</div>

## Rationale

Let's be honest... I made this mainly to try out the amazing [Textual](https://textual.textualize.io/) on something. But there's some merit to it (if you look hard enough :D). When working with a team, you might want to rely on a tool, like saying, "everyone, let's install [uv](https://docs.astral.sh/uv/guides/scripts/#creating-a-python-script) or [hatch](https://hatch.pypa.io/1.13/how-to/run/python-scripts/) so we can work with [inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)." Half of your team will ask you three months later how to run your script... not to mention any newcomers.

And yeah, there are tools—or should I say frameworks—like Nix and similar ones. But I don't care how you got the tool or what machine/system you are using. I only care to know if I can rely on the fact that everyone can use Docker Compose in a specific version.

There might be better tools for this, but I didn't look. Anyway, if you find this useful, that's awesome—it's here for you to use.

## Usage

What this provides is a bunch of **Check** classes and a TUI application made with the amazing [Textual](https://textual.textualize.io/) (honestly, the tool itself is great, but the way it was made is something else...).

The idea is to install it however you prefer and write a `backpack.py` script. Probably the most convenient method would be to use the aforementioned inline script metadata:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "backpack-checker",
# ]
# ///
import json
from backpack_checker.app import BackpackApp
from backpack_checker.checker import (
    And,
    Check,
    DockerContainerRunning,
    EnvVarsRequired,
    EnvVarsSuggested,
    MinimalVersionCheck,
    Necessity,
    Or,
    SubprocessCheck,
)
from semver import Version

class UVCheck(MinimalVersionCheck):
    _name = "Check if `uv` is installed"
    _explanation = "Check if Docker Compose is installed"
    command = "uv version --output-format=json"
    necessity = Necessity.SUGGESTED

    async def validate(self, result: str) -> bool:
        return self.minimal_version <= Version.parse(json.loads(result)["version"])


app = BackpackApp(
    checks=[UVCheck("0.5.8")]
)
if __name__ == "__main__":
    app.run()
```

and run it with `uv run backpack.py` or `hatch run backpack.py`.

### Checkers

You can use the premade checkers. To do that, you'll need to define some data for them.

As you'll see in the examples below, you can customize these extensively: you can create a `__init__` method to provide arguments to the checker or override the `name` and `explanation` properties to make the messaging dynamic.

For example:

#### SubprocessCheck

```python
from backpack_checker.checker import SubprocessCheck, Necessity

class AWSLocal(SubprocessCheck):
    _name = "Check if `awslocal` is installed"
    _explanation = """\
AWS Local is a wrapper for the AWS CLI that allows you to interface with AWS instances 
running locally, e.g., with Localstack.

More about awslocal [here](https://github.com/localstack/awscli-local?tab=readme-ov-file#example).
"""
    necessity = Necessity.SUGGESTED
    command = "awslocal --version"
```

This checks if the `awslocal --version` command executes with return code `0`. The message is designed to provide instructions for backpack users. You can use [Markdown](https://textual.textualize.io/widget_gallery/#markdown) when defining the name and explanation. The `necessity` attribute (default is `Necessity.REQUIRED`) will only throw a warning (painted yellow) and mark the failure as non-critical.

> [!TIP]  
> In this example, I'm suggesting you install `awslocal`. But if you'd rather use `aws --endpoint-url=http://localhost:4566`, that's fine too.

#### MinimalVersionCheck

You can also use a derivative of `SubprocessCheck`, called `MinimalVersionCheck`, to check for the existence of a tool and enforce a minimal semantic version.

```python
from backpack_checker.checker import MinimalVersionCheck

class DockerComposeCheck(MinimalVersionCheck):
    _name = "Check if `docker-compose` is installed"
    _explanation = "Check if Docker Compose is installed"
    command = "docker-compose --version --short"

app = BackpackApp(
    checks=[
        DockerComposeCheck("2.20.3"),
    ]
)
```

If a command doesn't directly return something like `2.20.3` (as `docker-compose --version --short` does), you can override the `validate` method:

```python
from semver import Version
from backpack_checker.checker import MinimalVersionCheck

class UVCheck(MinimalVersionCheck):
    _name = "Check if `uv` is installed"
    _explanation = "Check if UV is installed"
    command = "uv version --output-format=json"

    async def validate(self, result: str) -> bool:
        return self.minimal_version <= Version.parse(json.loads(result)["version"])

app = BackpackApp(
    checks=[
        UVCheck("0.5.8"),
    ]
)
```

#### DockerContainerRunning

Another checker is `DockerContainerRunning`, which uses the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/) to interact with your Docker engine and query running containers. It effectively invokes `docker.from_env().containers.list(filters=self.container_list_filters)`.

```python
class LocalstackRunning(DockerContainerRunning):
    _name = "Check if Localstack is running"
    _explanation = """..."""
    container_list_filters = {"status": "running", "name": "localstack"}
```

#### EnvVarsRequired and EnvVarsSuggested

These check whether specific environment variables are set:

```python
UV_EXTRA_INDEX_URL_EXPLANATION = """..."""
PIP_EXTRA_INDEX_URL_EXPLANATION = """..."""

app = BackpackApp(
    checks=[
        EnvVarsRequired(
            "Check if `UV_EXTRA_INDEX_URL` env var is set",
            ["UV_EXTRA_INDEX_URL"],
            UV_EXTRA_INDEX_URL_EXPLANATION,
        ),
        EnvVarsSuggested(
            "Check if `PIP_EXTRA_INDEX_URL` env var is set",
            ["PIP_EXTRA_INDEX_URL"],
            PIP_EXTRA_INDEX_URL_EXPLANATION,
        ),
    ]
)
```

#### And/Or Checkers

You can also group checks using `And` or `Or`:

```python
from backpack_checker.checker import MinimalVersionCheck, Or

class _DockerComposeCheck(MinimalVersionCheck):
    _name = ""
    _explanation = ""
    command = "docker-compose --version --short"

class _DockerComposeCheck2(_DockerComposeCheck):
    _name = ""
    command = "docker compose version --short"

class OrDockerCompose(Or[str]):
    _name = "Check if `docker compose` or `docker-compose` are installed"

    @property
    def explanation(self) -> str:
        return f"""\
This check ensures either `docker-compose` or `docker compose` is installed. 
Additionally, the version must be at least `{self.minimal_version}`, which supports 
features like the `include` directive with relative paths in `docker-compose.yml` files. 
We rely on that feature.
"""

    def __init__(self, minimal_version: Version | str):
        super().__init__()
        self.minimal_version = minimal_version
        self.checks = [
            _DockerComposeCheck(minimal_version),
            _DockerComposeCheck2(minimal_version),
        ]

app = BackpackApp(
    checks=[
        OrDockerCompose("2.20.3")
    ]
)
```

The `Or` checker returns `True` if any outcome is positive, while the `And` checker succeeds only if all outcomes are successful.

## What would be cool

If I ever have time to play with this again, I’d probably:

- [ ] Separate the UI (TUI) from the checking process.
  - [ ] Allow running the checker with a JSON result usable by the UI (potentially multiple UIs).
- [ ] Create a CLI entry point that works like `backpack check path/to/your/backpack.py`.
- [ ] Add some test coverage here—it would be cool...
