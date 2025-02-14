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

import logging
from hashlib import md5
from itertools import batched
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, cast
from zipfile import ZipFile, is_zipfile

from anyio import Path, open_file
from jsondb.database import JsonDB
from pyrogram.client import Client
from pyrogram.filters import command
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from elysian_chem_bot import DB_PERSIST_PATH, db_instance
from elysian_chem_bot.database_types import File, Sections

log: logging.Logger = logging.getLogger(__name__)
cache_db: JsonDB = JsonDB(Path(Path(DB_PERSIST_PATH).parent).joinpath("extracted_files_cache.json").as_posix())


class MaterialCallbackData:
    def __init__(self, callback_string: str) -> None:
        """Callback data for the button of the material.

        Args:
            callback_string (str): "MUST be sections delimited by /:file name"
        """
        self.sections: list[str] = callback_string.split(":")[0].split("/")
        self.file_name_or_section: str = callback_string.split(":")[1]

        if self.sections[0] == "":
            self.sections.pop(0)

    def __str__(self) -> str:
        """Returns a string representation of the callback data of a material."""
        return f"{'/'.join(self.sections)}:{self.file_name_or_section}"


async def generate_inline_keyboard_markup(sections: Sections, columns: int = 3) -> InlineKeyboardMarkup:
    db_instance.raw_db = cast(dict[str, dict[str, Any]], db_instance.raw_db)

    # Get to the requested section first
    cur_sec = db_instance.raw_db
    for sec in sections:
        cur_sec = cur_sec[sec]

    # Now we generate the buttons
    # note: callback data will be "sections delimited with /:filename"
    rows: list[list[InlineKeyboardButton]] = []
    joined_sections = "/".join(sections)
    for batch in batched(cur_sec, columns):
        keyboardified_batch: list[InlineKeyboardButton] = [
            InlineKeyboardButton(x, callback_data=f"{joined_sections}:{x}") for x in batch
        ]
        rows.append(keyboardified_batch)

    return InlineKeyboardMarkup(rows)


@Client.on_message(command("bahanbeta"))
async def material_beta(client: Client, message: Message) -> None:
    inline_keyboard: InlineKeyboardMarkup = await generate_inline_keyboard_markup([])
    await message.reply_text("Please use the button below\n**Current section is:** __/__", reply_markup=inline_keyboard)


@Client.on_callback_query(group=2)
async def material_cb(client: Client, cb_query: CallbackQuery) -> None:
    material_callback: MaterialCallbackData = MaterialCallbackData(cast(str, cb_query.data))

    log.info("sections=%s", material_callback.sections)
    log.info("fileid=%s", material_callback.file_name_or_section)

    sections_plus_file_name: list[str] = material_callback.sections.copy()
    sections_plus_file_name.append(material_callback.file_name_or_section)

    if not db_instance.is_sections_exist(sections_plus_file_name).status:
        # then it is a file, upload the file and return early
        file: File = db_instance.get_file(material_callback.sections, material_callback.file_name_or_section)
        chat_id = cb_query.message.chat.id
        user_name: str = cb_query.from_user.first_name
        user_id: int = cb_query.from_user.id
        suffix: str = ""
        if material_callback.file_name_or_section.endswith(".zip"):
            suffix = "**reply to this file with** /unzip **to unpack this archive**"

        await client.send_document(chat_id, file.file_id, caption=f"[{user_name}](tg://user?id={user_id}) {suffix}")
        return

    inline_keyboard: InlineKeyboardMarkup = await generate_inline_keyboard_markup(sections_plus_file_name)
    await cb_query.message.edit(
        f"Please use the button below\n**Current section is:** __{'/'.join(sections_plus_file_name)}__",
        reply_markup=inline_keyboard,
    )


@Client.on_message(command("unzip"))
async def unzip(client: Client, message: Message) -> None:
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("Please reply to a file!")
        return

    file_id: str = message.reply_to_message.document.file_id
    msg: Message = await message.reply_text("__Processing file...__")

    with NamedTemporaryFile() as tf:
        log.info("created temporary file '%s'", tf.name)

        log.info("downloading document with file_id '%s'", file_id)
        await msg.edit_text(f"**downloading document with file_id** `'{file_id}'`")
        await client.download_media(file_id, tf.name)

        if not is_zipfile(tf.name):
            await msg.edit_text("That file is not a zip file!")
            return

        with TemporaryDirectory() as td:
            zip_file = ZipFile(tf.name)
            zip_file.extractall(td)

    async for file in Path(td).rglob("*"):
        if not file.is_file:
            return

        await msg.edit_text(f"Uploading file {file.as_posix()}")

        async with await open_file(file.as_posix(), "rb") as extracted_file:
            content: bytes = await extracted_file.read()
            md5_sum: str = md5(content).hexdigest()  # noqa: S324
            if cached_file_id := cache_db.data.get(md5_sum):
                log.info("file '%s' found in cache, re-using file_id", file.as_posix())
                await message.reply_document(cached_file_id)
            else:
                log.info("file '%s' NOT found in cache, uploading instead", file.as_posix())
                doc = await message.reply_document(file.as_posix(), file_name=file.name)

                log.info("storing file '%s' in cache", file.as_posix())
                cache_db.data.update({md5_sum: doc.document.file_id})
