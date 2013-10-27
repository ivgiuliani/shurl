import sys
import os

curr = os.path.realpath(__file__)
sys.path.append(os.path.join(curr, "ENV", "lib", "python2.7", "site-packages"))

import shurl