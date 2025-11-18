import requests
import json
import uuid 
import time

# This combines the system CA store with the Python CA store
import truststore
truststore.inject_into_ssl()

username = "arista"
password = "7fwp7eyvpin9ouui"
device_list = ["leaf1", "leaf2", "leaf3", "leaf4", "spine1", "spine2", "spine3", "spine4", "borderleaf1", "borderleaf2"]

# device_list = ["borderleaf1"]
config_dir = "configs"
cs_id = uuid.uuid4()

# Format is HH:MM:SS
commit_timer = "00:00:30"
# Seconds as integer
wait_to_commit = 10


for device in device_list:
    with open(f"{config_dir}/{device}.cfg", "r") as fh:
        new_config = fh.read()

# First eAPI call to configure session
    url = f"https://{device}/command-api"
    json_payload = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {
                "version": 1,
                "cmds": [
                    "enable",
                    f"configure session {cs_id}",
                    "rollback clean-config", 
                    {
                        "cmd": "copy terminal: session-config",
                        "input": new_config
                    },
                    f"commit timer {commit_timer}"
                ],
                "format": "json",
                "timestamps": False,
                "autoComplete": True,
                "expandAliases": False,
                "stopOnError": True,
                "streaming": False,
                "includeErrorDetail": False
            },
            "id": "EapiExplorer-1"
    }
    print(f"Attempting push for {device}")
    try:
        response = requests.post(
            url=url,
            data=json.dumps(json_payload),
            auth=(username, password),
    #       verify=false,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        result_code = response.status_code
        if result_code == 200:
            print(f"Config pushed for {device}... waiting for confirm")
    except requests.exceptions.Timeout:
        print(f"Config push for {device} timed out, exiting")
        exit()
    except requests.exceptions.RequestException as e:
        print("An error occurred")
    time.sleep(wait_to_commit)
    url = f"https://{device}/command-api"
    json_payload = {
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {
                "version": 1,
                "cmds": [
                    "enable",
                    f"configure session {cs_id} commit",
                ],
                "format": "json",
                "timestamps": False,
                "autoComplete": True,
                "expandAliases": False,
                "stopOnError": True,
                "streaming": False,
                "includeErrorDetail": False
            },
            "id": "EapiExplorer-1"
    }
    try:
        response = requests.post(
            url=url,
            data=json.dumps(json_payload),
            auth=(username, password),
    #       verify=false,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        print("Config push confirmed.")
    except requests.exceptions.Timeout:
        print(f"Configuration couldn't be pushed to {device}, config will rollback automatically")
    except requests.exceptions.RequestException as e:
        print("An error occurred")