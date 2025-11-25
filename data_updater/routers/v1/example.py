from fastapi import APIRouter

router = APIRouter(prefix="/example", tags=["Example"])


@router.get("")
async def get_example():
    return {"message": "This is an example endpoint"}


@router.get("/{item_id}")
async def get_example_item(item_id: int):
    return {"item_id": item_id, "message": f"Example item {item_id}"}
