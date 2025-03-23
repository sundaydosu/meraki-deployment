import os
import json
import logging
import argparse
import subprocess
import sys
from datetime import datetime
from dotenv import load_dotenv
import meraki

# Ensure required packages are installed
required_packages = ["meraki", "requests", "python-dotenv"]
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)

# Load environment variables from .env file
load_dotenv()

# Configure logging
log_filename = f"meraki_deployment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load configuration from config.json
try:
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    logger.error("Missing config.json file. Ensure it exists in the script directory.")
    sys.exit(1)

dashboard_api_base_url = config.get("dashboard_api_base_url", "https://api.meraki.com/api/v1")
organization_id = config.get("organization_id")
meraki_api_key = os.getenv("MERAKI_API_KEY", config.get("meraki_api_key"))
default_timezone = config.get("default_timezone", "America/Los_Angeles")

if not meraki_api_key or not organization_id:
    logger.error("Missing API key or organization ID. Ensure they are set in .env or config.json.")
    sys.exit(1)

# Initialize Meraki SDK Client
dashboard = meraki.DashboardAPI(api_key=meraki_api_key, suppress_logging=True)

def get_or_create_network(network_name=None, tags=None, ignore_existing=False):
    """Fetches an existing network or creates a new one."""
    try:
        # If network name is provided, try to find it
        if network_name:
            networks = dashboard.organizations.getOrganizationNetworks(organization_id)
            for network in networks:
                if network["name"] == network_name:
                    if not ignore_existing:
                        logger.warning(f"Network '{network_name}' already exists. Use --ignore-existing to use it.")
                        return None
                    logger.info(f"Using existing network: {network['id']} ({network_name})")
                    return network["id"]
            
            # Network not found, create it
            network = dashboard.organizations.createOrganizationNetwork(
                organization_id,
                name=network_name,
                productTypes=["appliance", "switch"],
                timezone=default_timezone,
                tags=tags if tags else []
            )
            logger.info(f"Created network: {network['id']} ({network_name})")
            return network["id"]
        else:
            # No name provided, use first available network
            networks = dashboard.organizations.getOrganizationNetworks(organization_id)
            if networks:
                network_id = networks[0]["id"]
                logger.info(f"Using existing network: {network_id} ({networks[0]['name']})")
                return network_id
            else:
                # No networks found, create a default one
                network = dashboard.organizations.createOrganizationNetwork(
                    organization_id,
                    name="Automated Network",
                    productTypes=["appliance", "switch"],
                    timezone=default_timezone,
                    tags=tags if tags else []
                )
                logger.info(f"Created network: {network['id']} (Automated Network)")
                return network["id"]
    except meraki.APIError as e:
        logger.error(f"Error with network operations: {e}")
        sys.exit(1)

def get_available_devices():
    """Fetches available switches and MX85 appliances from the organization."""
    try:
        devices = dashboard.organizations.getOrganizationDevices(organization_id)
        switch_serial, mx85_serial = None, None
        for device in devices:
            if "MS" in device["model"] and not switch_serial:
                switch_serial = device["serial"]
            elif "MX85" in device["model"] and not mx85_serial:
                mx85_serial = device["serial"]
        if switch_serial and mx85_serial:
            logger.info(f"Found devices: Switch={switch_serial}, MX85={mx85_serial}")
            return switch_serial, mx85_serial
    except meraki.APIError as e:
        logger.error(f"Error retrieving devices: {e}")
    sys.exit(1)

