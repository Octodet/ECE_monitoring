# Elastic Cloud Metrics Collector
This Python script is designed to collect various operational metrics from your Elastic Cloud deployments, including platform information, allocator statistics, and detailed Elasticsearch cluster health and stats for each deployment. It's configured to pull sensitive information like host, username, and password directly from a .env file for enhanced security and ease of management.

## Prerequisites

Before running the script, ensure you have the following installed:

* Python 3.x
* `requests` library
* `python-dotenv` library

You can install the necessary Python libraries using pip:

```bash
pip install -r requirement.txt
```

## How to Run
Navigate to the directory containing metrics_collector.py and .env in your terminal, then run the script:

```bash
python monitor_ece.py