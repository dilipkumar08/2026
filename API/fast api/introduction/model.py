from pydantic import BaseModel,Field
from enum import Enum


class ShipmentStatus(str, Enum):
    placed = "placed" 
    in_transit = "in_transit"
    delivered = "delivered"
    out_for_delivery = "out_for_delivery"

    
class Shipment(BaseModel):
    content:str =Field(min_length=1,max_length=25)
    weight:float =Field(lt=25) 
    status : ShipmentStatus