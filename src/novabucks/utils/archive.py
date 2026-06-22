"""
Copyright (C) 2022 Red Hat, Inc. (https://github.com/Commonjava/charon)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

         http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import logging
import os
import tempfile
from zipfile import ZipFile

import requests

logger = logging.getLogger(__name__)


def download_archive(url: str, base_dir=None) -> str:
    """Download the archive from the given URL and save it to base_dir."""
    dir_ = base_dir
    if not dir_ or not os.path.isdir(dir_):
        dir_ = tempfile.mkdtemp()
        logger.info("No base dir specified for holding archive."
                    " Will use a temp dir %s to hold archive",
                    dir_)
    # Used solution here:
    # https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
    local_filename = os.path.join(dir_, url.split('/')[-1])
    # NOTE the stream=True parameter below
    # NOTE(2) timeout=30 parameter to set a 30-second timeout, and prevent indefinite hang.
    with requests.get(url, stream=True, timeout=30, verify=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                # if chunk:
                f.write(chunk)
    return local_filename


def extract_zip_all(zf: ZipFile, target_dir: str):
    """
    Extracts all contents from the given ZipFile to the target directory.

    Args:
        zf (ZipFile): The ZipFile object to extract files from.
        target_dir (str): The directory where all files will be extracted.

    Returns:
        None
    """
    zf.extractall(target_dir)


def extract_zip_with_files(zf: ZipFile, target_dir: str, file_suffix: str, debug=False):
    """
    Extracts files from the provided ZipFile object to the target directory,
    filtering to only include files that end with the specified suffix.

    Args:
        zf (ZipFile): The ZipFile object to extract files from.
        target_dir (str): The directory where filtered files will be extracted.
        file_suffix (str): Only files whose names end with this suffix will be extracted.
        debug (bool, optional): If True, logs the filtered file list for debugging. Defaults to False.

    Returns:
        None
    """
    names = zf.namelist()
    filtered = list(filter(lambda n: n.endswith(file_suffix), names))
    if debug:
        logger.debug("Filtered files list as below with %s", file_suffix)
        for name in filtered:
            logger.debug(name)
    zf.extractall(target_dir, members=filtered)
