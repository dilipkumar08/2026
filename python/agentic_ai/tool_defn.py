from datetime import datetime
from typing import Literal
from langchain.tools import tool

@tool
def age_finder(day:int,month:Literal[1,2,3,4,5,6,7,8,9,10,11,12],year:int)->int:
    """ converts age from date of birth."""
    current_year=datetime.now().year
    current_month=datetime.now().month
    current_day=datetime.now().day
    age=current_year-year
    if month>current_month:
        age-=1
    elif month==current_month:
        if day<=current_day:
            age-=1
    return age
    
            

print("description:",age_finder.description,"name:",age_finder.name,"arguments:",age_finder.args)
