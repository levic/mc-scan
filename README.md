Minecraft Scanner

* `scan.py` scans a region for interesting blocks
    * If a certain region hasn't been generated yet then it will exit with an exception
* `bedrock/libleveldb.so` needs to be symlinked or copied from a build from https://github.com/Mojang/leveldb-mcpe



```
# activate virtualenv
workon mc-scan


# copy the minecraft world into the local dir and run the scanner on that
./go.sh 
```
