from __future__ import annotations

import copy
import io
import json

import discord
from discord import ui

from bot.builder.catalog import COMPONENTS, component_def
from bot.builder.renderer import RenderedComponentsView
from bot.builder.state import BuilderState, ComponentSpec
from bot.emoji import emoji
from bot.storage import TemplateStore


def icon(kind: str) -> str:
    return emoji(component_def(kind).icon)


class TextModal(ui.Modal):
    def __init__(self, title: str, label: str, value: str, callback):
        super().__init__(title=title[:45])
        self.value_input = ui.TextInput(label=label[:45], default=value[:4000], style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.value_input)
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, str(self.value_input.value))


class JsonModal(ui.Modal):
    def __init__(self, callback):
        super().__init__(title="Import Components V2 JSON")
        self.payload = ui.TextInput(label="JSON", style=discord.TextStyle.paragraph, required=True, max_length=4000)
        self.add_item(self.payload)
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, str(self.payload.value))


class ComponentEditor(ui.Modal):
    def __init__(self, owner: "BuilderPlusView", index: int):
        spec = owner.state.components[index]
        super().__init__(title=f"Edit {spec.type.replace('_', ' ').title()}")
        self.owner = owner
        self.index = index
        self.spec = spec
        self.fields: list[tuple[str, ui.TextInput]] = []
        data = spec.data
        if spec.type == "text":
            self._field("content", "Text content", str(data.get("content", "")), True)
        elif spec.type == "button":
            self._field("label", "Label", str(data.get("label", "Button")), False)
            self._field("style", "Style: primary/secondary/success/danger/link", str(data.get("style", "primary")), False)
            self._field("custom_id", "Custom ID", str(data.get("custom_id", "helzerx:button")), False)
            self._field("url", "URL for link style", str(data.get("url", "")), False)
            self._field("disabled", "Disabled: true/false", str(data.get("disabled", False)), False)
        elif spec.type == "select":
            opts = "\n".join(f"{o.get('label','')} | {o.get('value','')} | {o.get('description','')}" for o in data.get("options", []))
            self._field("placeholder", "Placeholder", str(data.get("placeholder", "Choose an option")), False)
            self._field("custom_id", "Custom ID", str(data.get("custom_id", "helzerx:select")), False)
            self._field("options", "Options: Label | Value | Description", opts, True)
        elif spec.type == "media":
            self._field("items", "Media URLs, one per line (max 10)", "\n".join(data.get("items", [])), True)
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
            self._field("custom_id", "Button custom ID", str(data.get("custom_id", "helzerx:section")), False)
        elif spec.type == "file":
            self._field("url", "Attachment URL", str(data.get("url", "attachment://file.txt")), False)
        else:
            self._field("data", "Component data JSON", json.dumps(data, ensure_ascii=False), True)

    def _field(self, key: str, label: str, value: str, paragraph: bool) -> None:
        field = ui.TextInput(label=label[:45], default=value[:4000], required=False, style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short)
        self.add_item(field)
        self.fields.append((key, field))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        values = {key: str(field.value) for key, field in self.fields}
        try:
            data = self._parse(values)
            self.owner.state.update(self.index, data)
        except (ValueError, json.JSONDecodeError) as exc:
            await interaction.response.send_message(f"{emoji('ERROR')} {exc}", ephemeral=True)
            return
        self.owner._build()
        await interaction.response.edit_message(view=self.owner)

    def _parse(self, v: dict[str, str]) -> dict:
        t = self.spec.type
        if t == "text":
            return {"content": v["content"][:4000]}
        if t == "button":
            style = v["style"].lower().strip()
            if style not in {"primary", "secondary", "success", "danger", "link"}:
                raise ValueError("Invalid button style.")
            if style == "link" and not v["url"].strip():
                raise ValueError("Link buttons require a URL.")
            return {"label": v["label"][:80], "style": style, "custom_id": v["custom_id"][:100], "url": v["url"][:1000], "disabled": v["disabled"].lower() in {"true", "1", "yes"}}
        if t == "select":
            options = []
            for line in v["options"].splitlines()[:25]:
                p = [x.strip() for x in line.split("|", 2)]
                if len(p) >= 2 and p[0] and p[1]:
                    options.append({"label": p[0][:100], "value": p[1][:100], "description": p[2][:100] if len(p) == 3 else ""})
            if not options:
                raise ValueError("Add at least one select option.")
            return {"placeholder": v["placeholder"][:150], "custom_id": v["custom_id"][:100], "options": options}
        if t == "media":
            items = [x.strip() for x in v["items"].splitlines() if x.strip()][:10]
            if not items:
                raise ValueError("Add at least one media URL.")
            return {"items": items}
        if t == "thumbnail":
            if not v["url"].strip():
                raise ValueError("Image URL is required.")
            return {"url": v["url"][:1000], "description": v["description"][:256]}
        if t == "separator":
            spacing = v["spacing"].lower().strip()
            if spacing not in {"small", "large"}:
                raise ValueError("Spacing must be small or large.")
            return {"visible": v["visible"].lower() not in {"false", "0", "no"}, "spacing": spacing}
        if t == "section":
            accessory = v["accessory"].lower().strip()
            if accessory not in {"button", "thumbnail"}:
                raise ValueError("Accessory must be button or thumbnail.")
            return {"content": v["content"][:4000], "accessory": accessory, "label": v["label"][:80], "style": v["style"].lower(), "url": v["url"][:1000], "custom_id": v["custom_id"][:100]}
        if t == "file":
            return {"url": v["url"][:1000]}
        data = json.loads(v["data"])
        if not isinstance(data, dict):
            raise ValueError("Component data must be a JSON object.")
        return data


