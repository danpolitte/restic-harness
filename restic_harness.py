#!/usr/bin/python3

import sys
import argparse
import shlex
import os
import subprocess
import json
import configparser
import platform

""" The script that runs restic for you """

"""
TODO: add useful description here
"""

# TODO: make sure that no unrecognized config options are present for both source
# & dest. These might be typos that lead to behaviors the user didn't intend.

class restic_source(object):
    def __init__(self, source_dict, source_name, config_dir_abs):
        # Required properties
        self.name = source_name
        self.display_name = source_dict['display name']
        self.path = os.path.join(config_dir_abs, source_dict['path']) # Path in dictionary can be absolute or relative & this will work

        # Optional properties
        self.excludeFile = os.path.join(config_dir_abs, source_dict['exclude file']) if 'exclude file' in source_dict else None # Path in dictionary can be absolute or relative & this will work
        self.customHost = source_dict['custom host'] if 'custom host' in source_dict else None

class restic_dest(object):
    def __init__(self, dest_dict, dest_name, config_dir_abs):
        # Required properties
        self.name = dest_name
        self.display_name = dest_dict['display name']
        self.repo_path =  dest_dict['repo path']
        self.password_file =  os.path.join(config_dir_abs, dest_dict['password file'])

        # Optional properties
        # The env vars are given as a string of JSON, if present. We make it
        # into a dictionary of properties either way
        self.env_vars = json.loads(dest_dict['env']) if 'env' in dest_dict else {}

def build_backup_command(src_obj: restic_source, dest_obj: restic_dest, executable_path: str, quiet: bool):
    # Produces subprocess-compatible array of strings for the backup command

    command = []

    # The call to restic, with its many arguments
    command.append(executable_path)
    command.append('backup')
    if src_obj.customHost:
        command.extend(['--host', src_obj.customHost])
    if src_obj.excludeFile:
        command.extend(['--exclude-file', src_obj.excludeFile])
    command.extend(['--repo', dest_obj.repo_path])
    command.extend(['--password-file', dest_obj.password_file])
    if not quiet:
        command.append('--verbose')
    command.append(src_obj.path)

    return command

def main(args):
    dests_requested = args.dests
    is_dryrun = args.dry_run

    # The main config file is definitely in the same directory as this script.
    # Policy: we also assume that any paths given in the config files that are
    # relative are relative to this directory, too. (os.path.join handles this
    # and also leaving the absolute paths alone.)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    #print('This script appears to be in',script_dir)

    main_config_path = os.path.join(script_dir,'config.ini')
    #print('Main config should be at:', main_config_path)

    main_config_data = parse_configParser_config(main_config_path)['config']

    # ID the source & dest config files & the restic executable's location

    sources_config_abs = os.path.join(script_dir, main_config_data['sources config'])
    dest_config_abs = os.path.join(script_dir, main_config_data['destinations config'])
    restic_exec_abs = os.path.join(script_dir, main_config_data['restic executable'])

    # Read the source info & organize it
    source_config_data = parse_configParser_config(sources_config_abs)
    source_names = source_config_data.sections()
    sources = []
    for source in source_names:
        sources.append(restic_source(source_config_data[source], source, script_dir))

    # Read the destination info & organize it (so we can look dests up by name)
    dest_config_data = parse_configParser_config(dest_config_abs)
    dest_names = dest_config_data.sections()
    dests_dict = {}
    for dest in dest_names:
        dests_dict[dest] = restic_dest(dest_config_data[dest], dest, script_dir)

    # Loop through dests & sources and do all the backups
    for requested_dest in dests_requested:
        dest_obj = dests_dict[requested_dest]

        # Prepare destination's expected environment variables (add them to the calling shell's)
        env_vars = os.environ
        env_vars.update(dest_obj.env_vars)

        for source_obj in sources:

            if os.path.exists(source_obj.path):
                print('Backing up {source_obj.display_name} to {dest_obj.display_name}...'.format(**locals()))

                # Generate full command
                backup_command = build_backup_command(source_obj, dest_obj, restic_exec_abs, args.quiet)

                if not args.quiet:
                    print('Command:',quote_for_shell(backup_command))

                # Run the command
                if not is_dryrun:
                    subprocess.run(backup_command, env=env_vars)
            else:
                print('Skipping source {source_obj.display_name} since it isn\'t reachable...'.format(**locals()))
            print()
            print()

    print('Done.')

def quote_for_shell(shell_token_list):
    """
    Given a list of strings that's a command suitable e.g. for the subprocess module, turn it into (approximately)
    what would actually run in the shell. Don't run this! It's just for the user's gratification.
    """
    return ' '.join(shlex.quote(token) for token in shell_token_list)

def parse_configParser_config(config_path):
    # Read a config file in the Python ConfigParser format
    config = configparser.ConfigParser()
    config.read(config_path)
    return config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='The script that runs Restic backups for you from simple config files')
    parser.add_argument('dests', metavar='dest', help='the destination(s) to to backup to', nargs='+')
    parser.add_argument('-n', '--dry-run', help='do not perform backup, just print what would be done', action='store_true')
    parser.add_argument('-q', '--quiet', help='suppress most stdout from this function', action='store_true')
    args = parser.parse_args()
    main(args)
