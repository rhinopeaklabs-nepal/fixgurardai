# Fixed variants, for the before/after demo

`index.html` here is `testbed/index.html` with the four issues FixGuard
reports actually fixed: the silent form failure, the two console errors, the
missing image, and the dead link.

To reproduce the comparison live:

```bash
# 1. audit the broken page
#    -> 49 / critical

cp testbed/fixed/index.html testbed/index.html   # 2. apply the fixes

# 3. audit the same URL again
#    -> 97 / verified_healthy
# 4. open the comparison: +48, 6 resolved, 0 introduced

git checkout testbed/index.html                  # 5. restore for the next run
```

The comparison endpoint picks the previous audit of the same URL
automatically, so step 4 needs no ids.
