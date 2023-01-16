#! /usr/bin/env python

# Simple Python script to manage RDS snapshots
# Kept simple for now; little or no checking that input values in tags are correctly formatted etc
# Can be added in the future

# Run this script as a Kubernetes CronJob once per hour
# It will walk through all databases in the account and takes snapshots according to individuals schedules
# that are set per database and saved as tags. Databases with no such setting will be managed according to
# a currently hardcoded default schedule

# Uses UTC time zone

# Snapshot retention time can be included as a tag also so code to delete expired snapshots will need to be written
# Not yet decided if this will be included in this script or run as a separate script/CronJob

# Uses these tags on the RDS instance:
#  snapshot_retention_days -> number of days to retain the snapshot; used to calculate value in snapshot expiry tag 
#  snapshot_schedule -> space separated list of whole hours 00 - 23 to take snapshots (must be '00' '01' not '0' '1' etc) 
#  snapshot_latest -> tracks successful snapshots; content is either the hour of the successful snapshot or 'skipped' if not
#  snapshot_never -> disables snapshots if it exists; tag content is ignored
#
# Each snapshot gets tagged with an expiry timestamp, calculated from current timestamp plus retention days
# Characters such as comma (,) cannot be used in AWS tags so spaces used in schedule instead
# Scheduling is on an hourly basis, order of hours is not important and neither is distribution so 
#  snapshots could for example be taken hourly during office hours then at midnight
# Retention and scheduling tags should be defined for each RDS instance; default values are used otherwise
#  90 day retention and once per day at 0200
# The third tag is created and maintained internally by the script

import boto3
import datetime, time

# Get current hour of day for 24 hour clock
# Is returned in the form '00' to '23' so the scheduling hours also need to be in this form
hour = str(time.strftime("%H"))

# Timestamp value to make snapshot identifier unique; simple date-time for now
timestamp = str(time.strftime("%Y%m%d%H%M%S"))

# Get the current date + time for setting expiry date
datetime_now = datetime.datetime.now()

# Connect to rds instance
# No access keys here so other authentication needed
rds_client = boto3.client(
            'rds',
            'eu-north-1')

#rds_instance will have all rds information in dictionary.
rds_instances = rds_client.describe_db_instances()

for instance in rds_instances['DBInstances']: 
  dbInstanceName = instance['DBInstanceIdentifier']
  dbInstanceEngine = instance['DBInstanceClass']
  dbInstanceStatus = instance['DBInstanceStatus']
  dbInstanceArn = instance["DBInstanceArn"]

  # Set default values; will ge overwritten if found
  # Ninety days retention; default snapshot once every 24 hours at 2 am
  # Strings and list of strings
  retention_days = '90'
  schedule_string = '02'
  # Set to true if database tagged as never to be backed up
  no_snapshot = False
  # Means that snapshots will be taken first time RDS instance is found regardless of scheduling
  last_snapshot = 'skipped' 
  # rds_client.remove_tags_from_resource(ResourceName=dbInstanceArn, TagKeys=[''])
  tags = rds_client.list_tags_for_resource(ResourceName=dbInstanceArn)
  for tag in tags["TagList"]:
    if tag['Key'] == 'snapshot_never': no_snapshot = True
    if tag['Key'] == "snapshot_retention_days": retention_days = tag['Value']
    if tag['Key'] == 'snapshot_schedule': schedule_string = tag['Value']
    if tag['Key'] == 'snapshot_latest': 
      last_snapshot = tag['Value']
      # Delete the tag; no method availble for updating so remove and replace
      rds_client.remove_tags_from_resource(ResourceName=dbInstanceArn, TagKeys=['snapshot_latest'])

  # Convert schedule string to list
  schedule_list = schedule_string.split(" ")

  # print('Instance %s, Retention %s days, Schedule %s' %(dbInstanceName, retention_days, schedule_list))

  if no_snapshot:
    print('Database %s tagged as never to be backed up' %(dbInstanceName))
  elif last_snapshot == hour:
    print('Snapshot already done for %s this hour %s so skipping it' %(dbInstanceName, hour))
    rds_client.add_tags_to_resource(ResourceName=dbInstanceArn, Tags=[{ 'Key': 'snapshot_latest', 'Value': hour }])
  # Is the current hour in the schedule or was it skipped last time?
  elif hour in schedule_list or last_snapshot == 'skipped': 
    # OK snapshot time
    # The source DB instance must be in the available or storage-optimization state so get status
    # print('Hour in list: %s' %(hour))
    dbInstanceStatus = instance['DBInstanceStatus']

    if dbInstanceStatus in ['available', 'storage-optimization']:
      # print('Yes still available')
      # Snapshot identifier needs to be unique
      snapshotname = dbInstanceName + '-' + timestamp

      print('Snapshot created for %s: %s' %(dbInstanceName, snapshotname))
      datetime_expiry = datetime_now + datetime.timedelta(days=int(retention_days))
      expiry = datetime_expiry.strftime("%Y-%m-%d_%H:%M:%S")
      print('Expiry tag: %s' %(expiry))
      # """
      response = rds_client.create_db_snapshot(DBSnapshotIdentifier=snapshotname, DBInstanceIdentifier=dbInstanceName, Tags=[{ 'Key': 'snapshot_expiry', 'Value': expiry }])
      snapshot = response['DBSnapshot']
      # """
      # Add current hour as tag if succeeded
      rds_client.add_tags_to_resource(ResourceName=dbInstanceArn, Tags=[{ 'Key': 'snapshot_latest', 'Value': hour }])
    else:
      # Or flag it as skipped so it gets picked up next time
      rds_client.add_tags_to_resource(ResourceName=dbInstanceArn, Tags=[{ 'Key': 'snapshot_latest', 'Value': 'skipped' }])
      print('Database %s is not available - will try again later' %(dbInstanceName))
  else:
    # Set back to original value
    rds_client.add_tags_to_resource(ResourceName=dbInstanceArn, Tags=[{ 'Key': 'snapshot_latest', 'Value': last_snapshot }])
    print('No snapshots scheduled for %s this hour %s' %(dbInstanceName, hour))
