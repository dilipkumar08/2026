class Solution:
    def numberOfSpecialChars(self, word: str) -> int:
        if len(word)==1:
            return 0
        
        else:
            passed=[]
            result=0

            for i in word:
                if (i.upper() in word) and (i.lower() in word) and (i.lower() not in passed):
                    passed.append(i.lower())
                    result+=1
            return result
