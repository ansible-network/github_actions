#!/usr/bin/python
"""Install checkout version of packages into tox environment."""

import ast
import logging
import os
import subprocess
import sys

from argparse import ArgumentParser
from configparser import ConfigParser
from configparser import NoOptionError
from configparser import NoSectionError
from configparser import RawConfigParser
from pathlib import PosixPath
from tempfile import NamedTemporaryFile
from typing import Any
from typing import Optional


FORMAT = "[%(asctime)s] - %(message)s"
logging.basicConfig(format=FORMAT)
logger = logging.getLogger("install_sibling")
logger.setLevel(logging.DEBUG)


def run_tox_command(
    project_dir: PosixPath,
    env_name: Optional[str],
    label_name: Optional[str],
    config_file: Optional[PosixPath],
    env_vars: Optional[dict[Any, Any]],
    extra_args: list[str],
) -> str:
    """Execute a tox command using subprocess.

    :param project_dir: The location of the project containing tox.ini file.
    :param env_name: An optional tox env name.
    :param label_name: An optional tox label name.
    :param config_file: An optional tox configuration file.
    :param env_vars: An optional dictionary of environment to set when running command.
    :param extra_args: Tox extra args.
    :returns: The output result of the shell command.
    """
    tox_cmd = ["tox"]
    if env_name:
        tox_cmd.extend(["-e", env_name])
    if label_name:
        tox_cmd.extend(["-m", label_name])
    if config_file:
        tox_cmd.extend(["-c", str(config_file)])
    if extra_args:
        tox_cmd.extend(extra_args)

    logger.info("Running %s cwd=%s, env=%s", tox_cmd, str(project_dir), env_vars)
    with subprocess.Popen(
        " ".join(tox_cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        encoding="utf-8",
        cwd=str(project_dir),
        env=env_vars,
    ) as proc:
        out, err = proc.communicate()
        if proc.returncode != 0:
            logger.error(err)
            sys.exit(1)
        return out


def tox_config_remove_verbose(raw_config: str) -> str:
    """Filter out any leading verbose output lines before the config.

    :param raw_config: tox raw config
    :returns: A new tox config without verbose
    """
    items = raw_config.split("\n")
    index = 0
    result = ""
    for index in range(len(raw_config)):
        # Once we see a section heading, we collect all remaining lines
        if items[index].startswith("[") and items[index].rstrip().endswith("]"):
            result = "\n".join(items[index:])
            break
    return result


def get_envlist(tox_config: RawConfigParser) -> list[str]:
    """Retrieve tox env list from raw config.

    :param tox_config: tox raw config
    :returns: A list of tox environment names
    """
    envlist = []
    if (
        "tox" in tox_config.sections()
        and "env" in tox_config.options("tox")
        and "'-e" not in tox_config.get("tox", "args")
    ):
        envlist_default = ast.literal_eval(tox_config.get("tox", "envlist_default"))
        tox_args = ast.literal_eval(tox_config.get("tox", "args"))
        if "ALL" in tox_args or not envlist_default:
            for section in tox_config.sections():
                if section.startswith("testenv"):
                    envlist.append(section.split(":")[1])
        else:
            for testenv in envlist_default:
                envlist.append(testenv)
    else:
        for section in tox_config.sections():
            if section.startswith("testenv:"):
                envlist.append(section.split(":")[1])
    return envlist


def read_package_name(path: str, tox_py: str) -> Optional[str]:
    """Read package name from from setup.cfg or by running setup.py.

    :param path: the location of the python package
    :param tox_py: python executable using to test setup.py
    :returns: A python package name
    """
    setup_cfg = os.path.join(path, "setup.cfg")
    name = None
    if os.path.exists(setup_cfg):
        config = ConfigParser()
        config.read(setup_cfg)
        try:
            name = config.get("metadata", "name")
        except (NoSectionError, NoOptionError):
            # Some things have a setup.cfg, but don't keep
            # metadata in it; fall back to setup.py below
            logger.info("[metadata] name not found in %s, skipping", setup_cfg)
    else:
        logger.info("%s does not exist", setup_cfg)
        setup_py = os.path.join(path, "setup.py")
        if not os.path.exists(setup_py):
            logger.info("%s does not exist", setup_py)
        else:
            # It's a python package but doesn't use pbr, so we need to run
            # python setup.py --name to get setup.py to tell us what the
            # package name is.
            package_name = subprocess.check_output(
                [os.path.abspath(tox_py), "setup.py", "--name"],
                cwd=path,
                shell=True,
                stderr=subprocess.STDOUT,
            ).decode("utf-8")
            if package_name:
                name = package_name.strip()
    return name


def identify_packages(dirs: list[str], tox_py: str) -> dict[str, str]:
    """Retrieve package name from provided directories.

    :param dirs: list of python package directories
    :param tox_py: python executable using to test setup.py
    :returns: A dictionary containing package names and location
    """
    packages = {}
    for path in dirs:
        package_name = read_package_name(path, tox_py)
        if not package_name:
            logger.info("Could not find package name for '%s'", path)
        else:
            packages[package_name] = path
            # Convert a project or version name to its filename-escaped form
            # Any '-' characters are currently replaced with '_'.
            # Implementation vendored from pkg_resources.to_filename in order to avoid
            # adding an extra runtime dependency.
            packages[package_name.replace("-", "_")] = path
    return packages


def find_installed_packages(tox_python: str, packages: dict[str, str]) -> list[str]:
    """Find installed packages from python environment.

    :param tox_python: path to python executable
    :param packages: dependencies packages to filter
    :returns: The list of python packages installed into python environment
    """
    # We use the output of pip freeze here as that is pip's stable public
    # interface.
    frozen_pkgs = subprocess.check_output(
        [tox_python, "-m", "pip", "-qqq", "freeze"], stderr=subprocess.STDOUT
    ).decode("utf-8")
    # Matches strings of the form:
    # 1. '<package_name>==<version>'
    # 2. '# Editable Git install with no remote (<package_name>==<version>)'
    # 3. '<package_name> @ <URI_reference>' # PEP440, PEP508, PEP610
    # results <package_name>
    installed_packages = []
    for item in frozen_pkgs.split("\n"):
        if "==" in item:
            name = item[item.find("(") + 1 :].split("==")[0]
            if name in packages:
                installed_packages.append(name)
        elif "@" in item:
            name = item.split("@")[0].rstrip(" \t")
            if name in packages:
                installed_packages.append(name)
    return installed_packages


def create_constraints_file(constraints_file: str, packages: list[str]) -> str:
    """Create new constraints file by removing installed dependencies.

    :param constraints_file: tox constraints file
    :param packages: dependencies packages
    :returns: the path to the new constraints file
    """
    with NamedTemporaryFile(mode="w", delete=False) as temp_constraints_file:
        with open(constraints_file, encoding="utf-8") as file_handler:
            constraints_lines = file_handler.read().split("\n")
            for line in constraints_lines:
                package_name = line.split("===")[0]
                if package_name in packages:
                    continue
                temp_constraints_file.write(line)
                temp_constraints_file.write("\n")
            return temp_constraints_file.name


def install_into_env(envdir: str, dirs: list[str], constraints_file: Optional[str]) -> None:
    """Install dependencies packages into a python directory.

    :param envdir: The list of projects directories
    :param dirs: tox raw config
    :param constraints_file: tox constraints file
    """
    tox_python = f"{envdir}/bin/python"

    # identify packages dependencies
    packages = identify_packages(dirs, tox_python)
    for name, path in packages.items():
        logger.info("Packages -> name [%s] - path [%s]", name, path)

    # find packages installed version
    installed_packges = find_installed_packages(tox_python, packages)
    logger.info("installed packages => %s", installed_packges)

    tmp_contraints_file = None
    if constraints_file:
        tmp_contraints_file = create_constraints_file(constraints_file, installed_packges)

    for name in installed_packges:
        # uninstall package first
        uninstall_cmd = [tox_python, "-m", "pip", "uninstall", "-y", name]
        logger.info("Uninstalling package '%s' using %s", name, uninstall_cmd)
        uninstall_output = subprocess.check_output(uninstall_cmd)
        logger.info(uninstall_output.decode("utf-8"))

        install_cmd = [tox_python, "-m", "pip", "install"]
        if tmp_contraints_file:
            install_cmd.extend(["-c", tmp_contraints_file])

        package_dir = packages[name]
        install_cmd.append(package_dir)
        logger.info(
            "Installing package '%s' from '%s' for deps using %s",
            name,
            package_dir,
            install_cmd,
        )
        install_output = subprocess.check_output(install_cmd)
        logger.info(install_output.decode("utf-8"))

    for name in installed_packges:
        package_dir = packages[name]
        command = [tox_python, "-m", "pip", "install", "--no-deps", package_dir]
        logger.info("Installing '%s' from '%s' using %s", name, package_dir, command)
        install_output = subprocess.check_output(command)
        logger.info(install_output.decode("utf-8"))


def install_packages(
    projects: list[str],
    tox_raw_config: str,
    tox_envname: Optional[str],
    constraints_file: Optional[str],
) -> None:
    """Install dependencies packages into a tox env.

    :param projects: The list of projects directories
    :param tox_raw_config: tox raw config
    :param tox_envname: tox env name
    :param constraints_file: tox constraints file
    """
    tox_config = RawConfigParser()
    tox_config.read_string(tox_config_remove_verbose(tox_raw_config))

    envlist = get_envlist(tox_config)
    logger.info("env list => %s", envlist)
    if not envlist:
        return

    for testenv in envlist:
        envname = f"testenv:{testenv}"
        if tox_envname and tox_envname not in (envname, testenv):
            continue
        envdir, envlogdir = None, None
        for key in ("envdir", "env_dir"):
            if tox_config.has_option(envname, key):
                envdir = tox_config.get(envname, key)
                break
        for key in ("envlogdir", "env_log_dir"):
            if tox_config.has_option(envname, key):
                envlogdir = tox_config.get(envname, key)
                break
        if not envdir or not envlogdir:
            logger.error("Unable to find tox env directories for envname -> '%s'", envname)
            sys.exit(1)
        logger.info("installing packages from env '%s', envdir='%s'", envname, envdir)
        install_into_env(envdir, projects, constraints_file)


def main() -> None:
    """Read inputs parameters and install packages."""
    parser = ArgumentParser(
        description="Install checkout version of packages into tox environment."
    )
    parser.add_argument(
        "--tox-config-file", type=PosixPath, help="the location of the tox configuration file"
    )
    parser.add_argument("--tox-envname", help="the tox env name.")
    parser.add_argument("--tox-labelname", help="the tox label name.")
    parser.add_argument(
        "--tox-project-dir", default=".", help="the location of the project containing tox.ini file"
    )
    parser.add_argument(
        "--tox-env-vars",
        default="",
        help="the environment to set when running tox command. e.g: env1=value1\nenv2=value2",
    )
    parser.add_argument(
        "--tox-constraints-file", type=PosixPath, help="the location to the tox constraints file."
    )
    parser.add_argument(
        "tox_packages",
        default=[],
        nargs="+",
        help="the location of the package to install",
    )

    args = parser.parse_args()
    tox_extra_args = os.environ.get("TOX_EXTRA_ARGS")

    # parse tox environment variables
    tox_environment = {
        x.split("=", maxsplit=1)[0]: x.split("=", maxsplit=1)[1]
        for x in args.tox_env_vars.split("\n")
        if x
    } or None

    # Run tox without test
    extra_args = ["--notest"]
    if tox_extra_args:
        extra_args.append(tox_extra_args)
    run_tox_command(
        args.tox_project_dir,
        args.tox_envname,
        args.tox_labelname,
        args.tox_config_file,
        tox_environment,
        extra_args,
    )

    # show environment config
    extra_args = ["--showconfig"]
    tox_raw_config = run_tox_command(
        args.tox_project_dir,
        args.tox_envname,
        args.tox_labelname,
        args.tox_config_file,
        tox_environment,
        extra_args,
    )
    logger.info("Show config => %s", tox_raw_config)

    # install dependencies packages
    projects_dir = [os.path.abspath(path) for path in args.tox_packages]
    logger.info("Packages dirs -> %s", projects_dir)
    install_packages(projects_dir, tox_raw_config, args.tox_envname, args.tox_constraints_file)


if __name__ == "__main__":
    main()
