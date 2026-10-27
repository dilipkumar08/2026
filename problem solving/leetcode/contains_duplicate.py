class Solution:
    def containsDuplicate(self, nums: list[int]) -> bool:
        record = dict()
        for num in nums:
            record[num] = record.get(num,0)+1
            if record[num]==2:
                return True
        
        return False
