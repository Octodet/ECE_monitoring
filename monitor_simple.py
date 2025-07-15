import requests
import json
import os
import sys
import argparse
import fnmatch 

DEFAULT_OUTPUT_FILENAME = "ece_metrics.json"
host = 'https://my-ece-instance.co:12443'
api_key= 'ECE_API_KEY'

def make_api_request(url, headers, verify_ssl, stream=False):
    """Make API Request """
    try:
        response = requests.get(url, headers=headers, verify=verify_ssl, stream=stream)
        response.raise_for_status()   
        return response.json()
    except requests.exceptions.HTTPError as e:
        return {"error": "HTTPError", "status_code": e.response.status_code, "details": e.response.text}
    except requests.exceptions.RequestException as e:
        return {"error": "RequestException", "details": str(e)}

def print_summary(metrics_data):
    """Prints a detailed summary of the collected metrics."""
    try:
        # Allocator summary
        allocators = metrics_data.get("allocators", {}).get("allocators", [])
        if allocators and "error" not in allocators:
            total_mem_gb = sum(a['capacity']['memory']['total'] for a in allocators) / 1024
            used_mem_gb = sum(a['capacity']['memory']['used'] for a in allocators) / 1024
            print(f"Allocators: {len(allocators)} found")
            print(f"Total Memory Capacity: {total_mem_gb:.2f} GB")
            print(f"Used Memory Capacity:  {used_mem_gb:.2f} GB ({used_mem_gb/total_mem_gb:.1%})")
        else:
            print("Allocators: Could not retrieve data.")

        # Deployment summary
        deployments = metrics_data.get("deployments_details", [])
        print(f"\nInspected Deployments: {len(deployments)} found matching filter")
        for dep in sorted(deployments, key=lambda x: x['name']):
            health_info = dep.get("elasticsearch_cluster_health", {})
            if "error" in health_info:
                status_icon = "❓"
                status_text = f"Could not fetch health ({health_info.get('details', 'unknown error')})"
            else:
                status = health_info.get("status", "unknown")
                relocating = health_info.get('relocating_shards', 0)
                status_text = f"Status: {status.upper()} | Relocating Shards: {relocating}"
            print(f" - {dep['name']}: {status_icon} {status_text}")

    except Exception as e:
        print(f"\nCould not generate summary : {e}", file=sys.stderr)
    print("-------------------------\n")


def main():
    if not api_key:
        print("ERROR: API key not provided. Set ECE_API_KEY env var or use --api-key.", file=sys.stderr)
        sys.exit(1)
    headers = {"Authorization": f"ApiKey {api_key}"}
    verify_ssl = not insecure
    if insecure:
        print("SSL certificate verification is disabled.", file=sys.stderr)
        from urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    all_metrics = {}

    # Fetch Platform and Allocator 
    print("\nFetching paltform and allocators ...")
    all_metrics["platform_info"] = make_api_request(f"{host}/api/v1/platform", headers, verify_ssl)
    all_metrics["allocators"] = make_api_request(f"{host}/api/v1/platform/infrastructure/allocators", headers, verify_ssl)

    # Fetch Deployments  
    print("\nFetching deployment list...")
    deployment_list_response = make_api_request(f"{host}/api/v1/deployments", headers, verify_ssl)
    
    if "error" in deployment_list_response:
        all_metrics["deployments_details"] = []
    else:
        all_deployments = deployment_list_response.get('deployments', [])
        filtered_deployments = [
            d for d in all_deployments if fnmatch.fnmatch(d.get('name', ''), filter_name)
        ]
        print(f" Found {len(all_deployments)} total deployments")
        all_metrics["deployments_details"] = filtered_deployments

        # Fetch Detailed Metrics
        print("\nFetching details and cluster health for filtered deployments...")
        for dep in all_metrics["deployments_details"]:
            dep_id = dep['id']
            dep_name = dep.get('name', dep_id)
            print(f"\nProcessing Deployment: '{dep_name}'")

            # Get full deployment details to find the ES endpoint
            details_url = f"{host}/api/v1/deployments/{dep_id}?show_metadata=true"
            details = make_api_request(details_url, headers, verify_ssl)
            dep["details"] = details

            # Elasticsearch resource and its endpoint
            es_resource = next((r for r in details.get('resources', {}).get('elasticsearch', [])), None)
            if es_resource and es_resource['info']['cluster_id'] != "cluster_id":
                es_endpoint = es_resource['info']['links']['https']
                print(f" Found Elasticsearch endpoint: {es_endpoint}")

                # Fetch ES Cluster Health
                health_url = f"{es_endpoint}/_cluster/health"
                dep["elasticsearch_cluster_health"] = make_api_request(health_url, headers, verify_ssl)

                # Fetch ES Cluster Stats
                stats_url = f"{es_endpoint}/_cluster/stats"
                dep["elasticsearch_cluster_stats"] = make_api_request(stats_url, headers, verify_ssl)
            else:
                print(" Elasticsearch resource endpoint not found or deployment is not ready.")
                
    print_summary(all_metrics)
    print(f"Writing all collected data to '{output_file}'...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_metrics, f, ensure_ascii=False, indent=4)
        print(f"Successfully saved metrics to '{output_file}'")
    except IOError as e:
        print(f"Could not write to file '{output_file}': {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
