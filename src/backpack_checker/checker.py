import logging
import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum

import docker
from semver import Version

LOGGER = logging.getLogger(__name__)


class Necessity(Enum):
    REQUIRED = "required"
    SUGGESTED = "suggested"


class CheckError(Exception):
    pass


class CheckExecuteError(CheckError):
    pass


class CheckValidateError(CheckError):
    pass


class BaseCheck[ResultType](ABC):
    result: ResultType | None = None
    necessity: Necessity = Necessity.REQUIRED
    _name: str | None = None
    _explanation: str | None = None

    @property
    def explanation(self) -> str:
        if not self._explanation:
            raise NotImplementedError(
                f"{self.__class__.__name__}._explanation is not set"
            )
        return self._explanation

    @property
    def name(self) -> str:
        if not self._name:
            raise NotImplementedError(f"{self.__class__.__name__}._name is not set")
        return self._name

    def reset(self) -> None:
        self.result = None

    @abstractmethod
    async def run(self) -> bool: ...

    async def __call__(self) -> bool:
        return await self.run()


class Check[ResultType](BaseCheck[ResultType], ABC):
    async def run(self) -> bool:
        if self.result is None:
            try:
                self.result = await self.execute()
                LOGGER.info(
                    "Result from %s: %s",
                    self.__class__.__name__,
                    self.result,
                    extra={"check": self, "__class__": self.__class__},
                )
            except CheckExecuteError as exc:
                LOGGER.error(str(exc))
                raise exc
            except Exception as exc:
                raise CheckExecuteError(f"Check failed: {exc}") from exc
        try:
            return await self.validate(self.result)
        except CheckValidateError as exc:
            raise exc
        except Exception as exc:
            raise CheckValidateError(f"Check failed: {exc}") from exc

    @abstractmethod
    async def execute(self) -> ResultType: ...

    @abstractmethod
    async def validate(self, result: ResultType) -> bool: ...


class Or[ResultType](BaseCheck[ResultType]):
    checks: Sequence[BaseCheck[ResultType]]

    async def __call__(self) -> bool:
        return await self.run()

    async def run(self) -> bool:
        outcomes: list[bool] = []
        for check in self.checks:
            try:
                outcome = await check()
                self.result = check.result
                outcomes.append(outcome)
            except CheckError:
                outcomes.append(False)
                LOGGER.error(
                    "%s check %s failed",
                    self.__class__.__name__,
                    check.__class__.__name__,
                    extra={"check": check, "__class__": self.__class__},
                )
        return await self.validate(outcomes)

    async def validate(self, outcomes: list[bool]) -> bool:
        return any(outcomes)


class And[ResultType](Or[ResultType]):
    async def validate(self, outcomes: list[bool]) -> bool:
        return all(outcomes)


class SubprocessCheck(Check[str]):
    command: str

    async def execute(self) -> str:
        try:
            result = subprocess.run(
                shlex.split(self.command), capture_output=True, text=True
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CheckExecuteError(f"Command failed: {self.command}") from exc
        if not result.returncode == 0:
            raise CheckExecuteError(f"Command failed: {self.command}, {result.stderr}")

        return result.stdout

    async def validate(self, result: str) -> bool:
        return True


class MinimalVersionCheck(SubprocessCheck):
    def __init__(self, minimal_version: Version | str):
        if isinstance(minimal_version, str):
            minimal_version = Version.parse(minimal_version)
        self.minimal_version = minimal_version

    async def validate(self, result: str) -> bool:
        return self.minimal_version <= Version.parse(result)


class DockerContainerRunning(Check[int]):
    container_list_filters: dict[str, str]

    async def execute(self) -> int:
        client = docker.from_env()
        containers = client.containers.list(filters=self.container_list_filters)
        return len(containers)

    async def validate(self, result: int) -> bool:
        return result > 0


class EnvVarsRequired(Check[list[str | None]]):
    var: str
    necessity: Necessity = Necessity.REQUIRED

    def __init__(self, name: str, vars: list[str], explanation: str):
        self._name = name
        self.vars = vars
        self._explanation = explanation

    async def execute(self) -> list[str | None]:
        return [os.getenv(var) for var in self.vars]

    async def validate(self, result: list[str | None]) -> bool:
        return all(result)


class EnvVarsSuggested(EnvVarsRequired):
    necessity: Necessity = Necessity.SUGGESTED
