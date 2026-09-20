-- brute force
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        length=len(nums)
        for i in range(length):
            for j in range(i+1,length):
                if nums[i]+nums[j]==target:
                    return [i,j]
-- ideal solution
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:

        record={}

        for idx,value in enumerate(nums):
            rem=(target-value) 
            if  rem in record:
                return [idx,record[rem]] 
            record[value]=idx
