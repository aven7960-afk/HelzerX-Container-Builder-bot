from __future__ import annotations

from discord import ui

from bot.views import builder_plus as base


class FixedComponentEditor(base.ComponentEditor):
    """Use Label as the visible field label; nested TextInput must not set label."""

    def _field(self, key: str, label: str, value: str, paragraph: bool) -> None:
        field = ui.TextInput(
            default=value[:4000],
            required=False,
            placeholder=label[:100],
            style=base.discord.TextStyle.paragraph if paragraph else base.discord.TextStyle.short,
        )
        self.add_item(ui.Label(text=label[:45], component=field))
        self.fields.append((key, field))


class FixedMediaUploadModal(base.MediaUploadModal):
    """FileUpload and TextInput are wrapped by Label; nested TextInput has no label."""

    def __init__(self, owner: "base.BuilderPlusView", index: int):
        base.ui.Modal.__init__(self, title="Upload Media")
        self.owner = owner
        self.index = index
        self.upload = ui.FileUpload(
            custom_id=f"hx_media_{owner.owner_id}_{index}",
            min_values=1,
            max_values=10,
            required=True,
        )
        self.description = ui.TextInput(
            required=False,
            max_length=256,
            style=base.discord.TextStyle.short,
            placeholder="Description (optional)",
        )
        self.add_item(ui.Label(text="Image / Video / File", component=self.upload))
        self.add_item(ui.Label(text="Description", component=self.description))


# The existing BuilderPlusView/ComponentPicker callbacks resolve these names
# from the original module globals, so replace them before exporting the view.
base.ComponentEditor = FixedComponentEditor
base.MediaUploadModal = FixedMediaUploadModal

BuilderPlusView = base.BuilderPlusView
