# *args are more like list of values
# **kwargs are more like dictionary of values

from typing import ParamSpec , TypeVar, Callable

R=TypeVar('R')
P=ParamSpec('P')


def wrapper(func:Callable[P,R])->Callable[P,R]:
    def inner(*args:P.args,**kwargs:P.kwargs) ->R:
        print(args, kwargs)
        return func(*args,**kwargs)
    return inner
    
def add(a:int,b:int)->int:
    
    return a+b

if __name__=="__main__":
    wrapped=wrapper(add)
    print(wrapped(10,b= 20))