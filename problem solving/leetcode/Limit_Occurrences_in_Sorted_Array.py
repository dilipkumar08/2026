class Solution:
    def limitOccurrences(self, nums: list[int], k: int) -> list[int]:
        if k==0:
            return []
        else:
            count={}
            length=len(nums)
            start=0
            while(start<length):
                if count.get(nums[start],False)==False:
                    count[nums[start]]=count.get(nums[start],0)+1
                    start+=1
                elif count[nums[start]]<k:
                    count[nums[start]]+=1
                    start+=1
                else:
                    nums.pop(start)
                    length-=1
            return nums
                
                    
                ©leetcode
