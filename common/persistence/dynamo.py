import os, boto3

_TABLE = boto3.resource("dynamodb", region_name=os.environ["REGION"]).Table(os.environ["TABLE_NAME"])

def load_user(user_id: str) -> dict:
    resp = _TABLE.get_item(Key={"user_id": str(user_id)})
    return resp.get("Item", {"user_id": str(user_id), "tz": None, "next_id": 1, "items": {}})

def save_user(state: dict) -> None:
    _TABLE.put_item(Item=state)