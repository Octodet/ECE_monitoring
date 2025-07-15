import requests
import json
import os
import sys
from dotenv import load_dotenv
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings for insecure requests (use with caution in production)
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Load environment variables from .env file
load_dotenv()

# --- Configuration from .env ---
HOST = os.getenv('HOST')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
API_KEY = os.getenv('API_KEY')
OUTPUT_FILE = os.getenv('OUTPUT_FILE', 'metrics.json')  
VERIFY_SSL = os.getenv('VERIFY_SSL', False) == True  

def make_api_request(url, username = None, password = None ,verify_ssl=False, stream=False):
    """
    Makes an API GET request and returns the JSON response.

    Args:
        url (str): The URL for the API endpoint.
        username (str): The username for authentication.
        password (str): The password for authentication.
        verify_ssl (bool): Whether to verify SSL certificates (default: False).
        stream (bool): Whether to stream the response content (default: False).

    Returns:
        dict: The JSON response from the API, or an error dictionary if the request fails.
    """
    try:
        if API_KEY : 
            response = requests.get(url, headers = {"Authorization": f"ApiKey {API_KEY}"}, verify=verify_ssl, stream=stream)
        else :
            response = requests.get(url, auth=(username, password), verify=verify_ssl, stream=stream)
        response.raise_for_status()  
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP error for {url}: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        return {"error": "HTTPError", "status_code": e.response.status_code, "details": e.response.text}
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed for {url}: {e}", file=sys.stderr)
        return {"error": "RequestException", "details": str(e)}

def fetch_platform_and_allocators(host, username, password, verify_ssl):
    """
    Fetches platform information and allocator details.

    Args:
        host (str): The base URL of the environment.
        username (str): The username for authentication.
        password (str): The password for authentication.
        verify_ssl (bool): Whether to verify SSL certificates.

    Returns:
        dict: A dictionary containing 'platform_info' and 'allocators' data.
    """
    print("\n--- Fetching Platform and Allocator Information ---")
    metrics = {}
    metrics["platform_info"] = make_api_request(f"{host}/api/v1/platform", username, password, verify_ssl)
    metrics["allocators"] = make_api_request(f"{host}/api/v1/platform/infrastructure/allocators", username, password, verify_ssl)
    return metrics

def fetch_deployment_list(host, username, password, verify_ssl):
    """
    Fetches the list of all deployments.

    Args:
        host (str): The base URL of the environment.
        username (str): The username for authentication.
        password (str): The password for authentication.
        verify_ssl (bool): Whether to verify SSL certificates.

    Returns:
        list: A list of deployment dictionaries.
    """
    print("\n--- Fetching Deployment List ---")
    deployment_list_response = make_api_request(f"{host}/api/v1/deployments", username, password, verify_ssl)
    return deployment_list_response.get('deployments', [])

def fetch_deployment_details(host, username, password, verify_ssl, deployment):
    """
    Fetches detailed information for a single deployment, including ES cluster health and stats.

    Args:
        host (str): The base URL of the environment.
        username (str): The username for authentication.
        password (str): The password for authentication.
        verify_ssl (bool): Whether to verify SSL certificates.
        deployment (dict): The deployment dictionary containing at least 'id' and 'name'.

    Returns:
        dict: The updated deployment dictionary with 'details', 'elasticsearch_cluster_health',
              and 'elasticsearch_cluster_stats' if available.
    """
    dep_id = deployment['id']
    dep_name = deployment.get('name', dep_id)
    print(f"\nProcessing Deployment: '{dep_name}' (ID: {dep_id})")

    # Get full deployment details to find the ES endpoint
    details_url = f"{host}/api/v1/deployments/{dep_id}?show_metadata=true"
    details = make_api_request(details_url, username, password, verify_ssl)
    deployment["details"] = details

    # Elasticsearch resource and its endpoint
    es_resource = None
    if isinstance(details, dict) and 'resources' in details and 'elasticsearch' in details['resources']:
        es_resource = next((r for r in details['resources']['elasticsearch'] if 'info' in r and 'cluster_id' in r['info']), None)

    if es_resource and es_resource['info'].get('cluster_id') and es_resource['info']['cluster_id'] != "cluster_id":
        es_endpoint = es_resource['info']['metadata'].get('service_url')
        if es_endpoint:
            print(f"  Found Elasticsearch endpoint: {es_endpoint}")

            # Fetch ES Cluster Health
            health_url = f"{es_endpoint}/_cluster/health"
            deployment["elasticsearch_cluster_health"] = make_api_request(health_url, username, password, verify_ssl)

            # Fetch ES Cluster Stats
            stats_url = f"{es_endpoint}/_cluster/stats"
            deployment["elasticsearch_cluster_stats"] = make_api_request(stats_url, username, password, verify_ssl)
        else:
            print("  Elasticsearch service URL not found in metadata.")
    else:
        print("  Elasticsearch resource endpoint not found or deployment is not ready.")
    return deployment

