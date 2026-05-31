#!/usr/bin/python

import numpy as np
import sys

if __name__ == "__main__":
    if (len(sys.argv) != 4):
        print("Usage: " + sys.argv[0] + " <num_inputs> <num_outputs> <file_prefix>")
        sys.exit(1)

    num_inputs = int(sys.argv[1])
    num_outputs = int(sys.argv[2])
    table_prefix = sys.argv[3]

    # Create folder if it doesn't exist
    import os
    if not os.path.exists(table_prefix):
        os.makedirs(table_prefix)

    table_file = open("%s/table.hex" % (table_prefix), "w")
    for i in range(num_outputs):
        table_file.write("%x\n" % (i))
    table_file.close()
