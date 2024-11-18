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
import uuid

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
        print(
            '[INFO] Dryrun Mode={} | cleaning "DFS" files from {} to {} in folders : {}'.format(
                dryrun,
                self.PERIOD_START_DATE, self.PERIOD_END_DATE,
                ' + '.join(self.TARGET_ROOT_FOLDERS)
            )
        )

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
        print('[INFO] Dryrun Mode={} | cleaning "AWS/S3" learner certificates ".PNG" files in Bucket[{}]'.format(dryrun, self.BUCKET))
        self._dryrun = dryrun
        self._s3_conn = boto.connect_s3(settings.CERT_AWS_ID, settings.CERT_AWS_KEY)
        self._bucket = self._s3_conn.get_bucket(self.BUCKET)

    @classmethod
    def is_leaner_certificate(cls, s3_uri):
        """Return `True`: Learner Certificate
            `False`: Example Certificate
            `None`: Unrecognized
        """
        _sectors = s3_uri.split(cls.FILE_USERNAME_SEPARATOR)
        if len(_sectors) < 2:
            return None

        _username_or_uuid = _sectors[0].split('/')[-1]
        if _username_or_uuid:
            try:
                uuid.UUID(_username_or_uuid)
                return False        # (UUID): Example Certificate
            except ValueError:
                return True         # (Username): It's a Learner Certificate if ValueError raised here.

        return None

    def delete_png_once(self):
        example_cert_number = 0
        unrecognized_number = 0
        removed_learner_png_number = 0
        batch_count = 0
        marker = None       # Used for pagination

        while True:
            is_printed = False
            batch_count += 1
            # List all files with the specified prefix
            results = self._bucket.list(prefix=self.CERT_FILE_PREFIX, marker=marker)
            _last_key_name = None       # Track the last key name in the current batch

            for key in results:
                _png_resource_uri = key.name
                _last_key_name = key.name

                if _png_resource_uri.endswith(self.CERT_FILE_SUFFIX):                           # Only take .PNG files
                    _is_leaner_certificate = self.is_leaner_certificate(_png_resource_uri)      # Learner Certificate Only

                    if _is_leaner_certificate == None:
                        unrecognized_number += 1
                        is_printed = True
                        print('[ERROR] Got an Unrecognized URI : {}'.format(_png_resource_uri.encode('utf-8')))

                    elif _is_leaner_certificate:
                        is_printed = True
                        print('[INFO] DELETING Learner Certificate PNG: {} '.format(_png_resource_uri.encode('utf-8')))
                        if self._dryrun == False:
                            self._bucket.delete_key(_png_resource_uri)                          # Delete .PNG files of Learner Certificate
                            removed_learner_png_number += 1
                    else:
                        example_cert_number += 1                                                # Count Example Certificates Number

            # If no keys were processed, we're done
            if not _last_key_name:
                break
            # Update the marker to the last key name
            marker = _last_key_name

            if not is_printed:
                print('[INFO] Batch No. ---> {}, marker flag ---> {}'.format(batch_count, marker.encode('utf-8')))

        print(
            '[INFO] Example Certificate Number = {}, Unrecognized URI Number = {}, Removed Learner Certificate PNG Number = {}'.format(
                example_cert_number, unrecognized_number, removed_learner_png_number
            )
        )

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
