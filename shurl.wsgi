import sys
import os

ENVNAME = "ENV"  # change it with whatever your virtual environment's name is

curr = os.path.dirname(os.path.realpath(__file__))
envpath = os.path.join(curr, ENVNAME, "lib", "python2.7", "site-packages")
print envpath
sys.path.append(curr)
sys.path.append(envpath)

from shurl import app as application