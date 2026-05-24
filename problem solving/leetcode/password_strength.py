class Solution:
    def passwordStrength(self, password: str) -> int:
        lowerCase=[]
        upperCase=[]
        digits=[]
        special=['!','@','#','$']
        existSpecial=[]
        points=0

        for i in password:
            if i in special:
                if i not in existSpecial:
                    points+=5
                    existSpecial.append(i)
            elif i.isdigit():
                if i not in digits:
                    digits.append(i)
                    points+=3

                    
            elif i.upper()==i:
                if i not in upperCase:
                    points+=2
                    upperCase.append(i)
            elif i.lower()==i:
                if i not in lowerCase:
                    points+=1
                    lowerCase.append(i)

            print(points,i)
        return points©leetcode
