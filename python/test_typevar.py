from _typeshed import SupportsAdd
from typing import TypeVar, List

# I don’t know the type yet, but it must stay consistent

T=TypeVar('T',bound=SupportsAdd)

def sample(input:T)->T:
    return input+input


IF=TypeVar('IF', int,float)

def sample2(input:IF)->IF:
    return input*2

class Animal:
    def __init__(self):
        pass
    def make_sound(self)->str:
        return "Some sound"

class Dog(Animal):
    def make_sound(self)->str:
        return "Bark"
    
class Cat(Animal):
    def make_sound(self)->str:
        return "Meow"
    
AnimalType=TypeVar('AnimalType', bound=Animal)

def get_animal_sound(animal:List[AnimalType]):
    for i in animal:
        print(i.make_sound())

if __name__=="__main__":
    print(sample(5))
    print(sample("Hello"))
    get_animal_sound([Dog(), Cat(),Animal()])