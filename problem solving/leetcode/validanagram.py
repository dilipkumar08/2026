class Solution:
    def isAnagram(self, s: str, t: str) -> bool:
        if len(s)!=len(t):
            return False

        tmap=dict()
        smap=dict()
        for i in range(len(s)):
            smap[s[i]]=smap.get(s[i],0)+1
            tmap[t[i]]=tmap.get(t[i],0)+1

        for c in smap:
            if smap[c]!=tmap.get(c,0):
                return False
        return True     

# other solutions are Counter(s)==Counter(t)

# sorted(s) == sorted(t)

        
