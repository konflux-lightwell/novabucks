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
import re
import sys
from datetime import datetime
from shutil import copy2, rmtree
from tempfile import mkdtemp
from typing import Dict, List, Tuple, Union
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree
from jinja2 import Template

from novabucks.constants import (
    ARCHETYPE_CATALOG_FILENAME,
    ARCHETYPE_CATALOG_TEMPLATE,
    MAVEN_METADATA_TEMPLATE,
    META_FILE_DEL_KEY,
    META_FILE_FAILED,
    META_FILE_GEN_KEY,
)
from novabucks.utils.archive import extract_zip_all
from novabucks.utils.storage import HashType, digest, overwrite_file
from novabucks.utils.strings import remove_prefix

logger = logging.getLogger(__name__)


META_TEMPLATE = MAVEN_METADATA_TEMPLATE
ARCH_TEMPLATE = ARCHETYPE_CATALOG_TEMPLATE
MAVEN_METADATA_FILE = "maven-metadata.xml"
MAVEN_ARCH_FILE = "archetype-catalog.xml"
STANDARD_GENERATED_IGNORES = [MAVEN_METADATA_FILE, MAVEN_ARCH_FILE]


class VersionCompareKey:
    'Used as key function for version sorting'

    def __init__(self, obj: str):
        self.obj = obj

    def __lt__(self, other):
        return self.__compare(other) < 0

    def __gt__(self, other):
        return self.__compare(other) > 0

    def __le__(self, other):
        return self.__compare(other) <= 0

    def __ge__(self, other):
        return self.__compare(other) >= 0

    def __eq__(self, other):
        return self.__compare(other) == 0

    def __hash__(self) -> int:
        return self.obj.__hash__()

    def __compare(self, other) -> int:
        xitems = self.obj.split(".")
        if "-" in xitems[-1]:
            xitems = xitems[:-1] + xitems[-1].split("-")
        yitems = other.obj.split(".")
        if "-" in yitems[-1]:
            yitems = yitems[:-1] + yitems[-1].split("-")
        big = max(len(xitems), len(yitems))
        for i in range(big):
            try:
                xitem: Union[str, int] = xitems[i]
            except IndexError:
                return -1
            try:
                yitem: Union[str, int] = yitems[i]
            except IndexError:
                return 1
            if isinstance(xitem, str) and isinstance(yitem, str) and xitem.isnumeric() and yitem.isnumeric():
                xitem = int(xitem)
                yitem = int(yitem)
            elif isinstance(xitem, str) and xitem.isnumeric() and (not isinstance(yitem, str) or not yitem.isnumeric()):
                return 1
            elif isinstance(yitem, str) and yitem.isnumeric() and (not isinstance(xitem, str) or not xitem.isnumeric()):
                return -1
            # At this point, both are the same type (both int or both str)
            if isinstance(xitem, int) and isinstance(yitem, int):
                if xitem > yitem:
                    return 1
                elif xitem < yitem:
                    return -1
            elif isinstance(xitem, str) and isinstance(yitem, str):
                if xitem > yitem:
                    return 1
                elif xitem < yitem:
                    return -1
            else:
                continue
        return 0


class MavenMetadata(object):
    """This MavenMetadata will represent a maven-metadata.xml data content which will be
    used in jinja2 or other places
    """

    def __init__(self, group_id: str, artifact_id: str, versions: List[str]):
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.last_upd_time = datetime.now().strftime("%Y%m%d%H%M%S")
        self.versions = sorted(set(versions), key=VersionCompareKey)
        self._latest_version = None
        self._release_version = None

    def generate_meta_file_content(self) -> str:
        template = Template(META_TEMPLATE)
        return template.render(meta=self)

    @property
    def latest_version(self):
        if self._latest_version:
            return self._latest_version
        self._latest_version = self.versions[-1]
        return self._latest_version

    @property
    def release_version(self):
        if self._release_version:
            return self._release_version
        self._release_version = self.versions[-1]
        return self._release_version

    def __str__(self) -> str:
        return f"{self.group_id}:{self.artifact_id}\n{self.versions}\n\n"