def print_summary(metrics_data):
    """
    Prints a detailed summary of the collected metrics.

    Args:
        metrics_data (dict): The dictionary containing all collected metrics.
    """
    print("\n" + "="*50)
    print("                 METRICS SUMMARY")
    print("="*50)

    # Allocator summary
    all_allocators_flat = []
    allocators_response = metrics_data.get("allocators", {})
    if isinstance(allocators_response, dict) and "zones" in allocators_response:
        for zone in allocators_response["zones"]:
            if "allocators" in zone and isinstance(zone["allocators"], list):
                all_allocators_flat.extend(zone["allocators"])

    if all_allocators_flat:
        total_mem_gb = sum(a['capacity']['memory']['total'] for a in all_allocators_flat if 'capacity' in a and 'memory' in a['capacity'] and 'total' in a['capacity']['memory']) / 1024
        used_mem_gb = sum(a['capacity']['memory']['used'] for a in all_allocators_flat if 'capacity' in a and 'memory' in a['capacity'] and 'used' in a['capacity']['memory']) / 1024
        print(f"\n--- Allocators ({len(all_allocators_flat)} found) ---")
        print(f"  Total Memory Capacity: {total_mem_gb:.2f} GB")
        print(f"  Used Memory Capacity:  {used_mem_gb:.2f} GB ({used_mem_gb/total_mem_gb:.1%})" if total_mem_gb > 0 else "N/A")
    else:
        print("\n--- Allocators: Could not retrieve data or no allocators found. ---")
        if isinstance(allocators_response, dict) and "error" in allocators_response:
            print(f"  Error details: {allocators_response.get('details', 'No details available')}")

    # Deployment summary
    deployments = metrics_data.get("deployments_details", [])
    print(f"\n--- Inspected Deployments ({len(deployments)} found) ---")
    if not deployments:
        print("  No deployments found or collected.")
    else:
        for dep in sorted(deployments, key=lambda x: x.get('name', x['id'])):
            health_info = dep.get("elasticsearch_cluster_health", {})
            status_text = "Status: N/A"  

            if "error" in health_info:
                status_text = f"Could not fetch health (Error: {health_info.get('details', 'unknown error')})"
            else:
                status = health_info.get("status", "unknown")
                relocating = health_info.get('relocating_shards', 0)
                status_text = f"Status: {status.upper()} | Relocating Shards: {relocating}"
            # This is the line where the icon was removed
            print(f"  - {dep.get('name', dep['id'])}: {status_text}")
    print("\n" + "="*50 + "\n")

def save_metrics_to_file(data, output_file):
    """
    Saves the collected metrics data to a JSON file.

    Args:
        data (dict): The dictionary containing all collected metrics.
        output_file (str): The path to the output JSON file.
    """
    print(f"Attempting to write all collected data to '{output_file}'...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved metrics to '{output_file}'")
    except IOError as e:
        print(f"ERROR: Could not write to file '{output_file}': {e}", file=sys.stderr)
    except TypeError as e:
        print(f"ERROR: Data serialization error when writing to '{output_file}': {e}", file=sys.stderr)

def main():
    """
    Main function to load configuration, fetch metrics, print summary, and save to file.
    """
    # Validate essential environment variables
    if not API_KEY and not all([HOST, USERNAME, PASSWORD]):
        print("ERROR: Please ensure either API_KEY or  (HOST, USERNAME, and PASSWORD) are set in your .env file.", file=sys.stderr)
        sys.exit(1)

    print(f"--- Starting Metrics Collection for Host: {HOST} ---")
    all_metrics = {}

    # Fetch Platform and Allocator
    platform_allocator_metrics = fetch_platform_and_allocators(HOST, USERNAME, PASSWORD, VERIFY_SSL)
    all_metrics.update(platform_allocator_metrics)

    # Fetch Deployments
    all_deployments = fetch_deployment_list(HOST, USERNAME, PASSWORD, VERIFY_SSL)
    all_metrics["deployments_details"] = [] # Initialize as a list

    # Fetch Detailed Metrics for each deployment
    if all_deployments:
        print("\n--- Fetching Detailed Metrics for Deployments ---")
        for dep in all_deployments:
            detailed_dep = fetch_deployment_details(HOST, USERNAME, PASSWORD, VERIFY_SSL, dep)
            all_metrics["deployments_details"].append(detailed_dep)
    else:
        print("No deployments found to fetch detailed metrics for.")

    # Print Summary
    print_summary(all_metrics)

    # Save to file
    save_metrics_to_file(all_metrics, OUTPUT_FILE)

if __name__ == "__main__":
    main()