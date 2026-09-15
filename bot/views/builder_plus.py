from __future__ import annotations

import copy
import io
import json

import discord
from discord import ui

from bot.builder.catalog import COMPONENTS, component_def
from bot.builder.renderer import RenderedComponentsView, build_container
from bot.builder.state import BuilderState, ComponentSpec
from bot.storage import TemplateStore

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class TextModal(ui.Modal):
    def __init__(self, title: str, label: str, value: str, callback):
        super().__init__(title=title[:45])
        self.value_input = ui.TextInput(
            label=label[:45],
            default=value[:4000],
            max_length=4000,
            style=discord.TextStyle.paragraph,
            required=True,
        )
        self.add_item(self.value_input)
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, str(self.value_input.value))


class JsonModal(ui.Modal):
    def __init__(self, callback):
        super().__init__(title="Import Components V2 JSON")
        self.payload = ui.TextInput(
            label="JSON",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000,
        )
        self.add_item(self.payload)
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, str(self.payload.value))


class MediaUploadModal(ui.Modal):
    """Upload up to 10 media files directly from Discord, capped at 20 MiB each."""

    def __init__(self, owner: "BuilderPlusView", index: int):
        super().__init__(title="Upload Media")
        self.owner = owner
        self.index = index
        self.upload = ui.FileUpload(
            custom_id=f"hx_media_{owner.owner_id}_{index}",
            min_values=1,
            max_values=10,
            required=True,
        )
        self.description = ui.TextInput(
            label="Description (optional)",
            required=False,
            max_length=256,
            style=discord.TextStyle.short,
        )
        self.add_item(ui.Label(text="Image / Video / File", component=self.upload))
        self.add_item(ui.Label(text="Description", component=self.description))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        files = list(self.upload.values)
        if not files:
            await interaction.response.send_message("Choose at least one file.", ephemeral=True)
            return

        oversized = [f.filename for f in files if int(f.size or 0) > MAX_UPLOAD_BYTES]
        if oversized:
            names = ", ".join(f"`{name}`" for name in oversized[:5])
            await interaction.response.send_message(
                f"Each upload must be 20 MB or smaller. Too large: {names}",
                ephemeral=True,
            )
            return

        items = []
        description = str(self.description.value or "")[:256]
        for attachment in files[:10]:
            items.append(
                {
                    "url": attachment.url,
                    "filename": attachment.filename[:255],
                    "content_type": str(attachment.content_type or ""),
                    "size": int(attachment.size or 0),
                    "description": description,
                    "spoiler": bool(attachment.filename.startswith("SPOILER_")),
                }
            )

        self.owner.state.update(self.index, {"items": items})
        self.owner._build()
        await interaction.response.edit_message(view=self.owner)