class ArchetypeRef(object):
    """This ArchetypeRef will represent an entry in archetype-catalog.xml content which will be
    used in jinja2 or other places
    """

    def __init__(self, group_id: str, artifact_id: str, version: str, description: str):
        self.group_id = group_id
        self.artifact_id = artifact_id
        self.version = version
        self.description = description

    def __hash__(self):
        return hash(self.group_id + self.artifact_id + self.version)

    def __eq__(self, other) -> bool:
        if isinstance(other, ArchetypeRef):
            return (
                self.group_id == other.group_id
                and self.artifact_id == other.artifact_id
                and self.version == other.version
            )

        return False

    def __str__(self) -> str:
        return f"{self.group_id}:{self.artifact_id}\n{self.version}\n{self.description}\n\n"


class ArchetypeCompareKey:
    def __init__(self, gav: ArchetypeRef):
        self.gav = gav

    def __lt__(self, other):
        return self.__compare(other) < 0

    def __gt__(self, other):
        return self.__compare(other) > 0

    def __le__(self, other):
        return self.__compare(other) <= 0

    def __ge__(self, other):
        return self.__compare(other) >= 0

    def __eq__(self, other):
        return self.__compare(other) == 0

    def __hash__(self):
        return self.gav.__hash__()

    def __compare(self, other) -> int:
        x = self.gav.group_id + ":" + self.gav.artifact_id
        y = other.gav.group_id + ":" + other.gav.artifact_id

        if x == y:
            return 0
        elif x < y:
            return -1
        else:
            return 1


class MavenArchetypeCatalog(object):
    """This MavenArchetypeCatalog represents an archetype-catalog.xml which will be
    used in jinja2 to regenerate the file with merged contents
    """

    def __init__(self, archetypes: List[ArchetypeRef]):
        self.archetypes = sorted(set(archetypes), key=ArchetypeCompareKey)

    def generate_meta_file_content(self) -> str:
        template = Template(ARCHETYPE_CATALOG_TEMPLATE)
        return template.render(archetypes=self.archetypes)

    def __str__(self) -> str:
        return f"(Archetype Catalog with {len(self.archetypes)} entries).\n\n"


def _parse_archetypes(source) -> List[ArchetypeRef]:
    tree = ElementTree.fromstring(source.strip(), forbid_dtd=True, forbid_entities=True, forbid_external=True)

    archetypes = []
    for a in tree.findall("./archetypes/archetype"):
        gid = a.find('groupId').text
        aid = a.find('artifactId').text
        ver = a.find('version').text
        desc = a.find('description').text
        archetypes.append(ArchetypeRef(gid, aid, ver, desc))

    return archetypes


def _handle_archetype_catalog_merge(src_catalog: str, dest_catalog: str):
    """
    Handle merging of archetype-catalog.xml files during directory merge.

    Args:
        src_catalog: Source archetype-catalog.xml file path
        dest_catalog: Destination archetype-catalog.xml file path
    """
    try:
        with open(src_catalog, "rb") as sf:
            src_archetypes = _parse_archetypes(sf.read())
    except ElementTree.ParseError as e:
        logger.warning("Failed to read source archetype catalog %s: %s", src_catalog, e)
        return

    if len(src_archetypes) < 1:
        logger.warning(
            "No archetypes found in source archetype-catalog.xml: %s, " "even though the file exists! Skipping.",
            src_catalog,
        )
        return

    # Copy directly if dest_catalog doesn't exist
    if not os.path.exists(dest_catalog):
        copy2(src_catalog, dest_catalog)
        return

    try:
        with open(dest_catalog, "rb") as df:
            dest_archetypes = _parse_archetypes(df.read())
    except ElementTree.ParseError as e:
        logger.warning("Failed to read dest archetype catalog %s: %s", dest_catalog, e)
        return

    if len(dest_archetypes) < 1:
        logger.warning(
            "No archetypes found in dest archetype-catalog.xml: %s, "
            "even though the file exists! Copy directly from the src_catalog, %s.",
            dest_catalog,
            src_catalog,
        )
        copy2(src_catalog, dest_catalog)
        return

    else:
        original_dest_size = len(dest_archetypes)
        for sa in src_archetypes:
            if sa not in dest_archetypes:
                dest_archetypes.append(sa)
            else:
                logger.debug("DUPLICATE ARCHETYPE: %s", sa)

        if len(dest_archetypes) != original_dest_size:
            content = MavenArchetypeCatalog(dest_archetypes).generate_meta_file_content()
            try:
                overwrite_file(dest_catalog, content)
            except Exception as e:
                logger.error("Failed to merge archetype catalog: %s", dest_catalog)
                raise e


