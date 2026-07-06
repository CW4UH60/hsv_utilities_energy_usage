"""Service schemas for HSV Utilities Energy."""

from __future__ import annotations

import voluptuous as vol

ATTR_CONFIRM_REBUILD = "confirm_rebuild"
ATTR_ENTRY_ID = "entry_id"

SERVICE_REFRESH_DATA_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): str})
SERVICE_CLEAR_STATISTICS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): str,
        vol.Required(ATTR_CONFIRM_REBUILD): vol.Equal(True),
    }
)
