class Solution:
    def digitFrequencyScore(self, n: int) -> int:
        Count={}
        while n!=0:
            temp=n%10
            n=n//10
            if temp!=0:
                Count[temp]=Count.get(temp,0)+1
        result=0
        for num,freq in Count.items():
            result+=num*freq

        return result
            
            
        