def _merge_directories_with_rename(src_dir: str, dest_dir: str, root: str):
    """Recursively copy files from src_dir to dest_dir, overwriting existing files.
    * src_dir is the source directory to copy from
    * dest_dir is the destination directory to copy to.

    Returns Tuple of (copied_count, duplicated_count, merged_count, processed_count)
    """
    copied_count = 0
    duplicated_count = 0
    merged_count = 0
    processed_count = 0

    # Find the actual content directory
    content_root = src_dir
    for item in os.listdir(src_dir):
        item_path = os.path.join(src_dir, item)
        # Check the root maven-repository subdirectory existence
        maven_repo_path = os.path.join(item_path, root)
        if os.path.isdir(item_path) and os.path.exists(maven_repo_path):
            content_root = item_path
            break

    # pylint: disable=unused-variable
    for root_dir, dirs, files in os.walk(content_root):
        # Calculate relative path from content root
        rel_path = os.path.relpath(root_dir, content_root)
        dest_root = os.path.join(dest_dir, rel_path) if rel_path != '.' else dest_dir

        # Create destination directory if it doesn't exist
        os.makedirs(dest_root, exist_ok=True)

        # Copy all files, skip existing ones
        for file in files:
            src_file = os.path.join(root_dir, file)
            dest_file = os.path.join(dest_root, file)

            if file == ARCHETYPE_CATALOG_FILENAME:
                _handle_archetype_catalog_merge(src_file, dest_file)
                merged_count += 1
                logger.debug("Merged archetype catalog: %s -> %s", src_file, dest_file)
            elif os.path.exists(dest_file):
                duplicated_count += 1
                logger.debug("Duplicated: %s, skipped", dest_file)
            else:
                copy2(src_file, dest_file)
                copied_count += 1
                logger.debug("Copied: %s -> %s", src_file, dest_file)

            processed_count += 1

    logger.info(
        "One zip merged! Files copied: %s, Files duplicated: %s, " "Files merged: %s, Total files processed: %s",
        copied_count,
        duplicated_count,
        merged_count,
        processed_count,
    )
    return copied_count, duplicated_count, merged_count, processed_count


