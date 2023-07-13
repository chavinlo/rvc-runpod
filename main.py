from gradio_client import Client
import runpod
import os
import time
import uuid
from threading import Thread
import requests
import boto3
from botocore.client import Config
from modelmanager import model_manager

IGNORE_PATH = "/stub"

GOTO_ROOT = "/../../../../../../../"

UPLOAD_MODE = os.environ.get("UPLOAD_MODE", None)

if UPLOAD_MODE == "transfersh":
    from transfersh_client.app import send_to_transfersh
elif UPLOAD_MODE == "s3":
    BUCKET_AREA = os.environ.get("BUCKET_AREA", None)
    BUCKET_ENDPOINT_URL = os.environ.get("BUCKET_ENDPOINT_URL", None)
    BUCKET_ACCESS_KEY_ID = os.environ.get("BUCKET_ACCESS_KEY_ID", None)
    BUCKET_SECRET_ACCESS_KEY = os.environ.get("BUCKET_SECRET_ACCESS_KEY", None)
    BUCKET_NAME = BUCKET_ENDPOINT_URL.split("//")[-1].split(".")[0]
else:
    raise Exception("UPLOAD_MODE not found")

def error(msg):
    return {
        "statusCode": 400,
        "body": msg
    }

def success(msg):
    return {
        "statusCode": 200,
        "body": msg
    }

class rvc_serverless_pipe():
    def __init__(self):
        self.client = None
        self.model_manager = model_manager()

    def prepare(self):
        """
        Preparation function, returns gradio client object.
        Fails if cannot connect to gradio API.
        """
        # create stub
        with open(IGNORE_PATH, "w") as f:
            f.write("stub")

        if UPLOAD_MODE == "s3":
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

    def infer_args_parse(self, arguments):
        if "audio_url" not in arguments:
            return error("audio_url not found")
        if "model_name" not in arguments:
            return error("model_name not found")
        if "transpose" not in arguments:
            return error("transpose not found")
        if "pitch_extraction_algorithm" not in arguments:
            return error("pitch_extraction_algorithm not found")
        if "search_feature_ratio" not in arguments:
            return error("search_feature_ratio not found")
        if "filter_radius" not in arguments:
            return error("filter_radius not found")
        if "resample_output" not in arguments:
            return error("resample_output not found")
        if "volume_envelope" not in arguments:
            return error("volume_envelope not found")
        if "voiceless_protection" not in arguments:
            return error("voiceless_protection not found")
        if "hop_len" not in arguments:
            return error("hop_len not found")
        
        # transpose
        if not isinstance(arguments["transpose"], int):
            return error("transpose must be int")
        
        # pitch_extraction_algorithm
        if arguments["pitch_extraction_algorithm"] not in ["pm", "harvest", 'dio', 'crepe', 'crepe-tiny', 'mangio-crepe', 'mangio-crepe-tiny']:
            return error("pitch_extraction_algorithm not found")
        
        # search_feature_ratio
        if not isinstance(arguments["search_feature_ratio"], float):
            return error("search_feature_ratio must be float")
        if arguments['search_feature_ratio'] < 0 or arguments['search_feature_ratio'] > 1:
            return error("search_feature_ratio must be between 0 and 1")
        
        # filter_radius
        if not isinstance(arguments["filter_radius"], int):
            return error("filter_radius must be int")
        if arguments['filter_radius'] < 0 or arguments['filter_radius'] > 7:
            return error("filter_radius must be between 0 and 7")
        
        # resample_output
        if not isinstance(arguments["resample_output"], int):
            return error("resample_output must be int")
        if arguments['resample_output'] < 0 or arguments['resample_output'] > 48000:
            return error("resample_output must be between 0 and 48000")
        
        # volume_envelope
        if not isinstance(arguments["volume_envelope"], float):
            return error("volume_envelope must be float")
        if arguments['volume_envelope'] < 0 or arguments['volume_envelope'] > 1:
            return error("volume_envelope must be between 0 and 1")
        
        # voiceless_protection
        if not isinstance(arguments["voiceless_protection"], float):
            return error("voiceless_protection must be float")
        if arguments['voiceless_protection'] < 0 or arguments['voiceless_protection'] > 1:
            return error("voiceless_protection must be between 0 and 1")
        
        # hop_len
        if not isinstance(arguments["hop_len"], int):
            return error("hop_len must be int")
        if arguments['hop_len'] < 0 or arguments['hop_len'] > 512:
            return error("hop_len must be between 0 and 512")
        
        # model_name
        if not isinstance(arguments["model_name"], str):
            return error("model_name must be str")
        
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

        mm_response = self.model_manager.get_model(model_name)

        if mm_response['statusCode'] != 200:
            return mm_response
        else:
            # NOTE: we shouldn't do this, but I rather not touch the garbage that is gradio
            pth_path = GOTO_ROOT + mm_response['body']['pth_path']
            index_path = GOTO_ROOT + mm_response['body']['index_path']

        client.predict(
                pth_path,
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
            index_path,
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

        if UPLOAD_MODE == "s3":
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
        elif UPLOAD_MODE == "transfersh":
            audio_url = send_to_transfersh(out_audio_path, clipboard=False)
            audio_url = audio_url.replace("\n", "").replace("transfer.sh", "transfer.sh/get")

        os.remove(out_audio_path)

        return success({
            "success_message": success_message,
            "audio_url": audio_url
        })

    def handler(self, event):
        request = event['input']

        return self.infer(request)

def main():
    pipeline = rvc_serverless_pipe()

    pipeline.prepare()

    runpod.serverless.start({
        "handler": pipeline.handler,
    })

if __name__ == "__main__":
    main()