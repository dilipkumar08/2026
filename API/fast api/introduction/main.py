from fastapi import FastAPI, status, HTTPException
from scalar_fastapi import get_scalar_api_reference
from typing import Any
import model
import database
app = FastAPI()
shipments=database.shipments


@app.get("/shipment/latest")
def get_latest_shipment() -> dict:
    latest_id = max(shipments.keys ())
    print(latest_id)
    return shipments[latest_id]


@app.get("/shipment/status/",response_model=model.Shipment)
def get_shipment_status(id: int) :
    if id not in shipments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found"
        )
    return shipments[id]


@app.get("/shipment/{field}")
def get_shipment_field(field: str, id: int) -> dict:
    return {field: shipments[id][field]}


@app.post("/shipment")
def submit_shipment(Shipment: model.Shipment) -> model.Shipment:

    if Shipment.weight > 25:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Shipment weight exceeds the limit of 25 kg",
        )
    new_id = max(shipments.keys()) + 1
    shipments[new_id] = {"id":new_id,"content": Shipment.content, "weight": Shipment.weight, "status": "placed"}
    return {"id": new_id}


@app.put("/shipment{id}")
def shipment_update(id: int, content: str, weight: float, status: model.ShipmentStatus) -> dict:
    if id not in shipments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found"
        )
    shipments[id] = {"content": content, "weight": weight, "status": status}
    return {"id": id}

@app.patch("/shipment{id}")
def patch_shipment(id: int, content: str | None = None, weight: float | None = None, status: model.ShipmentStatus | None = None) -> dict:
    if id not in shipments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found"
        )
    if content is not None:
        shipments[id]["content"] = content
    if weight is not None:
        shipments[id]["weight"] = weight
    if status is not None:
        shipments[id]["status"] = status
    return {"id": id}


@app.delete("/shipment")
def delete_shipment(id: int) -> dict:
    if id not in shipments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found"
        )
    del shipments[id]
    return {"id": id}

@app.get(
    "/scalar", include_in_schema=False
)  # this is to induce a better API documentation interface
def get_scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title="Scalar API")