def deploy_meraki_device(serial_number, network_id, device_type, address=None):
    """Deploys a Meraki device to a network and verifies successful deployment."""
    try:
        # Claim the device into the network
        dashboard.networks.claimNetworkDevices(network_id, serials=[serial_number])
        logger.info(f"{device_type} {serial_number} deployment initiated.")

        # Set device name based on model
        try:
            device_info = dashboard.devices.getDevice(serial_number)
            device_name = f"{device_info['model']}_{serial_number}"
            dashboard.devices.updateDevice(serial_number, name=device_name)
            logger.info(f"Device named as: {device_name}")
            
            # Set device address if provided
            if address:
                dashboard.devices.updateDevice(serial_number, address=address, moveMapMarker=True)
                logger.info(f"Device address set to: {address}")
        except meraki.APIError as e:
            logger.warning(f"Could not set device name or address: {e}")

        # Verify if the device is assigned to the network
        devices = dashboard.networks.getNetworkDevices(network_id)
        assigned_serials = [device["serial"] for device in devices]

        if serial_number in assigned_serials:
            logger.info(f"Verification Successful: {device_type} {serial_number} is now in the network.")
        else:
            logger.error(f"Verification Failed: {device_type} {serial_number} is NOT found in the network.")
            sys.exit(1)

    except meraki.APIError as e:
        logger.error(f"Failed to deploy {device_type}: {e}")
        sys.exit(1)

def bind_network_to_template(network_id, template_name):
    """Binds a network to a configuration template."""
    try:
        # Get available templates
        templates = dashboard.organizations.getOrganizationConfigTemplates(organization_id)
        
        # Find the requested template
        template_id = None
        for template in templates:
            if template["name"] == template_name:
                template_id = template["id"]
                break
                
        if not template_id:
            logger.error(f"Template '{template_name}' not found")
            return False
            
        # Bind network to template
        dashboard.networks.bindNetwork(network_id, configTemplateId=template_id)
        logger.info(f"Network successfully bound to template '{template_name}'")
        return True
        
    except meraki.APIError as e:
        logger.error(f"Failed to bind network to template: {e}")
        return False

def main():
    """Main execution flow for Meraki device deployment."""
    parser = argparse.ArgumentParser(description="Automate Meraki device deployment.")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode without making changes")
    parser.add_argument("--network-name", help="Name of network to create or use")
    parser.add_argument("--tags", help="Comma-separated tags to apply to the network")
    parser.add_argument("--template", help="Name of configuration template to bind the network to")
    parser.add_argument("--address", help="Street address for deployed devices (for map placement)")
    parser.add_argument("--ignore-existing", action="store_true", help="Use existing network if it exists")
    parser.add_argument("--switch-serial", help="Serial number of switch to deploy (overrides auto-detection)")
    parser.add_argument("--appliance-serial", help="Serial number of appliance to deploy (overrides auto-detection)")
    args = parser.parse_args()

    logger.info("Starting Meraki Deployment...")
    
    # Convert tags string to list if provided
    tags = args.tags.split(',') if args.tags else None
    
    # Create or get network
    network_id = get_or_create_network(args.network_name, tags, args.ignore_existing)
    if not network_id:
        sys.exit(1)
    
    # Bind to template if specified
    if args.template and not args.dry_run:
        if not bind_network_to_template(network_id, args.template):
            logger.warning("Continuing deployment without template binding.")
    
    # Get device serials (either from args or auto-detect)
    if args.switch_serial and args.appliance_serial:
        switch_serial = args.switch_serial
        mx85_serial = args.appliance_serial
        logger.info(f"Using provided device serials: Switch={switch_serial}, MX85={mx85_serial}")
    else:
        switch_serial, mx85_serial = get_available_devices()

    if not args.dry_run:
        deploy_meraki_device(switch_serial, network_id, "Switch", args.address)
        deploy_meraki_device(mx85_serial, network_id, "MX85 Security Appliance", args.address)
        logger.info("Deployment completed successfully!")
    else:
        logger.info("Dry-run mode enabled. No actual changes were made.")
        logger.info(f"Would deploy switch {switch_serial} and appliance {mx85_serial} to network {network_id}")
        if args.template:
            logger.info(f"Would bind network to template '{args.template}'")
        if args.address:
            logger.info(f"Would set device address to '{args.address}'")

if __name__ == "__main__":
    main()