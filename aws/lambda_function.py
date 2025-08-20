import json, boto3, os

bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("BEDROCK_REGION","us-east-1"))
MODEL_ID = os.getenv("MODEL_ID", "us.meta.llama3-2-1b-instruct-v1:0")  

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        user_message = (body.get("message") or "").strip()
        if not user_message:
            return _resp(400, {"error": "message required"})

        # Llama 3.x expects `prompt` and returns `generation`
        prompt = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            "You are a friendly assistant for a pet food store called Hi Nature Pet!. Reply briefly and politely.\n"
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
            f"{user_message}\n"
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        )

        payload = {
            "prompt": prompt,
            "max_gen_len": 400,     # NOT max_tokens
            "temperature": 0.3
            # optional: "top_p": 0.9, "stop": ["<|eot_id|>"]
        }

        r = bedrock.invoke_model(
            modelId=MODEL_ID,                   
            body=json.dumps(payload),
            accept="application/json",
            contentType="application/json",
        )
        data = json.loads(r["body"].read())
        text = (data.get("generation") or "").strip()
        if not text:
            return _resp(502, {"error": "empty model response", "raw": data})
        return _resp(200, {"reply": text})
    except Exception as e:
        # during bring-up, surface the error to caller
        return _resp(502, {"error": str(e)})

def _resp(code, obj):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type"
        },
        "body": json.dumps(obj)
    }
