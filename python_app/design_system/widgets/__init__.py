"""Design system widget components.

Reusable, self-styling PyQt6 widgets for the MusicGenerator application.
"""

from python_app.design_system.widgets.buttons import (
    DesignButton,
    PrimaryButton,
    SecondaryButton,
    DangerButton,
    SuccessButton,
    IconButton,
    ToggleButton,
    GhostButton,
    OutlinedButton,
)
from python_app.design_system.widgets.toggle_switch import ToggleSwitch
from python_app.design_system.widgets.inputs import (
    StyledLineEdit,
    StyledComboBox,
    StyledSpinBox,
)
from python_app.design_system.widgets.custom_slider import CustomSlider
from python_app.design_system.widgets.labels import TypedLabel
from python_app.design_system.widgets.transport import TransportButton, SeekBar
from python_app.design_system.widgets.now_playing_card import NowPlayingCard
from python_app.design_system.widgets.icon import Icon
from python_app.design_system.widgets.status_badge import StatusBadge
from python_app.design_system.widgets.gradient_button import GradientButton
from python_app.design_system.widgets.table_action_button import TableActionButton
from python_app.design_system.widgets.indeterminate_progress import IndeterminateProgress

__all__ = [
    "DesignButton",
    "PrimaryButton",
    "SecondaryButton",
    "DangerButton",
    "SuccessButton",
    "IconButton",
    "ToggleButton",
    "GhostButton",
    "OutlinedButton",
    "ToggleSwitch",
    "StyledLineEdit",
    "StyledComboBox",
    "StyledSpinBox",
    "CustomSlider",
    "TypedLabel",
    "TransportButton",
    "SeekBar",
    "NowPlayingCard",
    "Icon",
    "StatusBadge",
    "GradientButton",
    "TableActionButton",
    "IndeterminateProgress",
]
