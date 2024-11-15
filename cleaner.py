"""
    Remove unwanted files from Disk or S3 by arguments.

    Usage:
        (certs) certs@learning-tribes:~$ pwd
        /edx/app/certs
        (certs) certs@learning-tribes:~$ source /edx/app/certs/venvs/certs/bin/activate
        (certs) certs@learning-tribes:~$ /edx/app/certs/venvs/certs/bin/python /edx/app/certs/certificates/cleaner.py --target_type=[s3|dfs] --dryrun=[true|false]
        [INFO] Dryrun Mode=True | cleaning AWS/S3 files, Bucket Name=lt-learning-customer2-default
        Done !

"""
from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import shutil
from sys import exit as process_terminate
from traceback import format_exc

import boto.s3
from boto.s3.key import Key

import settings


class _CleanerInterface(object):
    """Regulate all subclass of cleaner
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self):
        """Execute cleaning task
        """
        raise NotImplementedError


class DFSCleaner(_CleanerInterface):
    """Clean unwanted files in DFS ( folders: /downloads + /cert ).
        And we can specify the `End Date` of date range in the process.
    """
    TARGET_ROOT_FOLDERS = [                 # Target folders where we want to clean
        '/edx/var/certs/www-data/downloads',
        '/edx/var/certs/www-data/cert'
    ]
    PERIOD_START_DATE = datetime(2020, 2, 12)
    PERIOD_END_DATE = None

    def __init__(self, dryrun=True):
        self.PERIOD_END_DATE = datetime.now() - relativedelta(
            months=int(input('Please enter Month number of files which you wanna to remain: '))
        )
        self._dryrun = dryrun
        print('[INFO] Dryrun Mode={} | cleaning DFS files from {} to {}'.format(dryrun, self.PERIOD_START_DATE, self.PERIOD_END_DATE))

    def delete_resources_in_range(self, root_folder):
        for _folder_name in os.listdir(root_folder):
            _resource_folder = os.path.join(root_folder, _folder_name)
            if os.path.isdir(_resource_folder):
                _mod_time = datetime.fromtimestamp(os.path.getmtime(_resource_folder))
                if self.PERIOD_START_DATE < _mod_time < self.PERIOD_END_DATE:
                    print('[INFO] DELETING {} (Modified: {})'.format(_resource_folder, _mod_time))
                    if self._dryrun == False:
                        shutil.rmtree(_resource_folder)  # Delete folder and its contents

    def run(self):
        for _root_folder in self.TARGET_ROOT_FOLDERS:
            print('[INFO] ################# Root folder {} #################'.format(_root_folder))
            self.delete_resources_in_range(_root_folder)


class S3LearnerCertPNGCleaner(_CleanerInterface):
    """Delete PNG files associated with `Learner certificates` on S3
    """
    BUCKET = settings.CERT_BUCKET
    CERT_FILE_PREFIX = 'downloads/'
    CERT_FILE_SUFFIX = '.png'
    FILE_USERNAME_SEPARATOR = '_course-v1'

    def __init__(self, dryrun=True):
        print('[INFO] Dryrun Mode={} | cleaning AWS/S3 files, Bucket Name={}'.format(dryrun, self.BUCKET))
        self._dryrun = dryrun
        self._s3_conn = boto.connect_s3(settings.CERT_AWS_ID, settings.CERT_AWS_KEY)
        self._bucket = self._s3_conn.get_bucket(self.BUCKET)

    def delete_png_once(self):
        marker = None  # Used for pagination

        while True:
            count = 0
            # List all files with the specified prefix
            _cert_png_files = (key.name for key in self._bucket.list(prefix=self.CERT_FILE_PREFIX, marker=marker) if key.name.endswith(self.CERT_FILE_SUFFIX))
            for _png_resource_uri in _cert_png_files:
                print('[INFO] DELETING {} '.format(_png_resource_uri))
                if self._dryrun == False:
                    self._bucket.delete_key(_png_resource_uri)       # Delete the file
                marker = _png_resource_uri
                count += 1

            # If there are no more results, stop
            if not count:
                break

    def run(self):
        self.delete_png_once()


if __name__ == '__main__':
    try:
        def _argsStr2Bool(arg_str):
            return True if arg_str.lower() in ('yes', 'true', 't', '1') else False

        parser = ArgumentParser(description=r'A resource ( DFS / S3 ) cleaner.')
        parser.add_argument('--target_type', default='EmptyType', help='Options => dfs / s3')
        parser.add_argument('--dryrun', type=_argsStr2Bool, default=True, help='Options => dfs / s3')
        args = parser.parse_args()
        if args.target_type not in ('dfs', 's3'):
            raise Exception('[Error] Invalid target type: {}'.format(args.target_type))

        ########### Start to run cleaning task ###########
        _cleaner = DFSCleaner(args.dryrun) if args.target_type == 'dfs' else S3LearnerCertPNGCleaner(args.dryrun)
        _cleaner.run()

        print(r'Done !')

    except Exception:
        print(r'[Exception]: {err_msg}'.format(err_msg=format_exc()))
        process_terminate(10)
