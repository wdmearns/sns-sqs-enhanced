# (C) British Crown Copyright 2017, Met Office
"""
A command-line utility to poll an SQS queue for S3 events delivered via
SNS, and download the corresponding objects.

"""
import argparse
import json
import os.path
import requests

import boto3


DOWNLOAD_DIR = 'objects'
S3 = boto3.client('s3')


def download_object(url, verbose):
    if not os.path.exists(DOWNLOAD_DIR):
        os.mkdir(DOWNLOAD_DIR)
    target_path = os.path.join(DOWNLOAD_DIR, url.split('/')[-1])
    if verbose:
        print('Beginning download of {} to {}'.format(url, target_path))
    r = requests.get(url)
    with open(target_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=128):
            fd.write(chunk)
    if verbose:
        print('Completed download of {} to {}'.format(url, target_path))


def download_from_queue(queue_name, start_time, end_time, diagnostics,
                        keep_messages, verbose):
    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    if verbose:
        print("Using: {}".format(queue.url))
    while True:
        if verbose:
            print("Checking...")

        for message in queue.receive_messages(WaitTimeSeconds=2):
            message_body = json.loads(message.body)
            sns_notification = json.loads(message_body['Message'])

            # Production code should verify the SNS signature before
            # proceeding.

            if sns_notification['metadata']['name'] in diagnostics:
                if int(sns_notification['metadata']['forecast_period']) >= start_time:
                    if int(sns_notification['metadata']['forecast_period']) <= end_time:
                        download_object(sns_notification['url'], verbose)

            if not keep_messages:
                message.delete()


def check_times(start_time, end_time):
    if (start_time > end_time):
        raise ValueError('End time should be greater than or equal to start time')
    return (start_time * 60 * 60, end_time * 60 * 60)

'''
Take a list of elements as given in command line arguments, and return list
of related metadata names (NB This also filters out metadata names we're not
interested in, as well as any unrecognised names)
'''


def check_diagnostics(diagnostics):
    return_list = []
    if 'temperature' in diagnostics:
        return_list.append('surface_temperature')
    if 'pressure' in diagnostics:
        return_list.append('surface_air_pressure')
    if 'humidity' in diagnostics:
        return_list.append('relative_humidity')
    return return_list

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download objects identified in S3 events delivered'
                    ' to an SQS queue.')
    parser.add_argument('queue_name')
    parser.add_argument('start_time', type=int)
    parser.add_argument('end_time', type=int)
    parser.add_argument('diagnostic')
    parser.add_argument('-k', '--keep', action='store_true',
                        help='Retain messages in SQS queue after processing.'
                             ' (Useful when debugging.)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Turn on verbose output.')
    args = parser.parse_args()

    (start_time, end_time) = check_times(args.start_time, args.end_time)

    valid_diagnostics = check_diagnostics(args.diagnostic.split(','))

    download_from_queue(args.queue_name, start_time, end_time,
                        valid_diagnostics, args.keep, args.verbose)
