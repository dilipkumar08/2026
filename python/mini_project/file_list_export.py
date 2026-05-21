import os
import pandas as pd

def file_list_export(folder_path:str,export_path:str):

    """This function will generate a excel for the given path with sub folders as 
    headers and files inside that sub folders as rows of those headers"""

    file_name=str(input("Please, Enter the file name:"))
    data=dict()
    print("Exporting....🔃")

    try:
        for columns in os.listdir(folder_path):
            #only choosing the folders as headers instead of anyfiles
            column_path=os.path.join(folder_path,columns)
            if os.path.isdir(column_path):
                data[columns]= os.listdir(column_path)
        
        #pandas can't handle improper size between columns so we convert it to series then to dataframe
        df=pd.DataFrame({key:pd.Series(value) for key,value in data.items()})

        df.fillna('') # replacing the Null values with ''
        #print(df)
        df.to_excel(os.path.join(export_path,file_name+ ".xlsx"),index=False)
    except Exception as e:
        print(f"Process failed ⛔ : {e}") 
    print("Process Completed Successfully ✅")


if __name__=="__main__":
    folder_path=str(input("Please, Enter the folder path:"))
    export_path=str(input("please, Enter the export file path:"))
    file_list_export(folder_path,export_path)
