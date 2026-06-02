# Archive discovery

These are instructions for getting a suitable dev environment for archive discovery-related stuff:

Start by running the `scripts/recreate_dirs.py` script. This will recreate a directory structure on your local machine
that mimics the one found on the archive.

The first argument is the text file that contains the directory structure to
recreate - Use the file `scripts/sample-file-tree.txt`.

The second argument is a suitable root directory to where you want to have a sample of the archive.

```shell
uv run python scripts/recreate_dirs.py \
    scripts/sample-file-tree.txt \
    /datadisk/data/naturalgis-ipma-marine-data-catalog/simulated-archive/surveys/owf-seism-2024
```

Now get some sample files from the actual archive and onto your local machine.

!!! warning

    These are very large files!

    The script pulls in tens of GB of data. Ensure you have enough space available.


Run the script in `scripts/quick-get-sample-data.sh`. It expects to be supplied with a root directory,
which should be the simulated archive base:

```shell
bash scripts/quick-get-sample-data.sh /datadisk/data/naturalgis-ipma-marine-data-catalog/simulated-archive
```