class IndexSelect(ui.Select):
    def __init__(self, owner: "BuilderPlusView", action: str, placeholder: str, offset: int = 0):
        self.owner = owner
        self.action_name = action
        self.offset = offset
        items = owner.state.components[offset:offset + 25]
        options = [discord.SelectOption(label=f"#{offset + i + 1} {x.type.replace('_', ' ').title()}", value=str(offset + i), description="Enabled" if x.enabled else "Disabled") for i, x in enumerate(items)]
        super().__init__(placeholder=placeholder, options=options or [discord.SelectOption(label="No components", value="-1")])

    async def callback(self, interaction: discord.Interaction) -> None:
        index = int(self.values[0])
        if index < 0:
            await interaction.response.send_message("There are no components yet.", ephemeral=True)
            return
        if self.action_name == "edit":
            await interaction.response.send_modal(ComponentEditor(self.owner, index))
            return
        if self.action_name == "remove":
            self.owner.state.remove(index)
        elif self.action_name == "duplicate":
            if not self.owner.state.duplicate(index):
                await interaction.response.send_message(f"{emoji('ERROR')} Component limit reached (40).", ephemeral=True)
                return
        elif self.action_name == "toggle":
            self.owner.state.toggle(index)
        self.owner._build()
        await interaction.response.edit_message(view=self.owner)


