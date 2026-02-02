
def custom_fence(fence: str):
    def add_fence(func):
        def wrapper(text:str):
            print(fence*len(text))
            func(text)
            print(fence*len(text))
        return wrapper
    return add_fence

@custom_fence(input("Enter the fence type:"))
def print_smt(text:str):
    print(text)


print_smt("Dilip")