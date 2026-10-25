class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        indexes={} 

        for index, value in enumerate(nums):
            diff=target-value
            if diff in indexes:
                return [index,indexes[diff]]
            else:
                indexes[value]=index
        return []
