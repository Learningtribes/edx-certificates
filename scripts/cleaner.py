"""
    Remove unwanted files from Disk or S3 by arguments.

    Usage:
        python cleaner.py --target_type=s3/dfs --dryrun=True/False

"""
from argparse import ArgumentParser
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import shutil
from sys import exit as process_terminate
from traceback import format_exc


class DFSCleaner(object):
    """Clean unwanted files in DFS. And we can specify date range in the process.
    """
    TARGET_ROOT_FOLDERS = [                 # Target folders where we want to clean
        '/edx/var/certs/www-data/downloads',
        '/edx/var/certs/www-data/cert'
    ]
    PERIOD_START_DATE = datetime(2020, 1, 1)
    PERIOD_END_DATE = None

    def __init__(self, dryrun=True):
        self.PERIOD_END_DATE = datetime.now() - relativedelta(
            months=input('Please enter Month number of files which you wanna to remain: ')
        )
        self._dryrun = dryrun
        print('[INFO] Dryrun Mode={} | cleaning files from {} to {})'.format(dryrun, self.PERIOD_START_DATE, self.PERIOD_END_DATE))

    def delete_resources_in_range(self, root_folder):
        for _folder_name in os.listdir(root_folder):
            _resource_folder = os.path.join(root_folder, _folder_name)
            if os.path.isdir(_resource_folder):
                _mod_time = datetime.fromtimestamp(os.path.getmtime(_resource_folder))
                if self.PERIOD_START_DATE < _mod_time < self.PERIOD_END_DATE:
                    print('[INFO] DELETING {} (Modified: {})'.format(_resource_folder, _mod_time))
                    if self._dryrun == True:
                        return
                    shutil.rmtree(_resource_folder)  # Delete folder and its contents

    def run(self):
        for _root_folder in self.TARGET_ROOT_FOLDERS:
            print('[INFO] ################# Root folder {} #################'.format(_root_folder))
            self.delete_resources_in_range(_root_folder)


class S3Cleaner(object):
    def __init__(self, dryrun=True):
        print('[INFO] S3Cleaner(dryrun={})'.format(dryrun))
        self._dryrun = dryrun

    def run(self):
        pass


if __name__ == '__main__':
    try:
        parser = ArgumentParser(description=r'A resource ( DFS / S3 ) cleaner.')
        parser.add_argument(
            '--target_type', default='dfs', help='Options => dfs / s3'
        )
        parser.add_argument(
            '--dryrun', type=bool, default=True, help='Options => dfs / s3'
        )
        args = parser.parse_args()
        if args.target_type not in ('dfs', 's3'):
            raise Exception('[Error] Invalid target type: {}'.format(args.target_type))

        _cleaner = DFSCleaner(parser.dryrun) if args.target_type == 'dfs' else S3Cleaner(parser.dryrun)
        _cleaner.run()

        print(r'Done !')

    except Exception:
        print(r'[Exception]: {err_msg}'.format(err_msg=format_exc()))
        process_terminate(10)