def extract_zip_files(repos: List[str], root: str, prefix="", dir__=None) -> str:
    """Extract multiple zip archives to a temporary directory.
    * repos are the list of repo paths to extract
    * root is a prefix in the tarball to identify which path is
      the beginning of the maven GAV path
    * prefix is the prefix for temporary directory name
    * dir__ is the directory where temporary directories will be created.

    Returns the path to the merged temporary directory containing all extracted files
    """
    # Create final merge directory
    final_tmp_root = mkdtemp(prefix=f"novabucks-{prefix}-final-", dir=dir__)

    if len(repos) == 1:
        if os.path.exists(repos[0]):
            try:
                logger.info("Extracting the single ZIP file %s", repos[0])
                repo_zip = ZipFile(repos[0])
                extract_zip_all(repo_zip, final_tmp_root)

            except BadZipFile as e:
                logger.error("ZIP file extraction error for repo %s: %s", repos[0], e)
                sys.exit(1)
        else:
            logger.error("Error: archive %s does not exist", repos[0])
            sys.exit(1)
        return final_tmp_root

    total_copied = 0
    total_duplicated = 0
    total_merged = 0
    total_processed = 0

    # Collect all extracted directories first
    extracted_dirs = []

    for repo in repos:
        if os.path.exists(repo):
            try:
                logger.info("Extracting the ZIP file %s", repo)
                repo_zip = ZipFile(repo)
                tmp_root = mkdtemp(prefix=f"novabucks-{prefix}-", dir=dir__)
                extract_zip_all(repo_zip, tmp_root)
                extracted_dirs.append(tmp_root)

            except BadZipFile as e:
                logger.error("ZIP file extraction error for repo %s: %s", repo, e)
                sys.exit(1)
        else:
            logger.error("Error: archive %s does not exist", repo)
            sys.exit(1)

    # Merge all extracted directories
    if extracted_dirs:
        # Create merged directory name
        merged_dir_name = "merged_repositories"
        merged_dest_dir = os.path.join(final_tmp_root, merged_dir_name)

        # Merge content from all extracted directories
        for extracted_dir in extracted_dirs:
            copied, duplicated, merged, processed = _merge_directories_with_rename(extracted_dir, merged_dest_dir, root)
            total_copied += copied
            total_duplicated += duplicated
            total_merged += merged
            total_processed += processed

            # Clean up temporary extraction directory
            rmtree(extracted_dir)

    logger.info(
        "All zips merged! Total copied: %s, Total duplicated: %s, " "Total merged: %s, Total processed: %s",
        total_copied,
        total_duplicated,
        total_merged,
        total_processed,
    )
    return final_tmp_root


def _is_ignored(filename: str, ignore_patterns: List[str]) -> bool:
    for ignored_name in STANDARD_GENERATED_IGNORES:
        if filename and filename.startswith(ignored_name.strip()):
            logger.info("Ignoring standard generated Maven path: %s", filename)
            return True

    if ignore_patterns:
        for dirs in ignore_patterns:
            if re.match(dirs, filename):
                return True
    return False


def scan_maven_paths(
    files_root: str, ignore_patterns: List[str], root: str
) -> Tuple[str, List[str], List[str], List[str]]:
    # 2. scan for paths and filter out the ignored paths,
    # and also collect poms for later metadata generation
    logger.info("Scan %s to collect files", files_root)
    top_level = root
    valid_mvn_paths, non_mvn_paths, ignored_paths, valid_poms, valid_dirs = [], [], [], [], []
    changed_dirs = set()
    top_found = False
    for root_dir, dirs, names in os.walk(files_root):
        for directory in dirs:
            changed_dirs.add(os.path.join(root_dir, directory))
            if not top_found:
                if directory == top_level:
                    top_level = os.path.join(root_dir, directory)
                    top_found = True
                if os.path.join(root_dir, directory) == os.path.join(files_root, top_level):
                    top_level = os.path.join(files_root, top_level)
                    top_found = True

        for name in names:
            path = os.path.join(root_dir, name)
            if top_level in root_dir:
                # Let's wait to do the regex / pom examination until we
                # know we're inside a valid root directory.
                if _is_ignored(name, ignore_patterns):
                    ignored_paths.append(path)
                    continue

                valid_mvn_paths.append(path)

                if name.strip().endswith(".pom"):
                    valid_poms.append(path)
            else:
                non_mvn_paths.append(path)

    if len(non_mvn_paths) > 0:
        non_mvn_items = [n.replace(files_root, "") for n in non_mvn_paths]
        logger.info(
            "These files are not in the specified " "root dir %s, so will be ignored: \n%s", root, non_mvn_items
        )
    if not top_found or top_level.strip() == "" or top_level.strip() == "/":
        logger.warning(
            "Warning: the root path %s does not exist in tarball," " will use empty trailing prefix for the uploading",
            top_level,
        )
        top_level = files_root
    else:
        for c in changed_dirs:
            if c.startswith(top_level):
                valid_dirs.append(c)
    logger.info("Files scanning done.\n")

    if ignore_patterns and len(ignore_patterns) > 0:
        logger.info("Ignored paths with ignore_patterns %s as below:\n%s\n", ignore_patterns, "\n".join(ignored_paths))

    return (top_level, valid_mvn_paths, valid_poms, valid_dirs)


