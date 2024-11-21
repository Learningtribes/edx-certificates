"""
    Remove unwanted files from DFS or S3 by arguments :
        - DFS:      Local certificate folders generated before uploading to S3
        - AWS/S3:   .PNG files of Learner Certificate

    Usage:
        (certs) certs@learning-tribes:~$ pwd
        /edx/app/certs
        $ sudo -H -u certs bash
        (certs) certs@learning-tribes:~$ source /edx/app/certs/venvs/certs/bin/activate
        (certs) certs@learning-tribes:~$ /edx/app/certs/venvs/certs/bin/python /edx/app/certs/certificates/cleaner.py --target_type=[s3|dfs] --dryrun=[true|false]
        [INFO] Dryrun Mode=True | cleaning AWS/S3 files, Bucket Name=lt-learning-customer2-default
        Done !

"""
from argparse import ArgumentParser
from datetime import datetime
import os
import shutil
from sys import exit as process_terminate
from traceback import format_exc
import uuid

import boto.s3
from boto.s3.key import Key

import settings


class DFSCleaner(object):
    """Clean unwanted files in DFS ( folders: /downloads + /cert ).
        And we can specify the `End Date` of date range in the process.
    """
    TARGET_ROOT_FOLDERS = [                 # Target folders where we want to clean
        '/edx/var/certs/www-data/downloads',
        '/edx/var/certs/www-data/cert'
    ]
    PERIOD_START_DATE = None

    def __init__(self):
        self.PERIOD_START_DATE = datetime.strptime(
            raw_input('Please enter Start date [Format: 2019-12-06]: '),
            '%Y-%m-%d'
        )
        print(
            '[INFO] cleaning "DFS" files since {} in folders : {}'.format(
                self.PERIOD_START_DATE, ' + '.join(self.TARGET_ROOT_FOLDERS)
            )
        )

    def run(self, dryrun=True):
        for root_folder in self.TARGET_ROOT_FOLDERS:
            print('[INFO] ################# Root folder {} #################'.format(root_folder))

            for folder_name in os.listdir(root_folder):
                resource_folder = os.path.join(root_folder, folder_name)
                if os.path.isdir(resource_folder):
                    mod_time = datetime.fromtimestamp(os.path.getmtime(resource_folder))
                    if self.PERIOD_START_DATE <= mod_time:
                        print('[INFO] DELETING {} (Modified: {})'.format(resource_folder, mod_time))
                        if dryrun == False:
                            shutil.rmtree(resource_folder)  # Delete folder and its contents


class S3LearnerCertPNGCleaner(object):
    """Delete PNG files associated with `Learner certificates` on S3
    """
    BUCKET = settings.CERT_BUCKET
    CERT_FILE_PREFIX = 'downloads/'
    CERT_FILE_SUFFIX = '.png'
    FILE_USERNAME_SEPARATOR = '_course-v1'

    def __init__(self):
        print('[INFO] cleaning "AWS/S3" learner certificates ".PNG" files in Bucket[{}]'.format(self.BUCKET))
        self.s3_conn = boto.connect_s3(settings.CERT_AWS_ID, settings.CERT_AWS_KEY)
        self.bucket = self.s3_conn.get_bucket(self.BUCKET)

    @classmethod
    def is_leaner_certificate(cls, s3_uri):
        """Return `True`: Learner Certificate
            `False`: Example Certificate
            `None`: Unrecognized
        """
        sectors = s3_uri.split(cls.FILE_USERNAME_SEPARATOR)
        if len(sectors) < 2:
            print('[ERROR] Invalid URI format: {}'.format(s3_uri.encode('utf-8')))
            return None

        _username_or_uuid = sectors[0].split('/')[-1]
        if _username_or_uuid:
            try:
                uuid.UUID(_username_or_uuid)
                return False        # (UUID): Example Certificate
            except ValueError:
                return True         # (Username): It's a Learner Certificate if ValueError raised here.

        print('[ERROR] Got an Unrecognized URI : {}'.format(s3_uri.encode('utf-8')))
        return None

    def run(self, dryrun=True):
        example_cert_number = 0
        unrecognized_number = 0
        removed_learner_png_number = 0
        batch_count = 0
        marker = None       # Used for pagination

        while True:
            batch_count += 1
            # List all files with the specified prefix
            results = self.bucket.list(prefix=self.CERT_FILE_PREFIX, marker=marker)
            last_key_name = None       # Track the last key name in the current batch

            for key in results:
                png_resource_uri = key.name
                last_key_name = key.name

                if png_resource_uri.endswith(self.CERT_FILE_SUFFIX):                           # Only take .PNG files
                    is_leaner_certificate = self.is_leaner_certificate(png_resource_uri)       # Learner Certificate Only

                    if is_leaner_certificate == None:
                        unrecognized_number += 1

                    elif is_leaner_certificate:
                        print('[INFO] DELETING Learner Certificate PNG: {} '.format(png_resource_uri.encode('utf-8')))
                        if dryrun == False:
                            self.bucket.delete_key(png_resource_uri)                            # Delete .PNG files of Learner Certificate
                            removed_learner_png_number += 1
                    else:
                        example_cert_number += 1                                                # Count Example Certificates Number

            # If no keys were processed, we're done
            if not last_key_name:
                break
            # Update the marker to the last key name
            marker = last_key_name

        print(
            '[INFO] Example Certificate Number = {}, Unrecognized URI Number = {}, Removed Learner Certificate PNG Number = {}'.format(
                example_cert_number, unrecognized_number, removed_learner_png_number
            )
        )


if __name__ == '__main__':
    try:
        def argsStr2Bool(arg_str):
            return True if arg_str.lower() in ('yes', 'true', 't', '1') else False

        parser = ArgumentParser(description=r'A resource ( DFS / S3 ) cleaner.')
        parser.add_argument('--target_type', default='EmptyType', help='Options => dfs / s3')
        parser.add_argument('--dryrun', type=argsStr2Bool, default=True, help='Options => dfs / s3')
        args = parser.parse_args()
        print('[INFO] Dryrun mode : {}'.format('ON' if args.dryrun else 'OFF'))

        ########### Start to run cleaning task ###########
        if args.target_type == 'dfs':
            DFSCleaner().run(args.dryrun)
        elif args.target_type == 's3':
            S3LearnerCertPNGCleaner().run(args.dryrun)
        else:
            raise Exception('[Error] Invalid target type: {}'.format(args.target_type))

        print(r'Done !')

    except Exception:
        print(r'[Exception]: {err_msg}'.format(err_msg=format_exc()))
        process_terminate(10)
