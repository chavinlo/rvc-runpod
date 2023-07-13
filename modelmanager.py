import huggingface_hub
import json
import os

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

class model_manager():
    def __init__(self):
        hf_token = os.environ.get("HF_TOKEN", None)
        if hf_token is not None:
            huggingface_hub.login(token=hf_token)
        else:
            raise Exception("HF_TOKEN not found")
        pass

    def verify_config(self, config):
        #existance
        if 'arch_type' not in config:
            return error("arch_type not found")
        
        if 'arch_version' not in config:
            return error("arch_version not found")
        
        if 'components' not in config:
            return error("components not found")

        #type
        if not isinstance(config['arch_type'], str):
            return error("arch_type must be str")
        
        if not isinstance(config['arch_version'], str):
            return error("arch_version must be str")
        
        if not isinstance(config['components'], dict):
            return error("components must be dict")
        
        #arch_type
        if config['arch_type'] != "rvc":
            return error("arch_type must be 'rvc'")
        
        if "pth" not in config['components']:
            return error("components['pth'] not found")
        
        if "index" not in config['components']:
            return error("components['index'] not found")
        
        return None

    def get_model(self, model_name):
        config_path = huggingface_hub.hf_hub_download(
            repo_id=model_name,
            filename="config.json",
            repo_type="model")
        
        with open(config_path, "r") as f:
            config = json.load(f)

        check = self.verify_config(config)
        if check is not None:
            return check
        
        pth_path = huggingface_hub.hf_hub_download(
            repo_id=model_name,
            filename=config['components']['pth'],
            repo_type="model")
        
        index_path = huggingface_hub.hf_hub_download(
            repo_id=model_name,
            filename=config['components']['index'],
            repo_type="model")
        
        return success({
            "config": config,
            "pth_path": pth_path,
            "index_path": index_path
        })
        


        