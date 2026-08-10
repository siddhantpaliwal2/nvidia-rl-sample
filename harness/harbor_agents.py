"""Small Harbor agent adapters required by the enterprise task snapshots."""

from harbor.agents.installed.opencode import OpenCode
from harbor.environments.base import BaseEnvironment


class OpenCodeNode22(OpenCode):
    """Keep OpenCode on Node 22 when the base image already has system Node.

    NVM's installer makes the pre-existing system Node version its default.
    Harbor then installs OpenCode under Node 22, but a fresh agent shell loads
    that older default and cannot find the binary. Pinning NVM's default after
    installation makes setup and execution use the same global npm prefix.
    """

    async def install(self, environment: BaseEnvironment) -> None:
        await super().install(environment)
        await self.exec_as_agent(
            environment,
            command=(
                ". ~/.nvm/nvm.sh; "
                "nvm alias default 22 >/dev/null; "
                "nvm use 22 >/dev/null; "
                "opencode --version"
            ),
        )

    def get_version_command(self) -> str:
        return ". ~/.nvm/nvm.sh; nvm use 22 >/dev/null; opencode --version"
