from main import rvc_serverless_pipe
import argparse
import json
import os
import base64

parser = argparse.ArgumentParser()
parser.add_argument("--request_json", type=str, required=True)
args = parser.parse_args()
request = json.load(open(args.request_json, "r"))

pipeline = rvc_serverless_pipe()

pipeline.prepare()

import time

init_time = time.time()

for i in range(10):
    result = pipeline.handler(request)
    print(result)

end_time = time.time()

print("Total Time:", (end_time - init_time) / 10 )
