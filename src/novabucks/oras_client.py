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
from typing import List

import oras.client

logger = logging.getLogger(__name__)


class OrasClient:
    """
    Wrapper for oras-py's OrasClient, deciding whether to login based on config.
    """

    def __init__(self, registry_auth_config_path=None):
        self.registry_auth_config_path = registry_auth_config_path
        self.client = oras.client.OrasClient()

    def pull(self, result_reference_url: str, sign_result_loc: str) -> List[str]:
        """
        Call oras-py's pull method to pull the remote file to local.
        Args:
            result_reference_url (str):
                Reference of the remote file (e.g. "quay.io/repository/signing/radas@hash").
            sign_result_loc (str):
                Local save path (e.g. "/tmp/sign").
        """
        files = []
        try:
            pull_kwargs = {"target": result_reference_url, "outdir": sign_result_loc}
            if self.registry_auth_config_path:
                pull_kwargs["config_path"] = self.registry_auth_config_path
            files = self.client.pull(**pull_kwargs)
            logger.info("Pull file from %s to %s", result_reference_url, sign_result_loc)
        except Exception as e:
            logger.error("Failed to pull file from %s to %s: %s", result_reference_url, sign_result_loc, e)
        return files
