## Overview
This Python-based solution automates the deployment of Meraki switches and MX85 security appliances using the Meraki Dashboard API. It combines flexibility, configurability, and validation to streamline enterprise rollouts.

## Key Features
- Uses the official Meraki SDK for API communication  
- Supports both `.env` and `config.json` for configuration  
- Automatically installs missing dependencies  
- Creates or selects networks dynamically  
- Optionally binds to a Meraki configuration template  
- Claims and validates **switch & MX85 appliances**  
- Sets custom device names and addresses  
- CLI arguments for tags, templates, dry-run, serial overrides  
- **Verifies deployments and logs all actions**  

## Requirements
- **Python 3.6 or later**  
- **API access to your Meraki organization**  
- **Devices must exist in your org's inventory** (MS, MX85)  

## Installation
The script installs its own dependencies, but you can also install them manually:  
```bash
pip install meraki requests python-dotenv
```

## Configuration Options

### Method 1: `.env` File (Recommended)
```ini
MERAKI_API_KEY=your_meraki_api_key
```

### Method 2: `config.json`
```json
{
  "dashboard_api_base_url": "https://api.meraki.com/api/v1",
  "organization_id": "YOUR_ORG_ID",
  "meraki_api_key": "YOUR_API_KEY",
  "default_timezone": "America/Los_Angeles"
}
```

## CLI Usage
```bash
python meraki_deployment.py [OPTIONS]
```

### Common Options
- `--dry-run` — simulate without making changes  
- `--network-name` — set or use a specific network name  
- `--ignore-existing` — skip creation if network already exists  
- `--tags` — apply comma-separated tags to the network  
- `--template` — bind network to a configuration template  
- `--address` — assign location address to devices  
- `--switch-serial` — override detected switch serial  
- `--appliance-serial` — override detected MX85 serial  

## Workflow Summary
1. Load API key and config  
2. Discover or create network (named or default)  
3. Optionally bind to template  
4. Identify or override switch and MX85 serials  
5. Claim devices and assign name/address  
6. Verify device assignment in the network  
7. Log output to file and console  

## Logging
- Console + file logs with timestamps  
- File is named:  
  ```plaintext
  meraki_deployment_YYYYMMDD_HHMMSS.log
  ```

## Troubleshooting
| Issue | Solution |
|--------|----------|
| **Missing or invalid API key or org ID** | Check `.env` or `config.json` |
| **Devices not found** | Ensure they are available in inventory |
| **Permissions error** | Ensure API key has full access |

## Security Recommendations
- Use `.env` to store secrets (**not in version control**)  
- Apply **least-privilege principle** to API keys  
- **Rotate API keys** on a regular basis  
