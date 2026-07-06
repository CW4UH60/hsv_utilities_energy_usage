# HSV Utilities Energy

Unofficial Home Assistant integration for HSV Utilities / Huntsville Utilities SmartHub data.

This integration polls SmartHub usage and cost data, keeps recent results in memory, and imports long-term data into Home Assistant recorder statistics. It defaults to electric-only data for privacy and data minimization. Gas and water can be enabled from the integration options if needed.

SmartHub should be treated as a delayed billing and reconciliation source. Keep Sense or another local meter as the primary real-time Energy Dashboard source.

## Security

Home Assistant stores SmartHub credentials in `.storage/core.config_entries`. Protect Home Assistant admin, Samba, SSH, filesystem, backup, and diagnostics access. This fork redacts common secrets and identifiers from logs, but rotate the SmartHub password if old logs or screenshots containing account data were shared.

## Services

- `hsv_utilities_energy.refresh_data`: refresh now; accepts optional `entry_id`.
- `hsv_utilities_energy.clear_statistics`: rebuild statistics; requires `confirm_rebuild: true` and accepts optional `entry_id`.
