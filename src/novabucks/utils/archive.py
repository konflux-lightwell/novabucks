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
from zipfile import ZipFile

logger = logging.getLogger(__name__)


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
