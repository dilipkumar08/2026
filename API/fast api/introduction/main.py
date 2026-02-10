from fastapi import FastAPI,status,HTTPException
from scalar_fastapi import get_scalar_api_reference
from typing import Any

app=FastAPI()

shipments={ 9:{"weight":.9,"content":"glassware","status":"placed"}, 4:{"weight":.4,"content":"glassware","status":"placed"}, 11:{"weight":.11,"content":"glassware","status":"placed"}
           , 6:{"weight":.6,"content":"glassware","status":"placed"}, 8:{"weight":.8,"content":"glassware","status":"placed"}
           , 3:{"weight":.3,"content":"glassware","status":"placed"}}

@app.get("/shipment/latest")
def get_latest_shipment() -> dict: 
    latest_id=max(shipments.keys())
    print(latest_id)
    return shipments[latest_id]

@app.get("/shipment/status/") 
def get_shipment_status(id: int) -> dict:
    if id not in shipments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return shipments[id]


@app.get("/shipment/{field}")
def get_shipment_field(field:str,id:int)->dict:
    return { field:shipments[id][field]}


@app.post("/shipment")
def submit_shipment(data:dict[str,Any])->dict:
    content=data.get("content")
    weight=data.get("weight")
    if weight>25:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Shipment weight exceeds the limit of 25 kg")
    new_id=max(shipments.keys())+1
    shipments[new_id]={"content":content,"weight":weight,"status":"placed"}
    return {"id":new_id}

@app.put("/shipment")
def shipment_update(id:int,content:str,weight:float,status:str)->dict:
    if id not in shipments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    shipments[id]={"content":content,"weight":weight,"status":status}
    return {"id":id} 

@app.get("/scalar",include_in_schema=False  ) # this is to induce a better API documentation interface
def get_scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url,title="Scalar API")