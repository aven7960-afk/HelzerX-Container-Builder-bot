from __future__ import annotations

import io
import json

import discord
from discord import ui

from bot.builder.catalog import COMPONENTS, component_def
from bot.builder.state import BuilderState, ComponentSpec
from bot.emoji import emoji
from bot.storage import TemplateStore


STYLE_MAP = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "link": discord.ButtonStyle.link,
}


def icon(kind: str) -> str:
    return emoji(component_def(kind).icon)


class TextModal(ui.Modal):
    def __init__(self, title: str, label: str, value: str, callback):
        super().__init__(title=title)
        self.value_input = ui.TextInput(label=label, default=value[:4000], style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.value_input)
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, str(self.value_input.value))


class JsonModal(ui.Modal):
    def __init__(self, callback):
        super().__init__(title="Import Components V2 JSON")
        self.payload = ui.TextInput(label="JSON", placeholder='{"version":2,"components":[]}', style=discord.TextStyle.paragraph, required=True, max_length=4000)
        self.add_item(self.payload)
        self._callback = callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, str(self.payload.value))


class ComponentEditor(ui.Modal):
    def __init__(self, owner: "BuilderPlusView", index: int):
        super().__init__(title=f"Edit component #{index + 1}")
        self.owner = owner
        self.index = index
        spec = owner.state.components[index]
        self.content = ui.TextInput(label="Component data JSON", style=discord.TextStyle.paragraph, required=True, max_length=4000,
                                    default=json.dumps(spec.data, indent=2, ensure_ascii=False)[:4000])
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            data = json.loads(str(self.content.value))
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(f"{emoji('ERROR')} Invalid JSON object.", ephemeral=True)
            return
        self.owner.state.components[self.index].data = data
        await interaction.response.edit_message(view=self.owner)


class IndexSelect(ui.Select):
    def __init__(self, owner: "BuilderPlusView", action: str, placeholder: str):
        self.owner = owner
        self.action_name = action
        options = []
        for i, item in enumerate(owner.state.components[:25]):
            options.append(discord.SelectOption(label=f"#{i + 1} {item.type.title()}", value=str(i), description=("Enabled" if item.enabled else "Disabled")))
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
            self.owner.state.duplicate(index)
        elif self.action_name == "toggle":
            self.owner.state.toggle(index)
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
        lines = []
        for i, item in enumerate(self.state.components, 1):
            status = "" if item.enabled else " ~~disabled~~"
            lines.append(f"`{i:02}` {icon(item.type)} **{item.type.replace('_', ' ').title()}**{status}")
        return "\n".join(lines)

    def _build(self) -> None:
        self.clear_items()
        accent = self.state.accent_color
        container = ui.Container(accent_color=discord.Colour(accent) if accent is not None else None)
        container.add_item(ui.TextDisplay(f"# {emoji('BUILDER')} HelzerX Container Builder **V2**\n-# Build Discord Components V2 layouts directly inside Discord."))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"### {emoji('PREVIEW')} Live Preview\n**{self.state.name}** · Components **{self.state.component_count}/{self.state.MAX_COMPONENTS}** · Accent `{('#%06X' % accent) if accent is not None else 'None'}`"))
        container.add_item(ui.TextDisplay(self._component_summary()))

        add = ui.Select(placeholder=f"{emoji('ADD')} Add a component...", options=[
            discord.SelectOption(label=d.label, value=d.key, description=d.description, emoji=icon(d.key)) for d in COMPONENTS
        ])
        async def add_callback(interaction: discord.Interaction) -> None:
            kind = add.values[0]
            definition = component_def(kind)
            if not self.state.add(ComponentSpec(kind, json.loads(json.dumps(definition.default)))):
                await interaction.response.send_message(f"{emoji('ERROR')} Component limit reached (40).", ephemeral=True)
                return
            self._build()
            await interaction.response.edit_message(view=self)
        add.callback = add_callback
        container.add_item(ui.ActionRow(add))

        controls = ui.ActionRow(
            ui.Button(label="Edit", emoji=emoji("EDIT"), style=discord.ButtonStyle.secondary, custom_id="hx:edit"),
            ui.Button(label="Duplicate", emoji="📑", style=discord.ButtonStyle.secondary, custom_id="hx:duplicate"),
            ui.Button(label="Remove", emoji=emoji("REMOVE"), style=discord.ButtonStyle.danger, custom_id="hx:remove"),
            ui.Button(label="Reorder", emoji=emoji("REORDER"), style=discord.ButtonStyle.secondary, custom_id="hx:reorder"),
            ui.Button(label="More", emoji="☰", style=discord.ButtonStyle.secondary, custom_id="hx:more"),
        )
        for child in controls.children:
            child.callback = self._control
        container.add_item(controls)
        self.add_item(container)

    async def _control(self, interaction: discord.Interaction) -> None:
        action = str(interaction.data.get("custom_id", "")).split(":")[-1]
        if action in {"edit", "duplicate", "remove", "toggle"}:
            view = ui.LayoutView(timeout=120)
            box = ui.Container(ui.TextDisplay(f"### Select a component to {action}"), IndexSelect(self, action, f"Choose component to {action}"))
            view.add_item(box)
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        if action == "reorder":
            view = ui.LayoutView(timeout=120)
            select = IndexSelect(self, "move", "Choose a component to move")
            async def move_callback(i: discord.Interaction) -> None:
                index = int(select.values[0])
                self.state.move(index, 1)
                self._build()
                await i.response.edit_message(view=self)
            select.callback = move_callback
            view.add_item(ui.Container(ui.TextDisplay("### Reorder\nSelect an item; it moves down one position."), select))
            await interaction.response.send_message(view=view, ephemeral=True)
            return
        await interaction.response.send_message(f"{emoji('SETTINGS')} Use the **More** menu for color, JSON, templates and reset.", ephemeral=True)

    async def open_more(self, interaction: discord.Interaction) -> None:
        pass


