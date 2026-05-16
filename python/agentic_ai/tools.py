from typing import Callable


class tool:
    """
    A class represents resuable piece of code (Tool)
    
    Attributes: 
    name (str): Name of the tool
    description (str): A textual description of what the tool does
    func (callable): the function this tool wraps
    arguments (list): A list of arguments
    outputs (str or list): the return type of the wrapped funciton
    """

    def __init__(self,name:str,description:str,func:Callable,arguments:list,outputs:str|list):
        self.name=name
        self.description=description
        self.func=func
        self.arguments=arguments
        self.outputs=outputs

    
    def to_string(self)->str:
        """
        Return a string representation of the tool,
        including its name, description, arguments, and outputs.
        """
        args_str=','.join([f"{arg_name}:{arg_type}" for arg_name,arg_type in self.arguments])

        return (
            f"Tool Name: {self.name},"
            f" Description: {self.description},"
            f" Arguments: {args_str},"
            f" Outputs: {self.outputs}"
        )
