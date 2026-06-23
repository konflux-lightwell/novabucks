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

import os
import shutil
import tempfile
import unittest
from zipfile import ZipFile

from novabucks.maven import extract_zip_files


class ExtractZipFilesTest(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.__test_dir = tempfile.mkdtemp()
        self.__root = "maven-repository"
        self.__created_dirs = []

        self.__dir_repo = self._make_dir_repo("maven-repository/foo/bar/1.0", "foo-bar-1.0.jar")
        self.__dir_repo2 = self._make_dir_repo("maven-repository/baz/qux/2.0", "baz-qux-2.0.jar")
        self.__zip_repo = self._make_zip_repo("repo1.zip", "maven-repository/foo/bar/1.0", "foo-bar-1.0.jar")
        self.__zip_repo2 = self._make_zip_repo("repo2.zip", "maven-repository/baz/qux/2.0", "baz-qux-2.0.jar")

    def tearDown(self):
        super().tearDown()
        for d in self.__created_dirs:
            if os.path.exists(d):
                shutil.rmtree(d)
        if os.path.exists(self.__test_dir):
            shutil.rmtree(self.__test_dir)

    def _make_dir_repo(self, gav_path, filename):
        repo_dir = tempfile.mkdtemp(dir=self.__test_dir)
        artifact_dir = os.path.join(repo_dir, gav_path)
        os.makedirs(artifact_dir)
        with open(os.path.join(artifact_dir, filename), "w") as f:
            f.write("dummy")
        return repo_dir

    def _make_zip_repo(self, zip_name, gav_path, filename):
        zip_path = os.path.join(self.__test_dir, zip_name)
        with ZipFile(zip_path, "w") as zf:
            zf.writestr(f"{gav_path}/{filename}", "dummy")
        return zip_path

    def _track(self, path):
        self.__created_dirs.append(path)
        return path

    def test_single_zip(self):
        result = self._track(extract_zip_files([self.__zip_repo], self.__root, dir__=self.__test_dir))
        self.assertTrue(os.path.isdir(result))
        self.assertTrue(os.path.isfile(os.path.join(result, "maven-repository/foo/bar/1.0/foo-bar-1.0.jar")))

    def test_single_directory(self):
        result = self._track(extract_zip_files([self.__dir_repo], self.__root, dir__=self.__test_dir))
        self.assertTrue(os.path.isdir(result))
        self.assertTrue(os.path.isfile(os.path.join(result, "maven-repository/foo/bar/1.0/foo-bar-1.0.jar")))

    def test_multiple_directories(self):
        result = self._track(extract_zip_files([self.__dir_repo, self.__dir_repo2], self.__root, dir__=self.__test_dir))
        self.assertTrue(os.path.isdir(result))
        merged = os.path.join(result, "merged_repositories")
        self.assertTrue(os.path.isfile(os.path.join(merged, "maven-repository/foo/bar/1.0/foo-bar-1.0.jar")))
        self.assertTrue(os.path.isfile(os.path.join(merged, "maven-repository/baz/qux/2.0/baz-qux-2.0.jar")))

    def test_mixed_zip_and_directory(self):
        result = self._track(extract_zip_files([self.__zip_repo, self.__dir_repo2], self.__root, dir__=self.__test_dir))
        self.assertTrue(os.path.isdir(result))
        merged = os.path.join(result, "merged_repositories")
        self.assertTrue(os.path.isfile(os.path.join(merged, "maven-repository/foo/bar/1.0/foo-bar-1.0.jar")))
        self.assertTrue(os.path.isfile(os.path.join(merged, "maven-repository/baz/qux/2.0/baz-qux-2.0.jar")))

    def test_nonexistent_path(self):
        with self.assertRaises(SystemExit):
            extract_zip_files(["/nonexistent/path.zip"], self.__root, dir__=self.__test_dir)
