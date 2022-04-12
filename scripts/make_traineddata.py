#!/bin/env python3
# Please run this script on Unix-like platforms.
from glob import glob
import os, sys
from tempfile import mkdtemp


def load_file(file):
    with open(file) as fi:
        for line in fi:
            _, value = line.split(':', 2)
            yield value

def main():
    if len(sys.argv) < 3:
        print("Usage: ./make_traineddata.py path_to/base.traineddata path_to/locale_dir [output=tessdata/]", file=sys.stderr)
        exit(1)
    if os.system("combine_tessdata --version") != 0:
        print("`combine_tessdata` not found! (`tesseract-tools` should be installed)", file=sys.stderr)
        exit(1)
    base_file, locale_dir = sys.argv[1:3]
    output = "tessdata/"
    if len(sys.argv) == 4:
        output = sys.argv[3]
    output = os.path.abspath(output)
    tmpdir = mkdtemp()
    os.chdir(tmpdir)
    print("Generating word list...")
    with open("wordlist", "w") as fo:
        for file in glob(os.path.join(locale_dir, "*.yaml")):
            fo.writelines(load_file(file))
    print("Extracting base data...")
    os.system(f"cp {base_file} .")
    base_file = os.path.basename(base_file)
    os.system(f"combine_tessdata -u {base_file} new_data")
    for file in glob("*-dawg"):
        os.unlink(file)
    print("Wordlist to dawg...")
    os.system(f"wordlist2dawg wordlist new_data.lstm-word-dawg new_data.lstm-unicharset")
    os.system(f"mv {base_file} new_data.traineddata")
    print("Combining data...")
    os.system(f"combine_tessdata new_data.")
    if not os.path.exists(output):
        os.makedirs(output)
    os.system(f"mv new_data.traineddata {output}/{base_file}")
    os.system(f"rm -r {tmpdir}")
    print(f"Generated at {output}/{base_file}")


if __name__ == "__main__":
    main()
