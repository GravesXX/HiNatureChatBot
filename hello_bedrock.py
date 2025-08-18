# hello_bedrock.py
import os, json, boto3

# Region where you enabled Llama 3.2 access
REGION    = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID  = os.getenv("BEDROCK_MODEL_ID", "meta.llama3-2-3b-instruct")  # put your exact id here

# Optionally force a profile: export AWS_PROFILE=your-profile
session = boto3.Session(profile_name=os.getenv("AWS_PROFILE")) if os.getenv("AWS_PROFILE") else boto3.Session()
brt = session.client("bedrock-runtime", region_name=REGION)

def main():
    messages = [
        {"role": "system", "content": [{"text": "You are a helpful assistant."}]},
        {"role": "user",   "content": [{"text": "In one sentence, say hello to a pet store customer."}]},
    ]

    resp = brt.converse(
        modelId=MODEL_ID,
        messages=messages,
        inferenceConfig={"maxTokens": 128, "temperature": 0.3}
    )

    text = "".join(part.get("text","") for part in resp["output"]["message"]["content"])
    print(text)

if __name__ == "__main__":
    main()