class ComponentEditor(ui.Modal):
    def __init__(self, owner: "BuilderPlusView", index: int):
        spec = owner.state.components[index]
        super().__init__(title=f"Edit {spec.type.replace('_', ' ').title()}"[:45])
        self.owner = owner
        self.index = index
        self.spec = spec
        self.fields: list[tuple[str, ui.TextInput]] = []
        data = spec.data

        if spec.type == "text":
            self._field("content", "Text content", str(data.get("content", "")), True)
        elif spec.type == "button":
            for key, label, default in (
                ("label", "Label", "Button"),
                ("style", "Style: primary/secondary/success/danger/link", "primary"),
                ("custom_id", "Custom ID", "helzerx:button"),
                ("url", "URL for link style", ""),
                ("disabled", "Disabled: true/false", "false"),
            ):
                self._field(key, label, str(data.get(key, default)), False)
        elif spec.type == "select":
            options = "\n".join(
                f"{o.get('label', '')} | {o.get('value', '')} | {o.get('description', '')}"
                for o in data.get("options", [])
                if isinstance(o, dict)
            )
            self._field("placeholder", "Placeholder", str(data.get("placeholder", "Choose an option")), False)
            self._field("custom_id", "Custom ID", str(data.get("custom_id", "helzerx:select")), False)
            self._field("options", "Options: Label | Value | Description", options, True)
        elif spec.type == "media":
            self._field(
                "urls",
                "Media URLs (optional)",
                "\n".join(
                    str(item.get("url", "")) if isinstance(item, dict) else str(item)
                    for item in data.get("items", [])
                ),
                True,
            )
        elif spec.type == "thumbnail":
            self._field("url", "Image URL", str(data.get("url", "")), False)
            self._field("description", "Description", str(data.get("description", "")), False)
        elif spec.type == "separator":
            self._field("visible", "Visible: true/false", str(data.get("visible", True)), False)
            self._field("spacing", "Spacing: small/large", str(data.get("spacing", "small")), False)
        elif spec.type == "section":
            self._field("content", "Section text", str(data.get("content", "Section content")), True)
            self._field("accessory", "Accessory: button/thumbnail", str(data.get("accessory", "button")), False)
            self._field("label", "Button label", str(data.get("label", "Open")), False)
            self._field("style", "Button style", str(data.get("style", "primary")), False)
            self._field("url", "Accessory URL", str(data.get("url", "")), False)
        elif spec.type in {"user_select", "role_select", "mentionable_select", "channel_select"}:
            self._field("placeholder", "Placeholder", str(data.get("placeholder", "Select...")), False)
            self._field("custom_id", "Custom ID", str(data.get("custom_id", f"helzerx:{spec.type}")), False)
            self._field("min_values", "Minimum values", str(data.get("min_values", 1)), False)
            self._field("max_values", "Maximum values", str(data.get("max_values", 1)), False)
        elif spec.type == "file":
            self._field("url", "Attachment URL", str(data.get("url", "attachment://file.txt")), False)
            self._field("spoiler", "Spoiler: true/false", str(data.get("spoiler", False)), False)
        else:
            self._field("data", "Component data JSON", json.dumps(data, ensure_ascii=False), True)

    def _field(self, key: str, label: str, value: str, paragraph: bool) -> None:
        field = ui.TextInput(
            label=label[:45],
            default=value[:4000],
            required=False,
            style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short,
        )
        self.add_item(ui.Label(text=label[:45], component=field))
        self.fields.append((key, field))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            values = {key: str(field.value) for key, field in self.fields}
            data = self._parse(values)
            self.owner.state.update(self.index, data)
        except (ValueError, json.JSONDecodeError) as exc:
            await interaction.response.send_message(f"Invalid component: {exc}", ephemeral=True)
            return

        self.owner._build()
        await interaction.response.edit_message(view=self.owner)

    def _parse(self, values: dict[str, str]) -> dict:
        t = self.spec.type
        if t == "text":
            content = values["content"].strip()
            if not content:
                raise ValueError("Text content cannot be empty.")
            return {"content": content[:4000]}

        if t == "button":
            style = values["style"].lower().strip()
            if style not in {"primary", "secondary", "success", "danger", "link"}:
                raise ValueError("Invalid button style.")
            if style == "link" and not values["url"].strip():
                raise ValueError("Link buttons require a URL.")
            if style != "link" and values["url"].strip():
                url = ""
            else:
                url = values["url"][:1000]
            return {
                "label": values["label"][:80] or "Button",
                "style": style,
                "custom_id": values["custom_id"][:100] or "helzerx:button",
                "url": url,
                "disabled": values["disabled"].lower() in {"true", "1", "yes"},
            }

        if t == "select":
            options = []
            for line in values["options"].splitlines()[:25]:
                parts = [x.strip() for x in line.split("|", 2)]
                if len(parts) >= 2 and parts[0] and parts[1]:
                    options.append(
                        {
                            "label": parts[0][:100],
                            "value": parts[1][:100],
                            "description": parts[2][:100] if len(parts) == 3 else "",
                        }
                    )
            if not options:
                raise ValueError("Add at least one select option.")
            return {
                "placeholder": values["placeholder"][:150] or "Choose an option",
                "custom_id": values["custom_id"][:100] or "helzerx:select",
                "options": options,
            }

        if t == "media":
            urls = [x.strip() for x in values["urls"].splitlines() if x.strip()][:10]
            if not urls:
                raise ValueError("Use the media upload action to add files.")
            return {"items": [{"url": url, "description": "", "spoiler": False} for url in urls]}

        if t == "thumbnail":
            if not values["url"].strip():
                raise ValueError("Image URL is required.")
            return {"url": values["url"][:1000], "description": values["description"][:256]}

        if t == "separator":
            spacing = values["spacing"].lower().strip()
            if spacing not in {"small", "large"}:
                raise ValueError("Spacing must be small or large.")
            return {
                "visible": values["visible"].lower() not in {"false", "0", "no"},
                "spacing": spacing,
            }

        if t == "section":
            accessory = values["accessory"].lower().strip()
            if accessory not in {"button", "thumbnail"}:
                raise ValueError("Accessory must be button or thumbnail.")
            if accessory == "button" and values["style"].lower().strip() not in {"primary", "secondary", "success", "danger", "link"}:
                raise ValueError("Invalid button style.")
            return {
                "content": values["content"][:4000],
                "accessory": accessory,
                "label": values["label"][:80] or "Open",
                "style": values["style"].lower().strip() or "primary",
                "url": values["url"][:1000],
                "custom_id": "helzerx:section",
            }

        if t in {"user_select", "role_select", "mentionable_select", "channel_select"}:
            minimum = max(0, min(int(values["min_values"] or 1), 25))
            maximum = max(minimum, min(int(values["max_values"] or 1), 25))
            return {
                "placeholder": values["placeholder"][:150] or "Select...",
                "custom_id": values["custom_id"][:100] or f"helzerx:{t}",
                "min_values": minimum,
                "max_values": maximum,
            }

        if t == "file":
            return {
                "url": values["url"][:1000],
                "spoiler": values["spoiler"].lower() in {"true", "1", "yes"},
            }

        data = json.loads(values["data"])
        if not isinstance(data, dict):
            raise ValueError("Component data must be a JSON object.")
        return data


