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
import sys
from locale import CODESET, nl_langinfo

from novabucks.constants import DEFAULT_ERRORS_LOG, NOVABUCKS_LOGGING_FMT


class EncodedStream(object):
    def __init__(self, fileno, encoding):
        self.binarystream = os.fdopen(os.dup(fileno), 'wb')
        self.encoding = encoding

    def write(self, text):
        if not isinstance(text, bytes):
            self.binarystream.write(text.encode(self.encoding))
        else:
            self.binarystream.write(text)
        self.binarystream.flush()

    def __del__(self):
        try:
            self.binarystream.close()
        except AttributeError:
            pass


def set_logging(
    product, version, name="novabucks",
    level=logging.DEBUG, handler=None, use_log_file=True
):
    logger = logging.getLogger(name)
    for hdlr in list(logger.handlers):
        logger.removeHandler(hdlr)

    logger.setLevel(level)

    formatter = logging.Formatter(fmt=NOVABUCKS_LOGGING_FMT)

    if not handler:
        log_encoding = nl_langinfo(CODESET)
        encoded_stream = EncodedStream(sys.stderr.fileno(), log_encoding)
        handler = logging.StreamHandler(encoded_stream)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)

    logger.addHandler(handler)

    if use_log_file:
        set_log_file_handler(product, version, logger)

    logger = logging.getLogger('novabucks')
    for hdlr in list(logger.handlers):
        hdlr.setFormatter(formatter)


def set_log_file_handler(product, version, logger):
    prd = product.replace(" ", "_")
    ver = version.replace(" ", "_")
    log_loc = os.getenv("ERROR_LOG_LOCATION")
    error_log = "".join([prd, "-", ver, ".", DEFAULT_ERRORS_LOG])
    if log_loc:
        os.makedirs(log_loc, exist_ok=True)
        error_log = os.path.join(log_loc, error_log)
    handler = logging.FileHandler(error_log)
    formatter = logging.Formatter(fmt=NOVABUCKS_LOGGING_FMT)
    handler.setFormatter(formatter)
    handler.setLevel(logging.WARN)
    logger.addHandler(handler)
