# Backpack Checker

<div align="center">
    <img src="https://github.com/pkucmus/backpack-checker/raw/main/assets/screenshot.png" alt="Logo" width="300" role="img">
</div>

## Rationale

Let's be honest... I only made it to check the amazing [Textual](https://textual.textualize.io/) on something. But also, there is some merit to it (you can find it if you try very hard :D), working with a team you might want to rely on a tool, like "everyone, let's install [uv](https://docs.astral.sh/uv/guides/scripts/#creating-a-python-script) or [hatch](https://hatch.pypa.io/1.13/how-to/run/python-scripts/) so we can work with [inline script metadata](https://packaging.python.org/en/latest/specifications/inline-script-metadata/)", half of them will ask you after 3 months how to run you script... not to mention any newcomers.

And yeah there are tools or should I say frameworks like Nix and stuff but I don't care how you got the tool or what machine/system you are using, I only care to know if I can rely on the fact that everyone can use Docker Compose in a specific version. 

There might be better tools like this, I didn't look - anyway, if you'll find this useful, thats awesome - it's here for you to use.

## Usage

That this provides is a bunch of **Check** classes and a TUI application made with the amazing [Textual](https://textual.textualize.io/) (I mean honestly the tool is one thing, but the way they made it is something else...).

The idea is that you would install it in whatever manner and write yourself a backpack.py script. Probably the most convienient method would be to use the already mentioned inline script metadata:

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

You can use the premade checkers. To do that you will need to define some data for them. 

As you will see in the examples bellow, you can modify those quite a lot: you can make a `__init__` to provide args to the checker, you can overload the `name` and `explanation` properties to base the verbiage on something dynamic.

For example:

#### SubprocessCheck

```python
from backpack_checker.checker import SubprocessCheck, Necessity

class AWSLocal(SubprocessCheck):
    _name = "Check if `awslocal` is installed"
    _explanation = """\
AWS Local is a wrapper for the AWS CLI that allows you to interface AWS instances that 
are running locally - i.e. with Localstack.

More about awslocal [here](https://github.com/localstack/awscli-local?tab=readme-ov-file#example).

"""
    necessity = Necessity.SUGGESTED
    command = "awslocal --version"
```

This checks if the `awslocal --version` command will execute with return code `0`. The verbiage is to provide instructions for the backpack users. You can use [Markdown](https://textual.textualize.io/widget_gallery/#markdown) when defining the name and explanation. The `necessity` attribute (by default `Necessity.REQUIRED`) will only throw a warning (paint yellow) and mark the failure as nothing wrong.

> [!TIP]  
> So... in this example I'm suggesting you should install `awslocal`, but if you'd rather use `aws --endpoint-url=http://localhost:4566` then it's fine too.

#### MinimalVersionCheck

We can also use the deriative of `SubprocessCheck` which is `MinimalVersionCheck` which makes it faster to check of a tool's existince but with the requirement for a minimal semantiv version.

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

Not everything would respond with just `2.20.3` like `docker-compose --version --short` does in that case you can always overload the `validate` method:

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

Another checker is the `DockerContainerRunning` which will use the [Docker SDK for Python](https://docker-py.readthedocs.io/en/stable/) to interact with your Docker engine to ask for rinnung containers. Effectively invokes `docker.from_env().containers.list(filters=self.container_list_filters)` 

```python
class LocalstackRunning(DockerContainerRunning):
    _name = "Check if Localstack is running"
    _explanation = """..."""
    container_list_filters = {"status": "running", "name": "localstack"}
```

#### EnvVarsRequired and EnvVarsSuggested

These two are checking if you have env vars set:

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
            "Check if `PIP_EXTRA_INDEX_URL` env vars is set",
            ["PIP_EXTRA_INDEX_URL"],
            PIP_EXTRA_INDEX_URL_EXPLANATION,
        ),
    ]
)
```

#### And/Or Checkers

You can also group the checks with `And` and `Or`:

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
This check looks for either `docker-compose` or `docker compose` in the system. Either
one is required to run any of our applications. Additionally, the version of the tool
should be at least `{self.minimal_version}`. That version allows you to use the `include`
directive with relative paths in your `docker-compose.yml` files - we rely on that
feature.
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

The `Or` one will catch any errors and will return a `True` if `any` outcome is positive, `And` will do the same but only report a success once `all` oucomes are succesful. 

## What would be cool

If I ever have time to play with this again, then I would probably:

- [ ] separate the UI (TUI) from the checking process
  - [ ] allow to run the checker with a JSON result that could be used by the UI (possibly multiple UIs)
- [ ] make a CLI entrypoint that would work like `backpack check path/to/your/backpack.py`
- [ ] having any test coverage here would be cool...
