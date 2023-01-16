#! /usr/bin/env python

# A tag called 'expiry' and containing the expiry datetime is added to each snapshot at creation
# So for clearing expired snapshots, just delete all that have passed their expiry dates
# Checks if snapshot is 'available'; if not, skips it and it will be checked again next time
# If the tag 'expiry' is missing the snapshot never expires; reomove the expiry tag to retain a snapshot
# Should add logging and exception handling once it is working

import boto3
import datetime

# RDS client
rds_client = boto3.client('rds', 'eu-north-1')

# Get the current date + time for setting expiry date
datetime_now = datetime.datetime.now()

# Get list of manual snapshots
snapshots = rds_client.describe_db_snapshots(SnapshotType="manual")

# For tracking if any snapshots qualify for deletion
no_expired_found = True

for snapshot in snapshots['DBSnapshots']:
  tags = rds_client.list_tags_for_resource(ResourceName=snapshot['DBSnapshotArn'])
  for tag in tags['TagList']:
    if tag['Key'] == 'snapshot_expiry': 
      no_expired_found = False
      datetime_expiry = datetime.datetime.strptime(tag['Value'], "%Y-%m-%d_%H:%M:%S")
      if datetime_expiry < datetime_now:
        # Snapshot must be in 'available' state before deletion
        if snapshot['Status'] == 'available':
          response = rds_client.delete_db_snapshot(DBSnapshotIdentifier=snapshot['DBSnapshotIdentifier'])
          # print(response)
          print('Snapshot %s deleted' %(snapshot['DBSnapshotIdentifier']))
        else:
          print('Snapshot %s not available for deletion; maybe next time' %(snapshot['DBSnapshotIdentifier']))
      # else:
      #   print('%s retained' %(snapshot['DBSnapshotIdentifier']))


# Didn't find any so put that in the log so we can see that the script was run
if no_expired_found: 
  print('No expired snapshots found')

