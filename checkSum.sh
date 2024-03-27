#! /bin/sh
pwd
find . -type f -exec md5sum {} + | LC_ALL=C sort | md5sum