class BuilderPlusView(ui.LayoutView):
    def __init__(self, owner_id: int, accent_color: int = 0x5865F2, store: TemplateStore | None = None):
        super().__init__(timeout=900)
        self.owner_id = owner_id
        self.state = BuilderState(owner_id=owner_id, accent_color=accent_color)
        self.store = store or TemplateStore()
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(f"{emoji('ERROR')} This builder belongs to another user.", ephemeral=True)
            return False
        return True

    def _component_summary(self) -> str:
        if not self.state.components:
            return f"*{emoji('WARNING')} Empty container — use **Add Component** to begin.*"
        return "\n".join(f"`{i:02}` {icon(item.type)} **{item.type.replace('_', ' ').title()}**" + ("" if item.enabled else " ~~disabled~~") for i, item in enumerate(self.state.components, 1))[:3900]

    def _build(self) -> None:
        self.clear_items()
        accent = self.state.accent_color
        container = ui.Container(accent_color=discord.Colour(accent) if accent is not None else None)
        container.add_item(ui.TextDisplay(f"# {emoji('BUILDER')} HelzerX Container Builder **V2**\n-# Build Discord Components V2 layouts directly inside Discord."))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"### {emoji('PREVIEW')} Live Preview\n**{self.state.name}** · Components **{self.state.component_count}/{self.state.MAX_COMPONENTS}** · Accent `{('#%06X' % accent) if accent is not None else 'None'}`"))
        container.add_item(ui.TextDisplay(self._component_summary()))

        add = ui.Select(placeholder=f"{emoji('ADD')} Add a component...", options=[discord.SelectOption(label=d.label, value=d.key, description=d.description, emoji=icon(d.key)) for d in COMPONENTS])
        async def add_callback(interaction: discord.Interaction) -> None:
            definition = component_def(add.values[0])
            if not self.state.add(ComponentSpec(definition.key, copy.deepcopy(definition.default))):
                await interaction.response.send_message(f"{emoji('ERROR')} Component limit reached (40).", ephemeral=True)
                return
            self._build()
            await interaction.response.edit_message(view=self)
        add.callback = add_callback
        container.add_item(ui.ActionRow(add))

        controls = ui.ActionRow(
            ui.Button(label="Edit", emoji=emoji("EDIT"), style=discord.ButtonStyle.secondary, custom_id="hx:edit"),
            ui.Button(label="Duplicate", emoji=emoji("DUPLICATE"), style=discord.ButtonStyle.secondary, custom_id="hx:duplicate"),
            ui.Button(label="Remove", emoji=emoji("REMOVE"), style=discord.ButtonStyle.danger, custom_id="hx:remove"),
            ui.Button(label="Reorder", emoji=emoji("REORDER"), style=discord.ButtonStyle.secondary, custom_id="hx:reorder"),
            ui.Button(label="Send", emoji=emoji("SEND"), style=discord.ButtonStyle.success, custom_id="hx:send"),
        )
        for child in controls.children:
            child.callback = self._control
        container.add_item(controls)
        more = ui.ActionRow(ui.Button(label="More Tools", emoji=emoji("SETTINGS"), style=discord.ButtonStyle.secondary, custom_id="hx:more"))
        more.children[0].callback = self._control
        container.add_item(more)
        self.add_item(container)

    async def _component_picker(self, interaction: discord.Interaction, action: str) -> None:
        if not self.state.components:
            await interaction.response.send_message(f"{emoji('WARNING')} No components yet.", ephemeral=True)
            return
        picker = IndexSelect(self, action, f"Choose component to {action}")
        view = ui.LayoutView(timeout=120)
        view.add_item(ui.Container(ui.TextDisplay(f"### {action.title()} Component"), ui.ActionRow(picker)))
        await interaction.response.send_message(view=view, ephemeral=True)

    async def _control(self, interaction: discord.Interaction) -> None:
        action = str(interaction.data.get("custom_id", "")).split(":")[-1]
        if action in {"edit", "duplicate", "remove", "toggle"}:
            await self._component_picker(interaction, action)
            return
        if action == "reorder":
            if not self.state.components:
                await interaction.response.send_message(f"{emoji('WARNING')} No components yet.", ephemeral=True)
                return
            select = ui.Select(placeholder="Choose component", options=[discord.SelectOption(label=f"#{i+1} {x.type.replace('_',' ').title()}", value=str(i)) for i, x in enumerate(self.state.components[:25])])
            mode = ui.Select(placeholder="Choose move", options=[discord.SelectOption(label="Move up", value="up"), discord.SelectOption(label="Move down", value="down"), discord.SelectOption(label="Move to top", value="top"), discord.SelectOption(label="Move to bottom", value="bottom")])
            async def go(i: discord.Interaction) -> None:
                idx, direction = int(select.values[0]), mode.values[0]
                if direction == "up": target = idx - 1
                elif direction == "down": target = idx + 1
                elif direction == "top": target = -idx
                else: target = len(self.state.components) - 1 - idx
                if not self.state.move(idx, target):
                    await i.response.send_message(f"{emoji('WARNING')} That move is not possible.", ephemeral=True)
                    return
                self._build()
                await i.response.edit_message(view=self)
            select.callback = go
            mode.callback = go
            view = ui.LayoutView(timeout=120)
            view.add_item(ui.Container(ui.TextDisplay("### Reorder Components"), ui.ActionRow(select), ui.ActionRow(mode)))
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        if action == "send":
            if not self.state.components:
                await interaction.response.send_message(f"{emoji('WARNING')} Add at least one component before sending.", ephemeral=True)
                return
            await interaction.response.send_message(view=RenderedComponentsView(self.state))
            return
        if action == "more":
            await self.open_more(interaction)

    async def open_more(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(view=MoreView(self), ephemeral=True)


class MoreView(ui.LayoutView):
    def __init__(self, builder: BuilderPlusView):
        super().__init__(timeout=180)
        self.builder = builder
        box = ui.Container(ui.TextDisplay("### Builder Tools\nManage the container, JSON and templates."))
        self.select = ui.Select(placeholder="Choose an action...", options=[
            discord.SelectOption(label="Container Name", value="name"),
            discord.SelectOption(label="Accent Color", value="color"),
            discord.SelectOption(label="Export JSON", value="export"),
            discord.SelectOption(label="Import JSON", value="import"),
            discord.SelectOption(label="Save Template", value="save"),
            discord.SelectOption(label="Load Template", value="load"),
            discord.SelectOption(label="Delete Template", value="delete"),
            discord.SelectOption(label="Reset", value="reset"),
        ])
        self.select.callback = self.callback
        box.add_item(ui.ActionRow(self.select))
        self.add_item(box)

    async def callback(self, interaction: discord.Interaction) -> None:
        action = self.select.values[0]
        if action == "name":
            async def done(i, value):
                self.builder.state.name = value[:100]
                self.builder._build()
                await i.response.edit_message(view=self.builder)
            await interaction.response.send_modal(TextModal("Container Name", "Name", self.builder.state.name, done))
        elif action == "color":
            async def done(i, value):
                try:
                    color = int(value.strip().lstrip("#"), 16)
                    if not 0 <= color <= 0xFFFFFF: raise ValueError
                    self.builder.state.accent_color = color
                except ValueError:
                    await i.response.send_message(f"{emoji('ERROR')} Use a valid hex color such as `5865F2`.", ephemeral=True)
                    return
                self.builder._build()
                await i.response.edit_message(view=self.builder)
            await interaction.response.send_modal(TextModal("Accent Color", "Hex color", f"{self.builder.state.accent_color:06X}" if self.builder.state.accent_color is not None else "5865F2", done))
        elif action == "export":
            await interaction.response.send_message(file=discord.File(io.BytesIO(self.builder.state.to_json().encode()), filename="helzerx-components-v2.json"), ephemeral=True)
        elif action == "import":
            await interaction.response.send_modal(JsonModal(self._import))
        elif action == "save":
            async def done(i, value):
                name = value.strip()[:50]
                if not name: await i.response.send_message(f"{emoji('ERROR')} Template name cannot be empty.", ephemeral=True); return
                self.builder.store.save(self.builder.owner_id, name, self.builder.state)
                await i.response.send_message(f"{emoji('SUCCESS')} Template saved: **{name}**.", ephemeral=True)
            await interaction.response.send_modal(TextModal("Save Template", "Template name", self.builder.state.name, done))
        elif action in {"load", "delete"}:
            names = self.builder.store.names(self.builder.owner_id)[:25]
            if not names:
                await interaction.response.send_message(f"{emoji('WARNING')} No saved templates.", ephemeral=True); return
            select = ui.Select(placeholder="Choose a template...", options=[discord.SelectOption(label=n, value=n) for n in names])
            async def choose(i: discord.Interaction) -> None:
                name = select.values[0]
                if action == "delete":
                    self.builder.store.delete(self.builder.owner_id, name)
                    await i.response.send_message(f"{emoji('SUCCESS')} Deleted **{name}**.", ephemeral=True)
                    return
                payload = self.builder.store.load(self.builder.owner_id, name)
                if payload:
                    self.builder.state = BuilderState.from_dict(self.builder.owner_id, payload)
                    self.builder._build()
                    await i.response.edit_message(view=self.builder)
                else:
                    await i.response.send_message(f"{emoji('ERROR')} Template no longer exists.", ephemeral=True)
            select.callback = choose
            v = ui.LayoutView(timeout=120)
            v.add_item(ui.Container(ui.TextDisplay(f"### {'Load' if action == 'load' else 'Delete'} Template"), ui.ActionRow(select)))
            await interaction.response.send_message(view=v, ephemeral=True)
        elif action == "reset":
            self.builder.state.clear()
            self.builder._build()
            await interaction.response.edit_message(view=self.builder)

    async def _import(self, interaction: discord.Interaction, raw: str) -> None:
        try:
            self.builder.state = BuilderState.from_json(self.builder.owner_id, raw)
        except ValueError as exc:
            await interaction.response.send_message(f"{emoji('ERROR')} {exc}", ephemeral=True)
            return
        self.builder._build()
        await interaction.response.edit_message(view=self.builder)