def __parse_gav(full_artifact_path: str, root="/") -> Tuple[str, str, str]:
    """Parse maven groupId, artifactId and version from a standard path in a local maven repo.
    e.g: org/apache/maven/plugin/maven-plugin-plugin/1.0.0/maven-plugin-plugin-1.0.0.pom
    -> (org.apache.maven.plugin, maven-plugin-plugin, 1.0.0)
    root is like a prefix of the path which is not part of the maven GAV
    """
    slash_root = root
    if not root.endswith("/"):
        slash_root = slash_root + "/"

    ver_path = full_artifact_path
    if ver_path.startswith(slash_root):
        ver_path = ver_path[len(slash_root) :]
    if ver_path.endswith("/"):
        ver_path = ver_path[:-1]

    items = ver_path.split("/")
    version = items[-2]
    artifact = items[-3]
    group = ".".join(items[:-3])

    return group, artifact, version


def parse_gavs(pom_paths: List[str], root="/") -> Dict[str, Dict[str, List[str]]]:
    """Give a list of paths with pom files and parse the maven groupId, artifactId and version
    from them. The result will be a dict like {groupId: {artifactId: [versions list]}}.
    Root is like a prefix of the path which is not part of the maven GAV
    """
    gavs: Dict[str, Dict] = dict()
    for pom in pom_paths:
        g, a, v = __parse_gav(pom, root)
        avs = gavs.get(g, dict())
        vers = avs.get(a, list())
        vers.append(v)
        avs[a] = vers
        gavs[g] = avs
    return gavs


def hash_decorate_metadata(path: str, metadata: str) -> List[str]:
    return [os.path.join(path, metadata + hash) for hash in [".md5", ".sha1", ".sha256"]]


def __gen_digest_file(hash_file_path, meta_file_path: str, hashtype: HashType) -> bool:
    try:
        overwrite_file(hash_file_path, digest(meta_file_path, hashtype))
    except FileNotFoundError:
        logger.warning(
            "Error: Can not create digest file %s for %s " "because of some missing folders",
            hash_file_path,
            meta_file_path,
        )
        return False
    return True


def __gen_all_digest_files(meta_file_path: str) -> List[str]:
    md5_path = meta_file_path + ".md5"
    sha1_path = meta_file_path + ".sha1"
    sha256_path = meta_file_path + ".sha256"
    digest_files = []
    if __gen_digest_file(md5_path, meta_file_path, HashType.MD5):
        digest_files.append(md5_path)
    if __gen_digest_file(sha1_path, meta_file_path, HashType.SHA1):
        digest_files.append(sha1_path)
    if __gen_digest_file(sha256_path, meta_file_path, HashType.SHA256):
        digest_files.append(sha256_path)
    return digest_files


def gen_meta_file(group_id, artifact_id: str, versions: list, root="/", do_digest=True) -> List[str]:
    content = MavenMetadata(group_id, artifact_id, versions).generate_meta_file_content()
    g_path = "/".join(group_id.split("."))
    meta_files = []
    final_meta_path = os.path.join(root, g_path, artifact_id, MAVEN_METADATA_FILE)
    try:
        overwrite_file(final_meta_path, content)
        meta_files.append(final_meta_path)
    except FileNotFoundError as e:
        raise e
    if do_digest:
        meta_files.extend(__gen_all_digest_files(final_meta_path))
    return meta_files


