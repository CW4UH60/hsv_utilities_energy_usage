# Home Assistant Integration for HSV Utilities Energy

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]

Unofficial Home Assistant integration for Huntsville Utilities / HSV Utilities SmartHub usage data.

This fork keeps the Home Assistant domain as `hsv_utilities_energy` and is intended to use SmartHub as a bill-reconciliation source. Sense or another local meter should remain the primary real-time source for Home Assistant's Energy Dashboard.

## What It Does

- Polls HSV Utilities SmartHub through the cloud API.
- Defaults to electric data only for data minimization.
- Keeps recent SmartHub data in an in-memory cache.
- Writes long-term usage and cost data into Home Assistant recorder statistics.
- Creates Home Assistant sensors for enabled utility types.

The Home Assistant integration no longer depends on Delta Lake storage. The standalone scripts in this repository can still write Delta Lake data for offline analysis, but the HACS integration path uses the in-memory cache plus Home Assistant statistics.

## Requirements

- HSV Utilities SmartHub username
- HSV Utilities SmartHub password
- Service location number
- Account number
- Home Assistant with recorder enabled

## Disclaimer

This integration is not affiliated with, associated with, or sponsored by Huntsville Utilities, HSV Utilities, SmartHub, or any related entity. Use it at your own discretion and protect your Home Assistant admin access, filesystem access, and backups.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Go to `HACS > Integrations`.
3. Open `Custom repositories`.
4. Add `https://github.com/CW4UH60/hsv_utilities_energy_usage`.
5. Select category `Integration`.
6. Download `HSV Utilities Energy`.
7. Restart Home Assistant.
8. Go to `Settings > Devices & services > Add integration`.
9. Search for `HSV Utilities Energy`.

### Manual

1. Copy `custom_components/hsv_utilities_energy` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings > Devices & services`.

## Configuration

The setup flow asks for:

| Field | Notes |
| --- | --- |
| Username | SmartHub username or email |
| Password | SmartHub password, shown as a password field |
| Service Location Number | From SmartHub |
| Account Number | From SmartHub |
| Data Path | Kept for backward compatibility; not used by the HA integration |
| Update Interval | Default `900` seconds, minimum `300`, maximum `86400` |
| Fetch Days | Default `30`, maximum `30` |
| Utility Types | Default `ELECTRIC`; gas and water are optional |

Existing config entries keep their configured utility type list. New config entries default to electric only.

## Sensors

For each enabled utility type, the integration creates usage and cost sensors.

| Sensor | Description | Unit | State Class |
| --- | --- | --- | --- |
| Electric Usage | Recent electric consumption | kWh | `total_increasing` |
| Electric Cost | Recent electric cost from SmartHub | USD | `total_increasing` |
| Gas Usage | Recent gas consumption, if enabled | CCF or source unit | `total_increasing` |
| Gas Cost | Recent gas cost, if enabled | USD | `total_increasing` |

Sensor attributes include today, yesterday, last 24 hours, last update, and data lag where available.

SmartHub data is delayed. Treat it as billing reconciliation data, not as a live load meter.

## Services

### `hsv_utilities_energy.refresh_data`

Requests an immediate poll.

| Parameter | Required | Description |
| --- | --- | --- |
| `entry_id` | No | Target one config entry. Required when multiple entries are loaded. |

### `hsv_utilities_energy.clear_statistics`

Clears the integration's in-memory cache and forces a statistics rebuild. This can rewrite historical statistics, so it requires explicit confirmation.

| Parameter | Required | Description |
| --- | --- | --- |
| `confirm_rebuild` | Yes | Must be `true`. |
| `entry_id` | No | Target one config entry. Required when multiple entries are loaded. |

Example:

```yaml
service: hsv_utilities_energy.clear_statistics
data:
  confirm_rebuild: true
```

## Security Notes

- Home Assistant stores config entry data, including SmartHub credentials, in `.storage/core.config_entries`.
- Limit who has Home Assistant admin access, Samba access, SSH access, backup access, and filesystem access.
- This fork redacts passwords, bearer tokens, emails, account numbers, service location numbers, and meter numbers from integration logs.
- If SmartHub logs, Home Assistant logs, screenshots, or diagnostics were shared before this hardening pass, rotate the SmartHub password.
- The standalone CLI can still write raw JSON or Delta Lake records containing utility data and identifiers when explicitly requested. Keep those files private.

## Standalone CLI

The repository still includes standalone scripts for analysis outside Home Assistant.

```bash
uv sync
uv run main.py -i ELECTRIC -d 7
```

The CLI defaults to electric only and uses a 30-second HTTP timeout. Use `.env.example` as a template for local credentials, and never commit `.env`.

## Development

Useful checks:

```bash
uv run ruff format --check
uv run ruff check
uv run pytest
python -m compileall custom_components/hsv_utilities_energy
```

## License

MIT License. See [LICENSE](LICENSE).

[commits-shield]: https://img.shields.io/github/commit-activity/w/CW4UH60/hsv_utilities_energy_usage?style=flat-square
[commits]: https://github.com/CW4UH60/hsv_utilities_energy_usage/commits/master
[releases-shield]: https://img.shields.io/github/release/CW4UH60/hsv_utilities_energy_usage.svg?style=flat-square
[releases]: https://github.com/CW4UH60/hsv_utilities_energy_usage/releases