class MoreView(ui.LayoutView):
    def __init__(self, builder: BuilderPlusView):
        super().__init__(timeout=120)
        self.builder = builder
        box = ui.Container(ui.TextDisplay("### Builder Tools\nChoose an advanced operation."))
        select = ui.Select(placeholder="Choose an action...", options=[
            discord.SelectOption(label="Container Name", value="name", emoji="🏷️"),
            discord.SelectOption(label="Accent Color", value="color", emoji=emoji("COLOR")),
            discord.SelectOption(label="Export JSON", value="export", emoji=emoji("JSON")),
            discord.SelectOption(label="Import JSON", value="import", emoji="📥"),
            discord.SelectOption(label="Save Template", value="save", emoji=emoji("SAVE")),
            discord.SelectOption(label="Load Template", value="load", emoji="📂"),
            discord.SelectOption(label="Reset", value="reset", emoji="🔄"),
        ])
        select.callback = self.callback
        box.add_item(ui.ActionRow(select))
        self.add_item(box)

    async def callback(self, interaction: discord.Interaction) -> None:
        action = self.children[0].children[1].children[0].values[0]
        if action == "name":
            async def done(i, value):
                self.builder.state.name = value[:100]
                self.builder._build()
                await i.response.edit_message(view=self.builder)
            await interaction.response.send_modal(TextModal("Container Name", "Name", self.builder.state.name, done))
        elif action == "color":
            async def done(i, value):
                try:
                    self.builder.state.accent_color = int(value.strip().lstrip("#"), 16)
                    if not 0 <= self.builder.state.accent_color <= 0xFFFFFF:
                        raise ValueError
                except ValueError:
                    await i.response.send_message(f"{emoji('ERROR')} Use a valid hex color such as `5865F2`.", ephemeral=True)
                    return
                self.builder._build()
                await i.response.edit_message(view=self.builder)
            current = f"{self.builder.state.accent_color:06X}" if self.builder.state.accent_color is not None else "5865F2"
            await interaction.response.send_modal(TextModal("Accent Color", "Hex color", current, done))
        elif action == "export":
            data = io.BytesIO(self.builder.state.to_json().encode())
            await interaction.response.send_message(file=discord.File(data, filename="helzerx-components-v2.json"), ephemeral=True)
        elif action == "import":
            await interaction.response.send_modal(JsonModal(self._import))
        elif action == "save":
            async def done(i, value):
                self.builder.store.save(self.builder.owner_id, value.strip()[:50], self.builder.state)
                await i.response.send_message(f"{emoji('SUCCESS')} Template saved as **{value.strip()[:50]}**.", ephemeral=True)
            await interaction.response.send_modal(TextModal("Save Template", "Template name", self.builder.state.name, done))
        elif action == "load":
            names = self.builder.store.names(self.builder.owner_id)[:25]
            if not names:
                await interaction.response.send_message(f"{emoji('WARNING')} No saved templates.", ephemeral=True)
                return
            select = ui.Select(placeholder="Choose a template...", options=[discord.SelectOption(label=n, value=n) for n in names])
            async def load_callback(i):
                payload = self.builder.store.load(self.builder.owner_id, select.values[0])
                if payload:
                    self.builder.state = BuilderState.from_dict(self.builder.owner_id, payload)
                    self.builder._build()
                    await i.response.edit_message(view=self.builder)
            select.callback = load_callback
            v = ui.LayoutView(timeout=120)
            v.add_item(ui.Container(ui.TextDisplay("### Load Template"), ui.ActionRow(select)))
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