def generate_metadatas(poms: List[str], root: str, destination_dir: str, prefix: str = None) -> Dict[str, List[str]]:
    """Collect GAVs and generate maven-metadata.xml files.
    Instead of operating on S3, put results in `destination_dir` filesystem dir.
    Workflow:
    * Scan and get the GA for the poms
    * For each GA, find relevant pom files under destination_dir (mirroring S3's search)
    * Use these poms to generate maven-metadata.xml
    """
    ga_dict: Dict[str, bool] = {}
    logger.debug("Valid poms: %s", poms)
    valid_gavs_dict = parse_gavs(poms, root)
    for g, avs in valid_gavs_dict.items():
        for a in avs.keys():
            logger.debug("G: %s, A: %s", g, a)
            g_path = "/".join(g.split("."))
            ga_dict[os.path.join(g_path, a)] = True

    # Note: we don't need to add original poms, because they are already present in the local destination_dir.
    all_poms: List[str] = []
    meta_files: Dict[str, List[str]] = {}

    for path, _ in ga_dict.items():
        ga_prefix = path
        if prefix:
            ga_prefix = os.path.join(prefix, path)
        if not ga_prefix.endswith("/"):
            ga_prefix = ga_prefix + "/"
        # Build the absolute path to the search area
        search_dir = os.path.join(destination_dir, ga_prefix)
        existed_poms = []
        # Gather all .pom files in search_dir
        if os.path.exists(search_dir) and os.path.isdir(search_dir):
            for rootdir, _, files in os.walk(search_dir):
                for file in files:
                    if file.endswith(".pom"):
                        rel_path = os.path.relpath(os.path.join(rootdir, file), destination_dir)
                        existed_poms.append(rel_path.replace("\\", "/"))
            success = True
        else:
            success = False

        if len(existed_poms) == 0:
            if success:
                logger.debug("No poms found in destination_dir %s for GA path %s", destination_dir, path)
                meta_files_deletion = meta_files.get(META_FILE_DEL_KEY, [])
                meta_files_deletion.append(os.path.join(path, MAVEN_METADATA_FILE))
                meta_files_deletion.extend(hash_decorate_metadata(path, MAVEN_METADATA_FILE))
                meta_files[META_FILE_DEL_KEY] = meta_files_deletion
            else:
                logger.warning("An error happened when scanning artifacts under GA path %s", path)
                meta_failed_path = meta_files.get(META_FILE_FAILED, [])
                meta_failed_path.append(os.path.join(path, MAVEN_METADATA_FILE))
                meta_failed_path.extend(hash_decorate_metadata(path, MAVEN_METADATA_FILE))
                meta_files[META_FILE_FAILED] = meta_failed_path
        else:
            logger.debug("Got poms in destination_dir %s for GA path %s: %s", destination_dir, path, existed_poms)
            un_prefixed_poms = existed_poms
            if prefix:
                if not prefix.endswith("/"):
                    un_prefixed_poms = [remove_prefix(pom, prefix) for pom in existed_poms]
                else:
                    un_prefixed_poms = [remove_prefix(pom, prefix + "/") for pom in existed_poms]
            all_poms.extend(un_prefixed_poms)

    gav_dict = parse_gavs(all_poms)
    if len(gav_dict) > 0:
        meta_files_generation = []
        for g, avs in gav_dict.items():
            for a, vers in avs.items():
                try:
                    metas = gen_meta_file(g, a, vers, destination_dir)
                    meta_files_generation.extend(metas)
                except FileNotFoundError:
                    logger.warning(
                        "Failed to create or update metadata file for GA"
                        " %s, please check if aligned Maven GA"
                        " is correct in your set of files.",
                        f'{g}:{a}',
                    )
                logger.debug("Generated metadata file %s for %s:%s", meta_files_generation, g, a)
        meta_files[META_FILE_GEN_KEY] = meta_files_generation
    return meta_files


