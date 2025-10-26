#! /bin/python
"""
This script uses the pytr script (https://github.com/pytr-org/pytr) to download all transaction
documents from Trade Republic via API, creates a CSV for import into Portfolio Performance
and Uploads all of them them into the corresponding folder of your nextcloud instance.
It is configured via a .env file and optional parameters.

Usage: get_tr_docs.py [--help] [--nodl] [--skipdel] [--nocsv] [--noupload]

Author: Andreas Hering, 2025
"""

import argparse
import subprocess
import sys
from nc_py_api import Nextcloud
import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
import shutil
import time

# loading config variables from .env file
load_dotenv()

### Config is read from a seperate .env file
# see .env.example for keys
tr_phone_number = os.getenv("TR_PHONE_NUMBER")
tr_pin = os.getenv("TR_PIN")
tr_days_to_download = os.getenv("TR_DAYS_TO_DOWNLOAD")  # use 0 for all
tr_doc_download_path = os.getenv("TR_DOC_DOWNLOAD_PATH")
nc_auth_user = os.getenv("NC_AUTH_USER")
nc_auth_pass = os.getenv("NC_AUTH_PASS")
nc_tr_document_folder = os.getenv("NC_TR_DOCUMENT_FOLDER")
nc_url = os.getenv("NC_URL")
###

# Add arguments for script control
parser = argparse.ArgumentParser(
    description="Download Trade Republic docs, generate CSV for importing into Portfolio Performance and upload docs to Nextcloud"
)
parser.add_argument(
    "--nodl",
    "--skip-doc-download",
    help="Skip document download from Trade Republic",
    action="store_true",
)
parser.add_argument(
    "--skipdel",
    "--skip-dl-folder-deletion",
    help="Skip deletion of existing local download folder",
    action="store_true",
)
parser.add_argument(
    "--nocsv",
    "--skip-csv-generation",
    help="Skip generation of CSV for import into Portfolio Performance",
    action="store_true",
)
parser.add_argument(
    "--noupload",
    "--skip-nextcloud-upload",
    help="Skip folder creation in and upload of files to Nextcloud.",
    action="store_true",
)
parser.add_argument(
    "--ffc",
    "--force-nc-folder-create",
    help="Force folder creation in Nextcloud.",
    action="store_true",
)
args = parser.parse_args()


# Ensure that local download folder is empty when starting, to only create CSV for relevant files
# and upload needed files with less duplicates.
# (Nextcloud api does not check for existing files and just overwrites existing ones thus we try
# to reduce overhead of already uploaded files)
def remove_existing_dl_folder():
    print("Checking for existing download folder.")
    if os.path.isdir(tr_doc_download_path):
        if len(os.listdir(tr_doc_download_path)) > 0:
            shutil.rmtree(tr_doc_download_path)
            print(f"Deleted existing & not empty doc path: '{tr_doc_download_path}'")
    else:
        print("All good, no folder found. Starting download.")

# On Windows, set shell=True if needed; on Linux, leave it False.
use_shell = sys.platform.startswith('win')

# Download documents from Trade Republic
def download_docs():
    pytr_dl_docs_args = [
        "pytr",
        "dl_docs",
        "-n",
        tr_phone_number,
        "-p",
        tr_pin,
        "--last_days",
        tr_days_to_download,
        tr_doc_download_path,
    ]

    dl_docs = subprocess.Popen(
        pytr_dl_docs_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        text=True,  # Use text mode for input/output
        bufsize=1,  # Line-buffered for reading output line by line
        shell=use_shell,  # Use the shell to execute the command
    )
    
    # Read line from command line input (the code)
    user_code = input("Enter verification code: ")

    # Send the user's code followed by newline to the subprocess stdin
    dl_docs.stdin.write(user_code + "\n")
    dl_docs.stdin.flush()

    # Read and print subprocess output (optional)
    output, error = dl_docs.communicate()
    print(output)
    if error:
        print("Error:", error)

    print("Doc download process exited with return code:", dl_docs.returncode)


# # Create CSV for portfolio performance
def create_pp_csv():
    pp_csv_source_events = os.path.join(tr_doc_download_path, "all_events.json")
    timestr = time.strftime("%Y%m%d")
    pp_csv_name = f"{timestr}_pp_import.csv"
    pp_csv_path = os.path.join(tr_doc_download_path, pp_csv_name)
    pytr_pp_csv_args = [
        "pytr",
        "export_transactions",
        pp_csv_source_events,
        pp_csv_path,
    ]
    pp_csv_gen = subprocess.Popen(
        pytr_pp_csv_args,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,  # Use text mode for input/output
        bufsize=1,  # Line-buffered for reading output line by line
        shell=use_shell,  # Use the shell to execute the command
    )
    # wait for popen to complete and write the data (asynchronous execution).
    # Also save returned info into variables for eventual debug.
    stdout, stderr = pp_csv_gen.communicate()
    print("CSV generation process exited with return code:", pp_csv_gen.returncode)


# create nextcloud connection for folder creation and file upload
def create_nextcloud_connection():
    nc_connection = Nextcloud(
        nextcloud_url=nc_url, nc_auth_user=nc_auth_user, nc_auth_pass=nc_auth_pass
    )
    return nc_connection


# Get all subfolders(recursive) of tr_docs_download_path to create them in nextcloud
# TODO: also check if subfolders need to be created even if main folder already exists
def create_nextcloud_folders():
    nc = create_nextcloud_connection()
    
    # Get document folder for tr downloads in nextcloud (Does take while under Linux if nested deeply)
    search_result = nc.files.find(["eq", "name", os.path.basename(nc_tr_document_folder)])

    if not search_result or args.ffc:
        if nc_tr_document_folder not in search_result:
            print(f"Creating upload target folders in '{nc_tr_document_folder}'")
            directories = [
                x for x in Path(tr_doc_download_path).rglob("*") if x.is_dir()
            ]
            for directory in directories:
                subdirs = directory.parts[1:]
                nc_subdir_path = os.path.join(nc_tr_document_folder, "/".join(subdirs)).replace("\\","/")
                print(f"Creating dir: {'/'.join(subdirs)}")
                nc.files.makedirs(nc_subdir_path, exist_ok=True)

            print("Folder creation successful!") 
    
    else:
        print("Skip folder creation! Already existing!")
    

# Upload files into corresponding folders
def upload_docs_to_nextcloud():
    nc = create_nextcloud_connection()

    print(f"Uploading files and folders from '{tr_doc_download_path}' to '{nc_tr_document_folder}")
    for root, dirs, files in os.walk(tr_doc_download_path):
        for file_name in files:
            local_file_path = os.path.join(root, file_name)
            # Construct the relative path for remote upload preserving folder structure
            relative_path = os.path.relpath(local_file_path, tr_doc_download_path)
            remote_file_path = os.path.join(
                nc_tr_document_folder, relative_path
            ).replace("\\", "/")

            with open(local_file_path, "rb") as f:
                print(f"Uploading file {'/'.join(Path(remote_file_path).parts[4:])}")
                nc.files.upload_stream(remote_file_path, f)

    print("Upload to nextcloud successful!")


# bring it all together and do some work
if not args.skipdel:
    remove_existing_dl_folder()

if not args.nodl:
    download_docs()

if not args.nocsv and (not args.nodl or not args.skipdel):
    create_pp_csv()

if not args.noupload:
    create_nextcloud_folders()
    upload_docs_to_nextcloud()
