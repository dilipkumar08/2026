#!/bin/python3

def predict_result(charge:float):
    return min(2*charge,8)


if __name__ == "__main__":
    timeCharged = float(input().strip())
    result = predict_result(timeCharged)

    print("{0:.2f}".format(result))