class ComponentPicker(ui.Select):
    def __init__(self, owner: "BuilderPlusView", action: str = "edit"):
        self.owner = owner
        self.action = action
        options = []
        for index, spec in enumerate(owner.state.components[:25]):
            content = str(spec.data.get("content", "")) if spec.type == "text" else ""
            detail = content.replace("\n", " ").strip()[:80] or spec.type.replace("_", " ").title()
            options.append(
                discord.SelectOption(
                    label=f"{index + 1}. {spec.type.replace('_', ' ').title()}"[:100],
                    value=str(index),
                    description=detail[:100],
                )
            )
        super().__init__(
            placeholder="Select a component...",
            options=options or [discord.SelectOption(label="No components", value="-1")],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        index = int(self.values[0])
        if index < 0:
            await interaction.response.send_message("There are no components yet.", ephemeral=True)
            return
        if self.action == "edit":
            if self.owner.state.components[index].type == "media":
                await interaction.response.send_modal(MediaUploadModal(self.owner, index))
            else:
                await interaction.response.send_modal(ComponentEditor(self.owner, index))
            return
        if self.action == "remove":
            self.owner.state.remove(index)
        elif self.action == "duplicate":
            if not self.owner.state.duplicate(index):
                await interaction.response.send_message("Component limit reached.", ephemeral=True)
                return
        elif self.action == "toggle":
            self.owner.state.toggle(index)
        self.owner._build()
        await interaction.response.edit_message(view=self.owner)


class BuilderPlusView(ui.LayoutView):
    """HelzerX Components V2 builder with a true message preview."""

    def __init__(self, owner_id: int, accent_color: int | None = None, store: TemplateStore | None = None):
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.state = BuilderState(owner_id=owner_id, accent_color=accent_color)
        self.store = store or TemplateStore()
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This builder belongs to another user.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        self.clear_items()

        preview_header = ui.Container()
        preview_header.add_item(ui.TextDisplay("### Live Preview"))
        self.add_item(preview_header)

        # This is the same container structure that gets sent to the target channel.
        self.add_item(build_container(self.state, interactive=False, show_name=True, accent=False))

        editor = ui.Container()
        editor.add_item(ui.TextDisplay("### Container Builder"))
        editor.add_item(
            ui.TextDisplay(
                f"{self.state.component_count} / {self.state.MAX_COMPONENTS} components · {self.state.name}"
            )
        )

        add = ui.Select(
            placeholder="Add a component...",
            options=[
                discord.SelectOption(label=d.label, value=d.key, description=d.description[:100])
                for d in COMPONENTS
            ],
        )

        async def add_callback(interaction: discord.Interaction) -> None:
            definition = component_def(add.values[0])
            spec = ComponentSpec(definition.key, copy.deepcopy(definition.default))
            if not self.state.add(spec):
                await interaction.response.send_message("Component limit reached.", ephemeral=True)
                return
            if definition.key == "media":
                await interaction.response.send_modal(MediaUploadModal(self, self.state.component_count - 1))
            else:
                # Text Display and every other editable component open immediately after creation.
                await interaction.response.send_modal(ComponentEditor(self, self.state.component_count - 1))

        add.callback = add_callback
        editor.add_item(ui.ActionRow(add))

        if self.state.components:
            picker = ComponentPicker(self, "edit")
            editor.add_item(ui.ActionRow(picker))
            editor.add_item(
                ui.TextDisplay(
                    "Select a component to edit it. Selecting a Text Display opens its text editor immediately."
                )
            )
        else:
            editor.add_item(ui.TextDisplay("Add a component. Its editor opens immediately."))

        self.add_item(editor)

        controls = ui.Container()
        controls.add_item(ui.TextDisplay("### Controls"))
        row_one = ui.ActionRow(
            ui.Button(label="Duplicate", style=discord.ButtonStyle.secondary, custom_id="hx:duplicate"),
            ui.Button(label="Remove", style=discord.ButtonStyle.danger, custom_id="hx:remove"),
            ui.Button(label="Reorder", style=discord.ButtonStyle.secondary, custom_id="hx:reorder"),
            ui.Button(label="Toggle", style=discord.ButtonStyle.secondary, custom_id="hx:toggle"),
        )
        for child in row_one.children:
            child.callback = self._control
        controls.add_item(row_one)

        row_two = ui.ActionRow(
            ui.Button(label="Send", style=discord.ButtonStyle.success, custom_id="hx:send"),
            ui.Button(label="More Tools", style=discord.ButtonStyle.secondary, custom_id="hx:more"),
        )
        for child in row_two.children:
            child.callback = self._control
        controls.add_item(row_two)
        self.add_item(controls)

    async def _component_action(self, interaction: discord.Interaction, action: str) -> None:
        if not self.state.components:
            await interaction.response.send_message("There are no components yet.", ephemeral=True)
            return
        picker = ComponentPicker(self, action)
        view = ui.LayoutView(timeout=120)
        box = ui.Container()
        box.add_item(ui.TextDisplay(f"### {action.title()} Component"))
        box.add_item(ui.ActionRow(picker))
        view.add_item(box)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def _control(self, interaction: discord.Interaction) -> None:
        action = str(interaction.data.get("custom_id", "")).split(":")[-1]
        if action in {"duplicate", "remove", "toggle"}:
            await self._component_action(interaction, action)
            return

        if action == "reorder":
            await self._reorder(interaction)
            return

        if action == "send":
            await self._send_picker(interaction)
            return

        if action == "more":
            await interaction.response.send_message(view=MoreView(self), ephemeral=True)

    async def _reorder(self, interaction: discord.Interaction) -> None:
        if not self.state.components:
            await interaction.response.send_message("There are no components yet.", ephemeral=True)
            return
        select = discord.ui.Select(
            placeholder="Select component...",
            options=[
                discord.SelectOption(
                    label=f"{i + 1}. {x.type.replace('_', ' ').title()}",
                    value=str(i),
                )
                for i, x in enumerate(self.state.components[:25])
            ],
        )
        mode = discord.ui.Select(
            placeholder="Choose movement...",
            options=[
                discord.SelectOption(label="Move up", value="up"),
                discord.SelectOption(label="Move down", value="down"),
                discord.SelectOption(label="Move to top", value="top"),
                discord.SelectOption(label="Move to bottom", value="bottom"),
            ],
        )

        async def reorder_callback(i: discord.Interaction) -> None:
            if not select.values or not mode.values:
                await i.response.send_message("Choose a component and a movement.", ephemeral=True)
                return
            index = int(select.values[0])
            direction = mode.values[0]
            target = {
                "up": index - 1,
                "down": index + 1,
                "top": 0,
                "bottom": len(self.state.components) - 1,
            }[direction]
            if not self.state.move(index, target - index):
                await i.response.send_message("That move is not possible.", ephemeral=True)
                return
            self._build()
            await i.response.edit_message(view=self)

        select.callback = reorder_callback
        mode.callback = reorder_callback
        view = ui.LayoutView(timeout=120)
        box = ui.Container()
        box.add_item(ui.TextDisplay("### Reorder Components"))
        box.add_item(ui.ActionRow(select))
        box.add_item(ui.ActionRow(mode))
        view.add_item(box)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def _send_picker(self, interaction: discord.Interaction) -> None:
        if not self.state.components:
            await interaction.response.send_message("Add at least one component before sending.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("Sending requires a server channel.", ephemeral=True)
            return

        picker = ui.ChannelSelect(
            custom_id="hx_send_channel",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            placeholder="Select a channel to send to...",
            min_values=1,
            max_values=1,
        )

        async def channel_callback(i: discord.Interaction) -> None:
            selected = picker.values[0]
            target = i.client.get_channel(selected.id)
            if target is None:
                try:
                    target = await i.client.fetch_channel(selected.id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    await i.response.send_message("I cannot access that channel.", ephemeral=True)
                    return

            if not hasattr(target, "send"):
                await i.response.send_message("That channel cannot receive messages.", ephemeral=True)
                return

            try:
                await target.send(view=RenderedComponentsView(self.state, interactive=True))
            except discord.Forbidden:
                await i.response.send_message(
                    "I do not have permission to send messages in that channel.",
                    ephemeral=True,
                )
                return
            except discord.HTTPException as exc:
                await i.response.send_message(
                    f"Discord rejected the Components V2 message: `{exc}`",
                    ephemeral=True,
                )
                return

            await i.response.edit_message(view=SendDoneView(target))

        picker.callback = channel_callback
        view = ui.LayoutView(timeout=120)
        box = ui.Container()
        box.add_item(ui.TextDisplay("### Send Container\nChoose the destination channel."))
        box.add_item(ui.ActionRow(picker))
        view.add_item(box)
        await interaction.response.send_message(view=view, ephemeral=True)


class SendDoneView(ui.LayoutView):
    def __init__(self, channel):
        super().__init__(timeout=60)
        box = ui.Container()
        box.add_item(ui.TextDisplay(f"Sent successfully to {channel.mention}."))
        self.add_item(box)


class MoreView(ui.LayoutView):
    def __init__(self, builder: BuilderPlusView):
        super().__init__(timeout=180)
        self.builder = builder
        box = ui.Container()
        box.add_item(ui.TextDisplay("### Builder Tools\nManage the container, JSON and templates."))
        select = ui.Select(
            placeholder="Choose a tool...",
            options=[
                discord.SelectOption(label="Container Name", value="name"),
                discord.SelectOption(label="Accent Color", value="color"),
                discord.SelectOption(label="Export JSON", value="export"),
                discord.SelectOption(label="Import JSON", value="import"),
                discord.SelectOption(label="Save Template", value="save"),
                discord.SelectOption(label="Load Template", value="load"),
                discord.SelectOption(label="Delete Template", value="delete"),
                discord.SelectOption(label="Reset", value="reset"),
            ],
        )
        select.callback = self._callback
        box.add_item(ui.ActionRow(select))
        self.add_item(box)

    async def _callback(self, interaction: discord.Interaction) -> None:
        action = interaction.data["values"][0]
        b = self.builder

        if action == "name":
            async def save_name(i: discord.Interaction, value: str) -> None:
                b.state.name = value.strip()[:100] or "Untitled Container"
                b._build()
                await i.response.edit_message(view=b)
            await interaction.response.send_modal(TextModal("Container Name", "Name", b.state.name, save_name))
            return

        if action == "color":
            async def save_color(i: discord.Interaction, value: str) -> None:
                raw = value.strip().lstrip("#")
                if raw.lower() in {"none", "off", "remove"}:
                    b.state.accent_color = None
                else:
                    try:
                        color = int(raw, 16)
                    except ValueError:
                        await i.response.send_message("Enter a hex color such as `5865F2`, or `none`.", ephemeral=True)
                        return
                    if not 0 <= color <= 0xFFFFFF:
                        await i.response.send_message("Color must be between 000000 and FFFFFF.", ephemeral=True)
                        return
                    b.state.accent_color = color
                b._build()
                await i.response.edit_message(view=b)
            await interaction.response.send_modal(
                TextModal(
                    "Accent Color",
                    "Hex color",
                    f"#{b.state.accent_color:06X}" if b.state.accent_color is not None else "none",
                    save_color,
                )
            )
            return

        if action == "export":
            payload = b.state.to_json().encode("utf-8")
            await interaction.response.send_message(
                file=discord.File(io.BytesIO(payload), filename="helzerx-container.json"),
                ephemeral=True,
            )
            return

        if action == "import":
            async def import_json(i: discord.Interaction, raw: str) -> None:
                try:
                    b.state = BuilderState.from_json(b.owner_id, raw)
                except ValueError as exc:
                    await i.response.send_message(f"Invalid JSON: {exc}", ephemeral=True)
                    return
                b._build()
                await i.response.edit_message(view=b)
            await interaction.response.send_modal(JsonModal(import_json))
            return

        if action == "save":
            async def save_template(i: discord.Interaction, name: str) -> None:
                clean = name.strip()[:80]
                if not clean:
                    await i.response.send_message("Template name cannot be empty.", ephemeral=True)
                    return
                b.store.save(b.owner_id, clean, b.state)
                await i.response.send_message(f"Template `{clean}` saved.", ephemeral=True)
            await interaction.response.send_modal(TextModal("Save Template", "Template name", b.state.name, save_template))
            return

        if action == "load":
            names = b.store.names(b.owner_id)
            if not names:
                await interaction.response.send_message("You have no saved templates.", ephemeral=True)
                return
            picker = ui.Select(
                placeholder="Select a template...",
                options=[discord.SelectOption(label=name[:100], value=name) for name in names[:25]],
            )

            async def load_callback(i: discord.Interaction) -> None:
                state = b.store.load(b.owner_id, picker.values[0])
                if state is None:
                    await i.response.send_message("Template not found.", ephemeral=True)
                    return
                b.state = state
                b._build()
                await i.response.edit_message(view=b)

            picker.callback = load_callback
            view = ui.LayoutView(timeout=120)
            box = ui.Container()
            box.add_item(ui.TextDisplay("### Load Template"))
            box.add_item(ui.ActionRow(picker))
            view.add_item(box)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        if action == "delete":
            names = b.store.names(b.owner_id)
            if not names:
                await interaction.response.send_message("You have no saved templates.", ephemeral=True)
                return
            picker = ui.Select(
                placeholder="Select a template to delete...",
                options=[discord.SelectOption(label=name[:100], value=name) for name in names[:25]],
            )

            async def delete_callback(i: discord.Interaction) -> None:
                name = picker.values[0]
                b.store.delete(b.owner_id, name)
                await i.response.send_message(f"Template `{name}` deleted.", ephemeral=True)

            picker.callback = delete_callback
            view = ui.LayoutView(timeout=120)
            box = ui.Container()
            box.add_item(ui.TextDisplay("### Delete Template"))
            box.add_item(ui.ActionRow(picker))
            view.add_item(box)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        if action == "reset":
            b.state.clear()
            b._build()
            await interaction.response.edit_message(view=b)