def generate_archetype_catalog(root: str, destination_dir: str, prefix: str = None) -> bool:
    """
    Determine whether the local archive contains /archetype-catalog.xml
    in the repo contents.

    If so, determine whether the archetype-catalog.xml is already
    available in the destination_dir. Merge (or unmerge) these catalogs and
    return a boolean indicating whether the local file should be updated/uploaded.
    """
    # Determine the path for the archetype catalog in destination_dir
    remote = ARCHETYPE_CATALOG_FILENAME
    if prefix:
        remote = os.path.join(prefix, ARCHETYPE_CATALOG_FILENAME)
    local = os.path.join(root, ARCHETYPE_CATALOG_FILENAME)
    # As the local archetype will be overwritten later, we must keep
    # a cache of the original local for multi-targets support
    local_bak = os.path.join(root, ARCHETYPE_CATALOG_FILENAME + ".novabucks.bak")
    if os.path.exists(local) and not os.path.exists(local_bak):
        with open(local, "rb") as f:
            with open(local_bak, "w+", encoding="utf-8") as fl:
                fl.write(str(f.read(), encoding="utf-8"))

    # If there is no local catalog, this is a NO-OP
    if os.path.exists(local_bak):
        remote_path = os.path.join(destination_dir, remote)
        existed = os.path.exists(remote_path)
        if not existed:
            __gen_all_digest_files(local)
            # If there is no catalog in the destination_dir, just use what we have locally
            return True
        else:
            # If there IS a catalog in the destination_dir, we need to merge or un-merge it.
            with open(local, "rb") as f:
                try:
                    local_archetypes = _parse_archetypes(f.read())
                except ElementTree.ParseError:
                    logger.warning(
                        "Failed to parse archetype-catalog.xml from local archive with root: %s. "
                        "SKIPPING invalid archetype processing.",
                        root,
                    )
                    return False

            if len(local_archetypes) < 1:
                logger.warning(
                    "No archetypes found in local archetype-catalog.xml, " "even though the file exists! Skipping."
                )
            else:
                # Read the archetypes from the destination_dir so we can do a merge / un-merge
                try:
                    with open(remote_path, "rb") as rf:
                        remote_xml = rf.read()
                except FileNotFoundError:
                    remote_xml = b""
                try:
                    remote_archetypes = _parse_archetypes(remote_xml)
                except ElementTree.ParseError:
                    logger.warning(
                        "Failed to parse archetype-catalog.xml from destination_dir: %s. "
                        "OVERWRITING destination_dir archetype-catalog.xml with the valid, local copy.",
                        destination_dir,
                    )
                    return True

                if len(remote_archetypes) < 1:
                    __gen_all_digest_files(local)
                    # Nothing in the destination_dir. Just push what we have locally.
                    return True
                else:
                    original_remote_size = len(remote_archetypes)
                    for la in local_archetypes:
                        # The cautious approach in this operation contradicts
                        # assumptions we make for the rollback case.
                        # That's because we should NEVER encounter a collision
                        # on archetype GAV...they should belong with specific
                        # product releases.
                        #
                        # Still, we will WARN, not ERROR if we encounter this.
                        if la not in remote_archetypes:
                            remote_archetypes.append(la)
                        else:
                            logger.warning(
                                "\n\n\nDUPLICATE ARCHETYPE: %s. "
                                "This makes rollback of the current release UNSAFE!\n\n\n",
                                la,
                            )

                    if len(remote_archetypes) != original_remote_size:
                        # If the number of archetypes in the version of
                        # the file from the destination_dir has changed, we need
                        # to regenerate the file and re-upload it.
                        #
                        # Re-render the result of our archetype merge /
                        # un-merge to the local file, in preparation for
                        # update.
                        content = MavenArchetypeCatalog(remote_archetypes).generate_meta_file_content()
                        try:
                            overwrite_file(local, content)
                        except FileNotFoundError as e:
                            logger.error(
                                "Error: Can not create file %s because of some missing folders",
                                local,
                            )
                            raise e
                        __gen_all_digest_files(local)
                        return True

    return False
