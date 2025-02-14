# SPDX-License-Identifier: Apache-2.0
#
# Copyright 2025 Firdaus Hakimi <hakimifirdaus944@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib

from pyrogram.client import Client
from pyrogram.types import BotCommand


class CommandHelps:
    """Manages all the commands and its description for the bot."""

    def __init__(self, app: Client) -> None:
        """Initialize CommandHelps.

        Args:
            app (Client): The Pyrogram Client instance to be used for command handling.

        """
        self.commands: dict[str, str] = {}
        self.app: Client = app

    def add_commands(self, commands: str | list[str], description: str) -> None:
        """Add command(s). Replaces commands if they already exist.

        Args:
            commands (Union[str, list[str]]): The commands. Pass a list if you have
                mutiple aliases.
            description (str): Description of the commands.

        """
        if isinstance(commands, str):
            commands = [commands]

        for cmd in commands:
            self.commands.update({cmd: description})

    def remove_commands(self, commands: str | list[str]) -> None:
        """Remove command(s).

        Args:
            commands (Union[str, list[str]]): The commands. Pass a list if you have
                multiple alises to be removed.

        Raises:
            Nothing. KeyError-s are caught.

        """
        if isinstance(commands, str):
            commands = [commands]

        for cmd in commands:
            with contextlib.suppress(KeyError):
                self.commands.pop(cmd)

    def update_commands_telegram(self) -> None:
        """Update commands to Telegram, so that completion works for users."""
        telegram_commands: list[BotCommand] = []
        for cmd, desc in self.commands.items():
            telegram_commands.append(BotCommand(cmd, desc))

        _ = self.app.set_bot_commands(telegram_commands)
