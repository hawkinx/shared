#! /usr/bin/env python

# Simple Python script to create RDS snapshots

# Uses UTC time zone

# Snapshot retention time added as a tag to snapshots; expiration is handled by a separate script

# Uses these tags on the RDS instance:
#  snapshot_retention_days -> number of days to retain the snapshot; used to calculate value in snapshot expiry tag 
#  snapshot_never -> disables snapshots if it exists; other tag content is ignored

# Each snapshot gets tagged with an expiry timestamp, calculated from current timestamp plus retention days
# Default retention time is set at 90 days; if no retention time set it will use this
# The snapshot_never tag is retained to keep in sync with my other snapshot script; might get removed

import boto3
import sys, os
import datetime, time

# Default value for retention days
DEFAULT_RETENTION_DAYS = '90'

# Currently only these AWS regions are permitted
PERMITTED_REGIONS = ['eu-north-1', 'eu-central-1']
# Set a default region
DEFAULT_REGION = 'eu-north-1'

# Timestamp value to make snapshot identifier unique; simple date-time for now
timestamp = str(time.strftime("%Y%m%d%H%M%S"))

# Get the current date + time for setting expiry date
datetime_now = datetime.datetime.now()

# Get region or set default 
aws_region = os.getenv('AWS_REGION')
if aws_region is None: aws_region = DEFAULT_REGION

# Now check that the region value is a permitted one
if aws_region not in PERMITTED_REGIONS: 
  print('Region \'%s\' not in permitted list - bailing out' %(aws_region))
  sys.exit(0)

# OK we're good; connect to rds instance
# Assumes IAM access has been granted to the service account running the script
try:
  rds_client = boto3.client('rds', aws_region)
except:
  print('Failed to connect to RDS client : %s' %(e))
  sys.exit(0)

instance_id = os.getenv('RDS_INSTANCE_ID')
if instance_id is None:
  print('Environment variable RDS_INSTANCE_ID undefined - bailing out')
  sys.exit(0)

# Can filter for a specific instance by using an identifier where 'string' is the ARN or the instance identifier
# rds_instances = rds_client.describe_db_instances(DBInstanceIdentifier='string')
# Returns a dict object with a single entry so old code to loop through multiple entries still useful

try:
  rds_instances = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
except Exception as e:
  # Probably the instance wasn't found so it failed; print an error message and bail out
  # print('Exception occurred : %s' %(e))
  print('Instance \'%s\' not found - bailing out' %(instance_id))
  sys.exit(0)

# OK now we can get down to business; get the first and in this script only instance
for instance in rds_instances['DBInstances']: 
  # Generic exception handling to ensure that the show goes on; details printed so that the issues can be identified
  try:
    dbInstanceName = instance['DBInstanceIdentifier']
    dbInstanceEngine = instance['DBInstanceClass']
    dbInstanceStatus = instance['DBInstanceStatus']
    dbInstanceArn = instance["DBInstanceArn"]
  
    # Set default values; will ge overwritten if found
    retention_days = DEFAULT_RETENTION_DAYS
    # Set to true if database tagged as never to be backed up
    no_snapshot = False

    # Get a few values from tags
    tags = rds_client.list_tags_for_resource(ResourceName=dbInstanceArn)
    for tag in tags["TagList"]:
      if tag['Key'] == 'snapshot_never': no_snapshot = True
      if tag['Key'] == "snapshot_retention_days": retention_days = tag['Value']
  
    if no_snapshot:
      print('Database %s tagged as never to be backed up' %(dbInstanceName))
    else:
      # Need to check if it is possible to take a snapshot
      dbInstanceStatus = instance['DBInstanceStatus']
      # Note however that there the status 'pending snapshot' is not captured here; will result in an exception
      if dbInstanceStatus in ['available', 'storage-optimization']:
        # Snapshot identifier needs to be locally unique so use db name + timestamp
        snapshotname = dbInstanceName + '-' + timestamp

        # Check if the value is numeric; if not use the default value
        if retention_days.isnumeric():
          ndays = int(retention_days)
        else:
          ndays = int(DEFAULT_RETENTION_DAYS)
          print('retention_days tag is non-numeric - %s - please check. Using default value %s instead' %(retention_days,DEFAULT_RETENTION_DAYS))  

        # Build the expiry tag
        datetime_expiry = datetime_now + datetime.timedelta(days=ndays)
        expiry = datetime_expiry.strftime("%Y-%m-%d_%H:%M:%S")

        # The sharp bit, where the snapshot is created
        response = rds_client.create_db_snapshot(DBSnapshotIdentifier=snapshotname, DBInstanceIdentifier=dbInstanceName, Tags=[{ 'Key': 'snapshot_expiry', 'Value': expiry }])
        snapshot = response['DBSnapshot']

        # Done so send to log
        print('Snapshot created for %s: %s' %(dbInstanceName, snapshotname))
      else:
        # Send a message to the log that the databse wasn't available for snapshotting
        # Not sure if some sort of 'wait and try again' loop should added here as it can take a long time
        # Perhaps a wait, try again, wait then quit if still not available
        print('Database %s is not available - will try again later' %(dbInstanceName))
  except Exception as e:
    print('Exception occurred for RDS instance %s : %s' %(instance['DBInstanceIdentifier'], e))

