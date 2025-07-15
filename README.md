# Elastic Cloud Enterprise Monitor
This Python script is designed to collect various operational metrics from your Elastic Cloud Enterprise deployments, including platform information, allocator statistics, and detailed Elasticsearch cluster health and stats for each deployment. 


## The Scripts

``` monitor_ece.py ``` : Collects metrics from Elastic Cloud Enterprise using username and password authentication.

``` monitor_ece_w_api_key.py ``` : Collects metrics from Elastic Cloud Enterprise using an API key for authentication.

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
Navigate to the directory containing **monitor_ece.py** or **monitor_ece_w_api_key.py**  and .env in your terminal, then run the script:

```bash
python monitor_ece.py
```

or 

```bash
python monitor_ece_w_api_key.py