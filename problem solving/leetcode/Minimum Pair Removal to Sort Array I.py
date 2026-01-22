
class Solution:
    def isSorted(self,nums:List[int]):
        length=len(nums)
        for idx in range(length-1):
            if nums[idx+1]<nums[idx]:
                print('false')
                return False
        return True
    
    def sumMinimum(self,nums:List[int]):
        length=len(nums)
        minIdx=-1
        maxVal=float('inf')
        
        for idx in range(length-1):
            if nums[idx]+nums[idx+1]<maxVal:
                maxVal=nums[idx]+nums[idx+1]
                minIdx=idx
            
        nums[minIdx]=maxVal
        return self.shiftLeft(nums,minIdx+1)
    
    def shiftLeft(self,nums: List[int], idx:int):
        length=len(nums)
        while idx<length-1:
            nums[idx]=nums[idx+1]
            idx+=1
        nums.pop()
        return nums

    def minimumPairRemoval(self, nums: List[int]) -> int:
        result=0
        while not self.isSorted(nums):
            nums=self.sumMinimum(nums)
            result+=1
        
        return result




        
