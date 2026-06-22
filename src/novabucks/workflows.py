import json
import logging
import os
import sys

from novabucks.constants import DEFAULT_RADAS_SIGN_IGNORES, META_FILE_FAILED, META_FILE_GEN_KEY
from novabucks.maven import (
    ARCHETYPE_CATALOG_FILENAME,
    MAVEN_ARCH_FILE,
    extract_zip_files,
    generate_archetype_catalog,
    generate_metadatas,
    hash_decorate_metadata,
    scan_maven_paths,
)
from novabucks.radas_sign import RadasConfig, generate_radas_sign, sign_in_radas
from novabucks.utils.storage import copy_files_to_destination, write_manifest

logger = logging.getLogger(__name__)


def sign_in_radas_workflow(
    repo_url: str, requester: str, sign_key: str, result_path: str,
    ignore_patterns: list[str], radas_config: RadasConfig,
):
    # Load the radas configuration from the JSON file
    conf = json.load(radas_config)
    if not conf:
        logger.error("The novabucks configuration is not valid!")
        sys.exit(1)

    # Create the RadasConfig object
    radas_data = conf.get("radas", {})
    radas_conf = RadasConfig(radas_data)
    if not radas_conf.validate():
        logger.error("The configuration for radas is not valid!")
        sys.exit(1)

    # Create the ignore patterns list
    ig_patterns = list(conf.get("ignore_patterns", []))
    ig_patterns.extend(DEFAULT_RADAS_SIGN_IGNORES)
    if ignore_patterns:
        ig_patterns.extend(ignore_patterns)
    ig_patterns = list(set(ig_patterns))

    # Sign the artifacts in the repository
    sign_in_radas(
        repo_url=repo_url,
        requester=requester,
        sign_key=sign_key,
        result_path=result_path,
        ignore_patterns=ig_patterns,
        radas_config=radas_conf,
    )


def sign_individual_artifacts_workflow(
    repos: list[str], product_key: str, root_path: str,
    ignore_patterns: list[str], work_dir: str, destination_dir: str,
    sign_result_file: str,
):
    # 1. extract the zip files
    tmp_root = extract_zip_files(repos, root_path, product_key, work_dir)

    # 2. scan for paths and filter out the ignored paths,
    # and also collect poms for later metadata generation
    (top_level,
     valid_mvn_paths,
     valid_poms, _) = scan_maven_paths(tmp_root, ignore_patterns, root_path)

    # This prefix is a subdir under top-level directory in zip file
    # or root before real GAV dir structure
    if not os.path.isdir(top_level):
        logger.error("Error: the extracted top-level path %s does not exist.", top_level)
        sys.exit(1)

    # 3. copy the signed artifacts to the destination directory
    logger.info("Starting copying files to the output directory %s", destination_dir)
    copy_files_to_destination(file_paths=valid_mvn_paths, root_path=top_level, destination_dir=destination_dir)
    logger.info("Files copying done")
    generated_signs = []

    # 4. Write manifest file
    _, manifest_full_path = write_manifest(valid_mvn_paths, top_level, product_key)
    logger.info("Manifest file written: %s", manifest_full_path)

    # 5. Generate maven-metadata.xml files
    logger.info("Start generating maven-metadata.xml files for destination directory %s", destination_dir)
    meta_files = generate_metadatas(
        destination_dir=destination_dir,
        poms=valid_poms, root=top_level,
    )
    logger.info("maven-metadata.xml files generation done\n")
    failed_metas = meta_files.get(META_FILE_FAILED, [])

    # 6. Copy all maven-metadata.xml to the destination directory
    if META_FILE_GEN_KEY in meta_files:
        logger.info("Start updating maven-metadata.xml to the destination directory %s", destination_dir)
        copy_files_to_destination(
            file_paths=meta_files[META_FILE_GEN_KEY],
            root_path=top_level,
            destination_dir=destination_dir,
        )
        logger.info("maven-metadata.xml updating done in the destination directory %s\n", destination_dir)

    # 7. Determine refreshment of archetype-catalog.xml
    if os.path.exists(os.path.join(top_level, MAVEN_ARCH_FILE)):
        logger.info("Start generating archetype-catalog.xml for the destination directory %s", destination_dir)
        archetype_file = generate_archetype_catalog(
            root=top_level,
            destination_dir=destination_dir
        )
        logger.info("archetype-catalog.xml files generation done in destination directory %s\n", destination_dir)

        # 8. Copy archetype-catalog.xml if it has changed
        if archetype_file:
            archetype_files = [os.path.join(top_level, ARCHETYPE_CATALOG_FILENAME)]
            archetype_files.extend(
                hash_decorate_metadata(top_level, ARCHETYPE_CATALOG_FILENAME)
            )
            logger.info("Start updating archetype-catalog.xml to the destination directory %s", destination_dir)
            copy_files_to_destination(
                file_paths=archetype_files,
                root_path=top_level,
                destination_dir=destination_dir,
            )
            logger.info("archetype-catalog.xml updating done in the destination directory %s\n", destination_dir)

    # 9. Generate signature files from radas sign result
    logger.info("Start generating radas signature files for the destination directory %s\n", destination_dir)
    (_failed_metas, _generated_signs) = generate_radas_sign(
        top_level=top_level, root=root_path, sign_result_file=sign_result_file
    )
    if not _generated_signs:
        logger.error(
            "No sign result files were generated, "
            "please make sure the sign process is already done and without timeout")
        return (tmp_root, False)

    failed_metas.extend(_failed_metas)
    generated_signs.extend(_generated_signs)
    logger.info("Radas signature files generation done.\n")

    # 10. Copy signature files to the destination directory
    logger.info("Start copying radas signature files to the destination directory %s\n", destination_dir)
    copy_files_to_destination(
        file_paths=generated_signs,
        root_path=top_level,
        destination_dir=destination_dir,
    )
    logger.info("Radas signature files copying done.\n")
