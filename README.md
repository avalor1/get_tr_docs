I created this script to support my monthly workflow of tracking my passive income sources with Portfolio Performance.

This script uses the pytr script (https://github.com/pytr-org/pytr) to download all transaction 
documents from Trade Republic via API, creates a CSV for import into Portfolio Performance 
and Uploads all of them them into the corresponding folder of your nextcloud instance.
It is configured via a .env file and optional parameters.

Usage:
```bash
get_tr_docs.py [--help] [--nodl] [--skipdel] [--nocsv] [--noupload] [--ffc]
```