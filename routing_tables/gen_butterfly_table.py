#!/usr/bin/python

import numpy as np
import sys

if __name__ == "__main__":
    if (len(sys.argv) != 4):
        print("Usage (k-ary n-fly Butterfly): " + sys.argv[0] + " <K> <N> <file_prefix>")
        sys.exit(1)

    K = int(sys.argv[1])
    N = int(sys.argv[2])
    table_prefix = sys.argv[3]

    # Create folder if it doesn't exist
    import os
    if not os.path.exists(table_prefix):
        os.makedirs(table_prefix)

    for stage in range(N):
        for router in range(K **(N - 1)):
            table_file = open("%s/%0d_%0d.hex" % (table_prefix, stage, router), "w")
            for i in range(K ** N):
                dest = (i // (K ** stage)) % K
                table_file.write("%x\n" % (dest))
            table_file.close()
