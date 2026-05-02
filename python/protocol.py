from sklearn.ensemble import AdaBoostClassifier,RandomForestClassifier,RandomForestRegressor  # type: ignore[import-untyped]
from sklearn.model_selection import train_test_split  # type: ignore[import-untyped]

from typing import Protocol,TypeVar
import numpy as np # type: ignore[import-untyped]

T=TypeVar('T')



# class Model(Protocol[T]):
#     def fit(self,x_train:T,y_train:T)->None:
#         ...
#     def predict(self,x_test:T)->T:
#         ...


def evaluate(model,x_test:T,y_test:T)->T:
    preds=model.predict(x_test)
    return preds

if __name__=="__main__":
    model1=AdaBoostClassifier()
    model2=RandomForestClassifier() 
    model3=RandomForestRegressor()

    x=np.array([1,2,3,4,5,6,7,8,10]) 
    y=np.array([1,2,3,4,5,6,7,8,10])
    x=x.reshape(-1, 1)
    y=y.reshape(-1)

    print(x,y)

    x_train,x_test,y_train,y_test=train_test_split(x,y,train_size=0.7,shuffle=False)

    print(x_train,x_test)
    print(y_train,y_test)

    models=[model1,model2,model3]

    for model in models:
        model.fit(x_train,y_train)
        print(f"model:{model},{y_test} ",evaluate(model,x_test,y_test))




