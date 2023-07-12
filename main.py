from gradio_client import Client
import runpod
import os
import time
import magic
import uuid
from threading import Thread
import requests
import boto3
from botocore.client import Config

RVC_REPO_DIR = "/rvc_repo"
RVC_MODEL_DIR = "/rvc_repo/weights"

INDEX_APPEND_PATH = "added_IVF1653_Flat_nprobe_1_v2.index"
IGNORE_PATH = "/stub"

BUCKET_AREA = os.environ.get("BUCKET_AREA", None)
BUCKET_ENDPOINT_URL = os.environ.get("BUCKET_ENDPOINT_URL", None)
BUCKET_ACCESS_KEY_ID = os.environ.get("BUCKET_ACCESS_KEY_ID", None)
BUCKET_SECRET_ACCESS_KEY = os.environ.get("BUCKET_SECRET_ACCESS_KEY", None)
BUCKET_NAME = BUCKET_ENDPOINT_URL.split("//")[-1].split(".")[0]

class rvc_serverless_pipe():
    def __init__(self):
        self.client = None
        self.mime = magic.Magic(mime=True)

    def error(self, msg):
        return {
            "statusCode": 400,
            "body": msg
        }

    def success(self, msg):
        return {
            "statusCode": 200,
            "body": msg
        }

    def prepare(self):
        """
        Preparation function, returns gradio client object.
        Fails if cannot connect to gradio API.
        """
        # create stub
        with open(IGNORE_PATH, "w") as f:
            f.write("stub")

        session = boto3.Session(
            aws_access_key_id=BUCKET_ACCESS_KEY_ID,
            aws_secret_access_key=BUCKET_SECRET_ACCESS_KEY,
            region_name=BUCKET_AREA
        )

        s3 = session.client('s3',
            endpoint_url=BUCKET_ENDPOINT_URL,
            config=Config(signature_version='s3v4', region_name=BUCKET_AREA)
        )

        self.s3 = s3

        print("AWS BUCKET CONFIGURATION:")
        print(f"BUCKET_AREA: {BUCKET_AREA}")
        print(f"BUCKET_ENDPOINT_URL: {BUCKET_ENDPOINT_URL}")
        print(f"BUCKET_ACCESS_KEY_ID: {BUCKET_ACCESS_KEY_ID[:4]}...{BUCKET_ACCESS_KEY_ID[-4:]}")
        print(f"BUCKET_SECRET_ACCESS_KEY: {BUCKET_SECRET_ACCESS_KEY[:4]}...{BUCKET_SECRET_ACCESS_KEY[-4:]}")
        print(f"BUCKET_NAME: {BUCKET_NAME}")

        # start gradio in bg with thread
        def start_gradio():
            os.system("cd /rvc_repo && make run-ui")

        thread = Thread(target=start_gradio)
        thread.start()

        attempts = 0

        # wait for gradio to start
        time.sleep(5)
        while attempts < 10:
            try:
                client = Client("http://127.0.0.1:7860/")
                result = client.predict(
                            fn_index=0
                )

                self.client = client

                return
            except Exception as e:
                pass
            time.sleep(2)
            attempts += 1

        raise Exception("Cannot connect to gradio API")
    
    def list_models(self):
        os.listdir(RVC_MODEL_DIR)
        # remove .pth extension
        return [x[:-4] for x in os.listdir(RVC_MODEL_DIR)]

    def infer_args_parse(self, arguments):
        if "audio_url" not in arguments:
            return self.error("audio_url not found")
        if "model_name" not in arguments:
            return self.error("model_name not found")
        if "transpose" not in arguments:
            return self.error("transpose not found")
        if "pitch_extraction_algorithm" not in arguments:
            return self.error("pitch_extraction_algorithm not found")
        if "search_feature_ratio" not in arguments:
            return self.error("search_feature_ratio not found")
        if "filter_radius" not in arguments:
            return self.error("filter_radius not found")
        if "resample_output" not in arguments:
            return self.error("resample_output not found")
        if "volume_envelope" not in arguments:
            return self.error("volume_envelope not found")
        if "voiceless_protection" not in arguments:
            return self.error("voiceless_protection not found")
        if "hop_len" not in arguments:
            return self.error("hop_len not found")
        
        # transpose
        if not isinstance(arguments["transpose"], int):
            return self.error("transpose must be int")
        
        # pitch_extraction_algorithm
        if arguments["pitch_extraction_algorithm"] not in ["pm", "harvest", 'dio', 'crepe', 'crepe-tiny', 'mangio-crepe', 'mangio-crepe-tiny']:
            return self.error("pitch_extraction_algorithm not found")
        
        # search_feature_ratio
        if not isinstance(arguments["search_feature_ratio"], float):
            return self.error("search_feature_ratio must be float")
        if arguments['search_feature_ratio'] < 0 or arguments['search_feature_ratio'] > 1:
            return self.error("search_feature_ratio must be between 0 and 1")
        
        # filter_radius
        if not isinstance(arguments["filter_radius"], int):
            return self.error("filter_radius must be int")
        if arguments['filter_radius'] < 0 or arguments['filter_radius'] > 7:
            return self.error("filter_radius must be between 0 and 7")
        
        # resample_output
        if not isinstance(arguments["resample_output"], int):
            return self.error("resample_output must be int")
        if arguments['resample_output'] < 0 or arguments['resample_output'] > 48000:
            return self.error("resample_output must be between 0 and 48000")
        
        # volume_envelope
        if not isinstance(arguments["volume_envelope"], float):
            return self.error("volume_envelope must be float")
        if arguments['volume_envelope'] < 0 or arguments['volume_envelope'] > 1:
            return self.error("volume_envelope must be between 0 and 1")
        
        # voiceless_protection
        if not isinstance(arguments["voiceless_protection"], float):
            return self.error("voiceless_protection must be float")
        if arguments['voiceless_protection'] < 0 or arguments['voiceless_protection'] > 1:
            return self.error("voiceless_protection must be between 0 and 1")
        
        # hop_len
        if not isinstance(arguments["hop_len"], int):
            return self.error("hop_len must be int")
        if arguments['hop_len'] < 0 or arguments['hop_len'] > 512:
            return self.error("hop_len must be between 0 and 512")
        
        # model_name
        if not isinstance(arguments["model_name"], str):
            return self.error("model_name must be str")
        if arguments["model_name"] not in self.list_models():
            return self.error("Model not found")
        
        return None

    def infer(self, request):
        client = self.client
        arguments = request['arguments']
        
        """
        Argument list:
        'audio_url': url to mp3 file,
        'model_name': str,
        'transpose': int,
        'pitch_extraction_algorithm': str,
        'search_feature_ratio': float,
        'filter_radius': int,
        'resample_output': int,
        'volume_envelope': float,
        'voiceless_protection': float,
        'hop_len': int,
        """

        check = self.infer_args_parse(arguments)
        if check is not None:
            return check
        
        # grab extension from url
        ext = arguments["audio_url"].split(".")[-1]

        work_uuid = uuid.uuid4()

        # save
        inp_audio_path = f"/tmp/{work_uuid}.{ext}"

        with open(inp_audio_path, "wb") as f:
            f.write(requests.get(arguments["audio_url"]).content)
            
        # prepare model
        model_name = arguments['model_name']

        client.predict(
                f"{model_name}.pth",
                0,
                0,
                fn_index=5,
        )

        # inference
        result = client.predict(
            0,
            inp_audio_path,
            arguments["transpose"],
            IGNORE_PATH,
            arguments["pitch_extraction_algorithm"],
            f"logs/{model_name}/{INDEX_APPEND_PATH}",
            IGNORE_PATH,
            arguments["search_feature_ratio"],
            arguments["filter_radius"],
            arguments["resample_output"],
            arguments["volume_envelope"],
            arguments["voiceless_protection"],
            arguments["hop_len"],
            fn_index=2)
        
        # result is a tuple:
        # (success message, path to audio)
        # detuple:
        success_message, out_audio_path = result

        # remove leftover files
        #os.remove(out_audio_path)
        os.remove(inp_audio_path)

        s3 = self.s3

        with open(out_audio_path, 'rb') as data:
            s3.upload_fileobj(data, BUCKET_NAME, f"{work_uuid}.{ext}")
            
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': f"{work_uuid}.{ext}"
                }
        )

        audio_url = presigned_url
        
        os.remove(out_audio_path)

        return self.success({
            "success_message": success_message,
            "audio_path": out_audio_path,
            "audio_url": audio_url
        })

    def handler(self, event):
        request = event['input']

        operation = request['operation']
        arguments = request['arguments']

        if operation == "list_models":
            return self.list_models()
        elif operation == "infer":
            return self.infer(request)
        else:
            return self.error("Unknown operation")

def main():
    pipeline = rvc_serverless_pipe()

    pipeline.prepare()

    runpod.serverless.start({
        "handler": pipeline.handler,
    })

if __name__ == "__main__":
    main()