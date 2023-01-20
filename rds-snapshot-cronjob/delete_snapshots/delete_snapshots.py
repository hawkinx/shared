#! /usr/bin/env python

# A tag called 'expiry' and containing the expiry datetime is added to each snapshot at creation
# So for clearing expired snapshots, just delete all that have passed their expiry dates
# Checks if snapshot is 'available'; if not, skips it and it will be checked again next time
# If the tag 'expiry' is missing the snapshot never expires; reomove the expiry tag to retain a snapshot
# Basic logging and exception handling, but should be enough

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
  # Simple exception handling
  # If any exception occurs for a RDS snapshot, it is captured and the loop moves on to the next
  # Generic to ensure that the show goes on; details printed so that the issues can be identified
  try:  
    tags = rds_client.list_tags_for_resource(ResourceName=snapshot['DBSnapshotArn'])
    for tag in tags['TagList']:
      if tag['Key'] == 'snapshot_expiry': 
        no_expired_found = False
        datetime_expiry = datetime.datetime.strptime(tag['Value'], "%Y-%m-%d_%H:%M:%S")
        if datetime_expiry < datetime_now:
          # Snapshot must be in 'available' state before deletion
          if snapshot['Status'] == 'available':
            response = rds_client.delete_db_snapshot(DBSnapshotIdentifier=snapshot['DBSnapshotIdentifier'])
            print('Snapshot %s deleted' %(snapshot['DBSnapshotIdentifier']))
          else:
            # Shouldn't happen, but if it does we are covered
            print('Snapshot %s not available for deletion' %(snapshot['DBSnapshotIdentifier']))
  except Exception as e:
    # Simple message for now; assumes that snapshot identifier (i.e. name) is at least OK
    print('Exception occurred for RDS snapshot %s : %s' %(snapshot['DBSnapshotIdentifier'], e))

# Didn't find any so put that in the log so we can see that the script was run
if no_expired_found: 
  print('No expired snapshots found')

