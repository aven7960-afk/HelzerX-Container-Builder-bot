from __future__ import annotations

import discord
from discord import ui

from bot.builder.state import BuilderState, ComponentSpec
from bot.emoji import emoji


COMPONENT_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("text", "Text Display", "Rich markdown text"),
    ("section", "Section", "Text with an accessory"),
    ("separator", "Separator", "Visual divider"),
    ("media", "Media Gallery", "One or more images"),
    ("thumbnail", "Thumbnail", "Compact media accessory"),
    ("button", "Button", "Interactive button"),
    ("select", "String Select", "Dropdown menu"),
    ("action_row", "Action Row", "Interactive component row"),
    ("file", "File", "Inline file component"),
)


def _component_icon(component_type: str) -> str:
    return {
        "text": emoji("TEXT"),
        "section": emoji("SECTION"),
        "separator": emoji("SEPARATOR"),
        "media": emoji("MEDIA"),
        "thumbnail": emoji("THUMBNAIL"),
        "button": emoji("BUTTON"),
        "select": emoji("SELECT"),
        "action_row": emoji("ACTION_ROW"),
        "file": emoji("FILE"),
    }.get(component_type, "•")


class BuilderView(ui.LayoutView):
    """Interactive Components V2 builder panel.

    The UI is deliberately state-driven: every interaction rebuilds the
    layout from ``BuilderState``. This makes later JSON persistence and
    template support straightforward.
    """

    def __init__(self, owner_id: int, accent_color: int = 0x5865F2):
        super().__init__(timeout=900)
        self.state = BuilderState(owner_id=owner_id, accent_color=accent_color)
        self._build()

    def _build(self) -> None:
        self.clear_items()

        container = ui.Container(
            accent_color=(
                discord.Colour(self.state.accent_color)
                if self.state.accent_color is not None
                else None
            )
        )

        container.add_item(
            ui.TextDisplay(
                f"# {emoji('BUILDER')} HelzerX Container Builder V2\n"
                "Build modern Discord Components V2 layouts directly from Discord."
            )
        )
        container.add_item(ui.Separator())
        container.add_item(
            ui.TextDisplay(
                f"### {emoji('PREVIEW')} Live Preview\n"
                f"Components: **{self.state.component_count}/{self.state.MAX_COMPONENTS}**\n"
                "The preview below reflects your current component tree."
            )
        )
        container.add_item(ui.Separator())

        if self.state.components:
            lines = []
            for index, component in enumerate(self.state.components, start=1):
                lines.append(
                    f"`{index:02}` {_component_icon(component.type)} **{component.type.replace('_', ' ').title()}**"
                )
            container.add_item(ui.TextDisplay("\n".join(lines)))
        else:
            container.add_item(
                ui.TextDisplay(
                    "*Your container is empty.*\n"
                    "Use **Add Component** below to start building."
                )
            )

        add_select = ui.Select(
            placeholder=f"{emoji('ADD')} Add a component...",
            custom_id=f"builder:add:{self.state.owner_id}",
            options=[
                discord.SelectOption(
                    label=label,
                    value=value,
                    description=description,
                    emoji=_component_icon(value),
                )
                for value, label, description in COMPONENT_OPTIONS
            ],
        )
        add_select.callback = self._add_component
        container.add_item(ui.ActionRow(add_select))

        actions = ui.ActionRow(
            ui.Button(
                label="Edit",
                emoji=emoji("EDIT"),
                style=discord.ButtonStyle.secondary,
                custom_id=f"builder:edit:{self.state.owner_id}",
            ),
            ui.Button(
                label="Remove",
                emoji=emoji("REMOVE"),
                style=discord.ButtonStyle.danger,
                custom_id=f"builder:remove:{self.state.owner_id}",
            ),
            ui.Button(
                label="Reorder",
                emoji=emoji("REORDER"),
                style=discord.ButtonStyle.secondary,
                custom_id=f"builder:reorder:{self.state.owner_id}",
            ),
            ui.Button(
                label="Color",
                emoji=emoji("COLOR"),
                style=discord.ButtonStyle.secondary,
                custom_id=f"builder:color:{self.state.owner_id}",
            ),
            ui.Button(
                label="Send",
                emoji=emoji("SEND"),
                style=discord.ButtonStyle.success,
                custom_id=f"builder:send:{self.state.owner_id}",
            ),
        )
        container.add_item(actions)

        for button in actions.children:
            button.callback = self._action_dispatch

        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.state.owner_id:
            await interaction.response.send_message(
                f"{emoji('ERROR')} This builder belongs to another user.",
                ephemeral=True,
            )
            return False
        return True

    async def _add_component(self, interaction: discord.Interaction) -> None:
        select = interaction.data
        values = select.get("values", []) if isinstance(select, dict) else []
        if not values:
            await interaction.response.defer()
            return

        component_type = str(values[0])
        defaults = {
            "text": {"content": "# Hello from HelzerX\nBuild something great."},
            "section": {"content": "Section content", "accessory": "button"},
            "separator": {"spacing": "small"},
            "media": {"items": []},
            "thumbnail": {"url": "https://example.com/image.png"},
            "button": {"label": "Click me", "style": "primary"},
            "select": {"placeholder": "Choose an option", "options": []},
            "action_row": {},
            "file": {"url": "https://example.com/file.txt"},
        }
        self.state.add(ComponentSpec(component_type, defaults.get(component_type, {})))
        self._build()
        await interaction.response.edit_message(view=self)

    async def _action_dispatch(self, interaction: discord.Interaction) -> None:
        custom_id = str(interaction.data.get("custom_id", "")) if interaction.data else ""
        action = custom_id.split(":")[1] if ":" in custom_id else ""

        if action == "remove":
            if self.state.components:
                self.state.remove(len(self.state.components) - 1)
                self._build()
                await interaction.response.edit_message(view=self)
                return
            await interaction.response.send_message("Nothing to remove yet.", ephemeral=True)
            return

        if action == "reorder":
            if len(self.state.components) >= 2:
                self.state.move(len(self.state.components) - 1, -1)
                self._build()
                await interaction.response.edit_message(view=self)
                return
            await interaction.response.send_message("Add at least two components first.", ephemeral=True)
            return

        if action == "send":
            await interaction.response.send_message(
                f"{emoji('SUCCESS')} Builder is ready. Message sending will be wired to the final renderer next.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"{emoji('BUILDER')} **{action.title() if action else 'Action'}** is reserved for the next builder module.",
            ephemeral=True,
        )
